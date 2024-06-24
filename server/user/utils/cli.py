import functools
import logging
import json
import hashlib
import os
import shutil
from time import sleep
import functools
import subprocess

TERMINAL_SIZE = shutil.get_terminal_size()
LOG_SEPARATOR = "\n{}\n".format(
    "-" * int(TERMINAL_SIZE[0] * 80 / 100)
    if TERMINAL_SIZE[0] > 80
    else TERMINAL_SIZE[0]
)
logging.basicConfig(format="[%(asctime)s]  %(name)s  %(message)s")
logger = logging.getLogger(__name__)


def wait(path, log=False, interval=2):
    logger.warning("WAIT  %s", path)
    keys = []
    if os.path.isfile(path):
        keys = [path]
    elif os.path.isdir(path):
        keys = os.listdir(path)
    if len(keys) == 0:
        sleep(interval)
        wait(path)
        return False
    if log:
        logger.warning("WAIT LOG  %s%s\n", keys[-1], LOG_SEPARATOR)
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


def map_options(env=[], ports=[], entrypoint=[], volumes=[]):
    ports_map = []
    for pair in map(lambda p: ("-p", "{0}:{0}".format(p[1])), ports):
        try:
            int(pair[0])
        except ValueError as _:
            continue
        ports_map.extend(pair)

    entrypoint_map = []
    for opt in [*ports, *entrypoint]:
        name, value = opt

        if value in ("", None, False, 0):
            continue
        elif value in (True, 1):
            entrypoint_map.append(name)
            continue

        entrypoint_map.extend((name, value))

    env_map = []
    for opt in env:
        name, value = opt

        if value in ("", None):
            continue
        env_map.extend(("-e", "%s=%s" % (name, value)))

    volumes_map = []
    for opt in volumes:
        name, value = opt

        if value in ("", None):
            continue
        volumes_map.extend(("-v", "%s:%s" % (name, value)))

    return {
        "ports": ports_map,
        "entrypoint": entrypoint_map,
        "env": env_map,
        "volumes": volumes_map,
    }


def load_json(path):
    with open(path, "r") as fd:
        return json.load(fd)


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


def validate_password(word):
    if word:
        if len(word) < 10:
            raise ValueError("PASSWORD must be at least 10 characters")
        return True
    else:
        raise ValueError("PASSWORD is required")


def on(condition):
    def decorator_run_ps(func):
        @functools.wraps(func)
        def wrapper_run_ps(*args, **kwargs):
            if condition:
                return func(*args, **kwargs)

        return wrapper_run_ps

    return decorator_run_ps


def cleanup_container(name, cwd=os.getcwd()):
    logger.warning("CLEANUP CONTAINER  %s", name)
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
        logger.warning("CLEAN UP CONTAINER - Error not handled  %s", e)
