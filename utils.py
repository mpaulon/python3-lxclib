import os
import subprocess
import sys
from pathlib import Path


def _open_in(filepath: Path, editor: str):
    command = [editor, filepath.as_posix()]
    process = subprocess.Popen(
        command,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    ret_code = process.wait()
    if ret_code != 0:
        raise RuntimeError(f"Failed to open {filepath} in {editor}")


def open_in_editor(filepath: Path):
    return _open_in(filepath, os.environ.get("EDITOR", "less"))


def open_in_pager(filepath: Path):
    return _open_in(filepath, os.environ.get("PAGER", "less"))
