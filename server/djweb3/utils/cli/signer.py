import os
import shutil
import subprocess

from djweb3.utils.mapper import Mapper
from djweb3.utils.models import SingletonAbstract
from djweb3.utils import load_json, sha256sum, touch, Logger
from djweb3.utils.validator import Validator


class Signer(SingletonAbstract):

    def __init__(self, **kwargs) -> None:
        self.path = kwargs["path"]
        self.env = kwargs["env"]
        self.cmd = kwargs["cmd"]

        try:
            if not os.path.isdir(self.path()):
                os.makedirs(self.path("data/keystore"))
                # touch(self.path("run/pcscd/pcscd.comm"))
                touch(
                    self.path("config/rules.js"),
                    self.env["rules_js"],
                )
                touch(
                    self.path("config/4byte.json"),
                    self.env["4bytedb"],
                )
                os.makedirs(self.path("clef"))

            self.seed()
            self.attest()

            Logger.info("init", "signer", "success")
        except Exception as e:
            Logger.error("signer", e)

    # SUDO: use master password
    def seed(self):
        # Generate master seed to be able to store credentials
        subprocess.check_call(
            [
                *self.cmd["entrypoint"],
                " ".join(
                    [
                        *self.cmd["bin"],
                        "--configdir",
                        "/app/data",
                        "--stdio-ui",
                        "init",
                        ">/dev/null 2>&1 << EOF\n%sEOF"
                        % ("{0}\n" * 2).format(self.env["master_password"]),
                    ]
                ),
            ],
            cwd=self.cmd["cwd"],
        )
        return True

    # SUDO: use master password
    def attest(self):
        # Attest to rulesets integrity
        if os.path.isfile(self.path("config/rules.js")):
            subprocess.check_call(
                [
                    *self.cmd["entrypoint"],
                    " ".join(
                        [
                            *self.cmd["bin"],
                            "--configdir",
                            "/app/data",
                            "--keystore",
                            "/app/data/keystore",
                            "--stdio-ui",
                            "attest",
                            self.sha256sum_rules_js,
                            ">/dev/null 2>&1 << EOF\n%sEOF"
                            % ("{0}\n").format(self.env["master_password"]),
                        ]
                    ),
                ],
                cwd=self.cmd["cwd"],
            )
            return True

    def newaccount(self, user_pwd):
        # Create account and Generate keystore (with the account password)
        if Validator.password(user_pwd):
            subprocess.check_call(
                [
                    *self.cmd["entrypoint"],
                    " ".join(
                        [
                            *self.cmd["bin"],
                            "--keystore",
                            "/app/data/keystore",
                            "--stdio-ui",
                            "newaccount",
                            "--lightkdf",
                            ">/dev/null 2>&1 << EOF\n%sEOF"
                            % ("{0}\n" * 1).format(user_pwd),
                        ]
                    ),
                ],
                cwd=self.cmd["cwd"],
            )
            return True

    # SUDO: use master password
    def setpw(self, user_pwd):
        # Store a credential for the generated keystore file
        if Validator.password(user_pwd):
            subprocess.check_call(
                [
                    *self.cmd["entrypoint"],
                    " ".join(
                        [
                            *self.cmd["bin"],
                            "--configdir",
                            "/app/data",
                            "--keystore",
                            "/app/data/keystore",
                            "--stdio-ui",
                            "setpw",
                            "0x%s" % self.wallet_address_eth,
                            ">/dev/null 2>&1 << EOF\n%sEOF"
                            % ("{user}\n{user}\n{master}\n").format(
                                user=user_pwd,
                                master=self.env["master_password"],
                            ),
                        ]
                    ),
                ],
                cwd=self.cmd["cwd"],
            )

            return self.wallet_address_eth

    @property
    def wallet_address_eth(self):
        try:
            basename = os.listdir(self.path("data/keystore"))[-1]
            return load_json(self.path("data/keystore", basename))["address"]
        except (IndexError, KeyError) as e:
            Logger.error("account not found  %s", e)

    @property
    def sha256sum_rules_js(self):
        try:
            with open(self.path("config/rules.js"), "r") as fd:
                return sha256sum(fd.read())
        except FileNotFoundError as e:
            Logger.error("account not found - attest rulesets  %s", e)

    @classmethod
    def parse_options(cls, options):
        try:
            # Mandatory
            ports = []
            cmd = [
                ("--chainid", options["chainid"]),
                ("--nousb", "nousb" in options),
                ("--lightkdf", "lightkdf" in options),
                (
                    ("--ipcdisable", True)
                    if options["api"]["ipc"]["ipcdisable"]
                    else (
                        "--ipcpath",
                        options["api"]["ipc"]["ipcpath"] or "/app/clef/clef.ipc",
                    )
                ),
                # ("--pcscdpath", "/run/pcscd/pcscd.comm") # $GETH_PCSCDPATH,
                ("--http", "http" in options["api"]),
            ]

            # Conditional
            required = {"http": options["api"]["http"]}
            if required["http"]:
                ports.extend(
                    [
                        (
                            "--http.port",
                            options["api"]["http"].get("port", "8550"),
                        ),
                    ]
                )
                cmd.extend(
                    [
                        (
                            "--http.addr",
                            options["api"]["http"].get("addr", "localhost"),
                        ),
                        (
                            "--http.vhosts",
                            options["api"]["http"].get("vhosts", "localhost"),
                        ),
                    ]
                )

            mapping = Mapper.client_options(ports=ports, cmd=cmd)
            return {
                "tty": options["tty"],
                "ports": mapping["ports"],
                "cmd": [*mapping["cmd"], "<<EOF\nok\nEOF"],
            }
        except Exception as e:
            Logger.error("signer config", e)

    @classmethod
    def volumes(cls, path):
        return [
            {
                "type": "bind",
                "source": path("config/rules.js"),
                "target": "/app/config/rules.js",
                # ensure integrity
                "read_only": True,
            },
            {
                "type": "bind",
                "source": path("config/4byte.json"),
                "target": "/app/config/4byte.json",
                # ensure integrity
                "read_only": True,
            },
            {
                "type": "bind",
                "source": path("data"),
                "target": "/app/data/",
            },
            {
                "type": "tmpfs",
                # "source": path("tmp/stdin"),
                "target": "/tmp/stdin",
                "read_only": True,
                "tmpfs": {
                    "size": "1gb",
                    # restricted deletion, owner readable
                    "mode": 1400,
                },
            },
            {
                "type": "tmpfs",
                # "source": path("tmp/stdout"),
                "target": "/tmp/stdout",
                "tmpfs": {
                    "size": "1gb",
                    # restricted deletion, owner writable
                    "mode": 1200,
                },
            },
            {
                "type": "bind",
                "source": path("clef/"),
                "target": "/app/clef/",
                "bind": {
                    "selinux":
                    # shared only with `execution`, related to `ipc` docker property
                    "z"
                },
            },
        ]
