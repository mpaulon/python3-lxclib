import enum
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


class Container:
    """manage lxc container"""

    class MissingInformationsError(Exception):
        """raised when a creation failed due to missing informations for template"""

    class MustUseForceError(Exception):
        """raised when and action is impossible except with the use of force"""

    class SystemdRunError(Exception):
        """raised when an error occurs under systemd-run"""

        def __init__(self, command, output, *args: object) -> None:
            self._command = command
            self._output = output
            super().__init__(*args)

        @property
        def pretty_command(self):
            """return a pretty command you can copy/paste in your terminal"""
            return " ".join(self._command)

        @property
        def output(self):
            return self._output

    class State(enum.Enum):
        """lxc container states"""

        RUNNING = 0
        STOPPED = 1
        ABSENT = 2

    def __init__(
        self,
        name: str,
        distribution: Optional[str] = None,
        release: Optional[str] = None,
        architecture: Optional[str] = None,
    ) -> None:
        self.name = name
        self.distribution = distribution
        self.release = release
        self.architecture = architecture

    def __str__(self) -> str:
        return self.name

    @property
    def state(self):
        """get container state"""
        try:
            _out = subprocess.check_output(
                ["lxc-info", "--state", "--name", self.name],
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            return self.State.ABSENT
        _state = _out.decode().split(":")[1].strip().upper()
        return self.State[_state]

    @classmethod
    def list_all(cls):
        """list all containers on the system"""
        _out = subprocess.check_output(["lxc-ls", "--line"])
        _containers = _out.decode().strip().split("\n")
        return [Container(name=c) for c in _containers]

    @classmethod
    def list_info(cls):
        """return dict of containers infos"""
        return {c.name: c.info() for c in cls.list_all()}

    def _systemd_run(self, unit_name: str, command: list[str], bind: bool = False):
        complete_command = [
            "systemd-run",
            "--unit",
            unit_name,
            "--user",
            "--scope",
            "-p",
            "Delegate=yes",
            "--",
        ] + command
        if bind:
            process = subprocess.Popen(
                complete_command,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            ret_code = process.wait()
            if ret_code != 0:
                raise self.SystemdRunError(command=complete_command, output=None)
        else:
            try:
                subprocess.run(
                    complete_command,
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as err:
                raise self.SystemdRunError(
                    command=complete_command, output=err.output.decode()
                )

    def _systemd_run_stop(self):
        command = ["lxc-stop", "--name", self.name]
        unit_name = "lxc-stop-" + self.name
        return self._systemd_run(unit_name, command)

    def _systemd_run_start(self):
        command = ["lxc-start", "--name", self.name]
        unit_name = "lxc-start-" + self.name
        return self._systemd_run(unit_name, command)

    def _systemd_run_create(self):
        if (
            self.distribution is None
            or self.release is None
            or self.architecture is None
        ):
            raise self.MissingInformationsError()
        command = ["lxc-create", "--template", "download", "--name", self.name, "--"]
        options = [
            "--dist",
            self.distribution,
            "--release",
            self.release,
            "--arch",
            self.architecture,
        ]
        unit_name = "lxc-create-" + self.name
        return self._systemd_run(unit_name, command + options)

    def _systemd_run_destroy(self):
        command = ["lxc-destroy", "--name", self.name]
        unit_name = "lxc-destroy-" + self.name
        return self._systemd_run(unit_name, command)

    def _systemd_run_attach(
        self, inner_command: Optional[list[str]] = None, bind: bool = False
    ):
        command = ["lxc-attach", "--name", self.name]
        if inner_command is not None:
            command.append("--")
            command += inner_command
        unit_name = "lxc-attach-" + self.name
        return self._systemd_run(unit_name, command, bind)

    def stop(self, check: bool = False):
        """stop container"""
        if self.state == self.State.STOPPED:
            return False
        if not check:
            self._systemd_run_stop()
        return True

    def start(self, force: bool = False, check: bool = False):
        """start container, if force make sure container exists"""
        if self.state == self.State.RUNNING:
            return False
        if self.state == self.State.ABSENT and not force:
            raise self.MustUseForceError()
        self.create(check=check)
        if not check:
            self._systemd_run_start()
        return True

    def create(self, check: bool = False):
        """create container"""
        if self.state != self.State.ABSENT:
            return False
        if not check:
            self._systemd_run_create()
        return True

    def destroy(self, force: bool = False, check: bool = False):
        """destroy container, if force stop it"""
        if self.state == self.State.ABSENT:
            return False
        if self.state != self.state.STOPPED and not force:
            raise self.MustUseForceError()
        self.stop(check=check)
        if not check:
            self._systemd_run_destroy()
        return True

    def restart(self, force: bool = False, check: bool = False):
        """restart lxc container"""
        self.stop(check)
        self.start(force, check)
        return True

    def attach(
        self,
        command: Optional[list[str]] = None,
        bind: bool = False,
        force_run: bool = False,
        force: bool = False,
        check: bool = False,
    ):
        """attach lxc container"""
        force_run = force_run or force
        if self.state != self.State.RUNNING and not force_run:
            raise self.MustUseForceError()
        self.start(force=force, check=check)
        if not check:
            self._systemd_run_attach(command, bind)
        return True

    def info(self):
        """return container infos"""
        try:
            _out = subprocess.check_output(
                ["lxc-info", "--state", "--ips", "--pid", "--name", self.name],
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            return {"state": self.State.ABSENT}

        _infos = {}
        for _info in _out.decode().strip().split("\n"):
            _info = _info.split(":")
            _info_key = _info[0].lower()
            if _info_key in _infos:
                if not isinstance(_infos[_info_key], list):
                    _infos[_info_key] = [_infos[_info_key]]
                _infos[_info_key].append(_info[1].strip().lower())
            else:
                _infos[_info_key] = _info[1].strip().lower()
        if "state" in _infos:
            _infos["state"] = self.State[_infos["state"].upper()]
        return _infos

    @property
    def container_folder(self):
        """return path to folder containing rootfs and config of the container"""
        return Path.home() / Path(".local/share/lxc") / self.name

    @property
    def config_file(self):
        """return container config file path"""
        return self.container_folder / "config"
