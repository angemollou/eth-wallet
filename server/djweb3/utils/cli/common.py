import functools
import json
import hashlib
import os
from time import sleep
import functools
import subprocess
import yaml

from djweb3.utils.event import LOG_SEPARATOR, Logger


def wait_fd(path, interval=2, log=False):
    Logger.info("WAIT  %s", path)
    keys = []
    if os.path.isfile(path):
        keys = [path]
    elif os.path.isdir(path):
        keys = os.listdir(path)
    if len(keys) == 0:
        sleep(interval)
        wait_fd(path)
        return False
    if log:
        Logger.info("WAIT LOG  %s%s\n", keys[-1], LOG_SEPARATOR)
    return keys[-1]


def touch(path, content=None):
    if os.path.isfile(path):
        return path
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    if content is None:
        open(path, "a").close()
    else:
        with open(path, "w+") as fd:
            fd.write(content)

    return path


def load_json(path):
    with open(path, "r") as fd:
        return json.load(fd)


def dump_json(data, path):
    with open(path, "w+") as fd:
        return json.dump(data, fd)


def dump_yaml(data, path):
    with open(path, "w+") as fd:
        return fd.write(yaml.dump(data, default_flow_style=False))


def sha256sum(text):
    m = hashlib.sha256()
    m.update(text.encode())
    return m.hexdigest()


def set_on(opt, condition, fallback=None):
    if condition:
        return [opt]
    elif fallback is not None:
        return [fallback]
    else:
        return []


def on(condition):
    def decorator_run_ps(func):
        @functools.wraps(func)
        def wrapper_run_ps(*args, **kwargs):
            if condition:
                return func(*args, **kwargs)

        return wrapper_run_ps

    return decorator_run_ps


def cleanup_container(name, cwd=os.getcwd()):
    Logger.info("CLEANUP CONTAINER  %s", name)
    try:
        found = (
            subprocess.run(
                [
                    "docker",
                    "container",
                    "ls",
                    "-a",
                    "-f",
                    "name=%s" % name,
                ],
                cwd=cwd,
                capture_output=True,
                text=True,
            ).stdout.find(name)
            != -1
        )
        if found:
            subprocess.check_call(
                [
                    "docker",
                    "container",
                    "stop",
                    name,
                ],
                cwd=cwd,
                stderr=subprocess.DEVNULL,
            )
            subprocess.call(
                [
                    "docker",
                    "container",
                    "rm",
                    name,
                ],
                cwd=cwd,
                stderr=subprocess.DEVNULL,
            )
    except Exception as e:
        Logger.info("CLEAN UP CONTAINER - Error not handled  %s", e)
