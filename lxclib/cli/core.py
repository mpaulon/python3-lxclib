import argparse
import logging
import shlex

import lxclib

from . import utils

logger = logging.getLogger(__name__)


def list_containers(_args):
    if _args.json:
        print(lxclib.Container.list_info())
    else:
        for c in lxclib.Container.list_all():
            if _args.details:
                print(c, c.info())
            else:
                print(c)


def attach_container(_args):
    container = lxclib.Container(_args.name)
    try:
        container.attach(
            shlex.split(_args.command),
            bind=not _args.no_bind,
            force_run=_args.force_run,
            force=_args.force,
        )
    except lxclib.Container.SystemdRunError as err:
        logger.critical("Command %s failed with %s", err.pretty_command, err.output)


def start_container(_args):
    container = lxclib.Container(_args.name)
    try:
        container.start()
    except lxclib.Container.SystemdRunError as err:
        logger.critical("Command %s failed with %s", err.pretty_command, err.output)


def stop_container(_args):
    container = lxclib.Container(_args.name)
    try:
        container.stop()
    except lxclib.Container.SystemdRunError as err:
        logger.critical("Command %s failed with %s", err.pretty_command, err.output)


def restart_container(_args):
    stop_container(_args)
    start_container(_args)


def destroy_container(_args):
    container = lxclib.Container(_args.name)
    try:
        container.destroy(force=_args.force)
    except lxclib.Container.SystemdRunError as err:
        logger.critical("Command %s failed with %s", err.pretty_command, err.output)
    except lxclib.Container.MustUseForceError:
        logger.critical("Container cannot be destroyed, try using --force")


def create_container(_args):
    container = lxclib.Container(
        _args.name, _args.distribution, _args.release, _args.architecture
    )
    try:
        container.create()
    except lxclib.Container.SystemdRunError as err:
        logger.critical("Command %s failed with %s", err.pretty_command, err.output)


def info_container(_args):
    container = lxclib.Container(_args.name)
    try:
        print(container.info())
    except lxclib.Container.SystemdRunError as err:
        logger.critical("Command %s failed with %s", err.pretty_command, err.output)


def config_container(_args):
    container = lxclib.Container(_args.name)
    if _args.show:
        return utils.open_in_pager(container.config_file.absolute())
    if _args.edit:
        return utils.open_in_editor(container.config_file.absolute())


def run():
    logging.basicConfig()

    parser = argparse.ArgumentParser()
    parser.set_defaults(func=parser.print_help)
    subparser = parser.add_subparsers()
    list_parser = subparser.add_parser("list")
    list_parser.add_argument("--json", action="store_true")
    list_parser.add_argument("--details", action="store_true")
    list_parser.set_defaults(func=list_containers)

    parser_container = subparser.add_parser("container")
    parser_container.add_argument("--name", type=str, required=True)
    subparser_container = parser_container.add_subparsers()

    attach_parser = subparser_container.add_parser("attach", aliases=["exec"])
    attach_parser.add_argument("command", type=str)
    attach_parser.add_argument("--no-bind", action="store_true", required=False)
    attach_parser.add_argument("--force-run", action="store_true", required=False)
    attach_parser.add_argument("--force", action="store_true", required=False)
    attach_parser.set_defaults(func=attach_container)

    start_parser = subparser_container.add_parser("start")
    start_parser.set_defaults(func=start_container)

    stop_parser = subparser_container.add_parser("stop")
    stop_parser.set_defaults(func=stop_container)

    restart_parser = subparser_container.add_parser("restart")
    restart_parser.set_defaults(func=restart_container)

    destroy_parser = subparser_container.add_parser("destroy")
    destroy_parser.add_argument("--force", action="store_true")
    destroy_parser.set_defaults(func=destroy_container)

    create_parser = subparser_container.add_parser("create")
    create_parser.add_argument("--distribution", type=str, required=True)
    create_parser.add_argument("--release", type=str, required=True)
    create_parser.add_argument("--architecture", type=str, required=True)
    create_parser.set_defaults(func=create_container)

    info_parser = subparser_container.add_parser("info")
    info_parser.add_argument("--json", action="store_true")
    info_parser.set_defaults(func=info_container)

    config_parser = subparser_container.add_parser("config")
    config_parser.add_argument("--show", action="store_true")
    config_parser.add_argument("--edit", action="store_true")
    config_parser.set_defaults(func=config_container)

    args = parser.parse_args()
    args.func(args)
