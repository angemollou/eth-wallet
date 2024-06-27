import os
import subprocess
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from djweb3.utils.cli import (
    dump_json,
    wait_fd,
    LOGGER,
    set_on,
    cleanup_container,
    on,
    touch,
    LOG_SEPARATOR,
    load_json,
    sha256sum,
)
from djweb3.utils.mapper import Mapper
from djweb3.utils.validator import Validator
from djweb3.utils.normalizer import Normalizer

BASE_DIR = settings.ETH_NODE["base_dir"]
NETWORKS = settings.ETH_NODE["signer"]["chain_id"]
CHAIN_ID = next(filter(lambda k: NETWORKS[k], NETWORKS))


class Command(BaseCommand):
    help = "Run a Ethereum node via docker"

    def add_arguments(self, parser):
        parser.add_argument(
            "-t",
            "--tty",
            action="store_true",
            help="Enable the TTY of runtime sys",
        )
        # SIGNER self.options
        parser.add_argument(
            "-u",
            "--newaccount",
            action="store_true",
            help="Request a new wallet address",
        )
        parser.add_argument(
            "-w",
            "--password",
            help="A password that is at least 10 characters long",
        )
        parser.add_argument(
            "-r",
            "--reset",
            action="store_true",
            help="Clean all data",
        )
        # EXECUTION self.options
        parser.add_argument(
            "--http",
            action="store_true",
            help="Enable the HTTP-RPC server",
            default=settings.ETH_NODE["execution"]["api"]["http"],
        )
        parser.add_argument(
            "--http.addr",
            help="HTTP-RPC server listening interface",
            default=(
                settings.ETH_NODE["execution"]["api"]["http"].get("addr", "localhost")
                if settings.ETH_NODE["execution"]["api"]["http"]
                else None
            ),
        )
        parser.add_argument(
            "--http.port",
            help="HTTP-RPC server listening port",
            default=(
                settings.ETH_NODE["execution"]["api"]["http"].get("port", "8545")
                if settings.ETH_NODE["execution"]["api"]["http"]
                else None
            ),
        )
        parser.add_argument(
            "--http.api",
            help="Namespaces accessible over the HTTP-RPC interface",
            nargs="+",
            default=(
                settings.ETH_NODE["execution"]["api"]["http"].get(
                    "namespaces", "eth,net,web3"
                )
                if settings.ETH_NODE["execution"]["api"]["http"]
                else None
            ),
        )
        parser.add_argument(
            "--http.corsdomain",
            help="Comma separated list of domains from which to accept cross origin requests (browser enforced)",
            nargs="+",
            default=(
                settings.ETH_NODE["execution"]["api"]["http"].get("corsdomain")
                if settings.ETH_NODE["execution"]["api"]["http"]
                else None
            ),
        )
        parser.add_argument(
            "--ws",
            action="store_true",
            help="Enable the WS-RPC server",
            default=settings.ETH_NODE["execution"]["api"]["ws"],
        )
        parser.add_argument(
            "--ws.addr",
            help="WS-RPC server listening interface",
            default=(
                settings.ETH_NODE["execution"]["api"]["ws"].get("addr", "localhost")
                if settings.ETH_NODE["execution"]["api"]["ws"]
                else None
            ),
        )
        parser.add_argument(
            "--ws.port",
            help="WS-RPC server listening port",
            default=(
                settings.ETH_NODE["execution"]["api"]["ws"].get("port", "3334")
                if settings.ETH_NODE["execution"]["api"]["ws"]
                else None
            ),
        )
        parser.add_argument(
            "--ws.api",
            help="Namespaces accessible over the WS-RPC interface",
            nargs="+",
            default=(
                settings.ETH_NODE["execution"]["api"]["ws"].get(
                    "namespaces", "eth,net,web3"
                )
                if settings.ETH_NODE["execution"]["api"]["ws"]
                else None
            ),
        )
        parser.add_argument(
            "--ws.origins",
            help="Comma separated list of domains from which to accept WebSocket requests",
            nargs="+",
            default=(
                settings.ETH_NODE["execution"]["api"]["ws"].get("origins", "localhost")
                if settings.ETH_NODE["execution"]["api"]["ws"]
                else None
            ),
        )
        parser.add_argument(
            "--ipcdisable",
            action="store_true",
            help="Disable the IPC-RPC server",
            default=settings.ETH_NODE["execution"]["api"]["ipc"]["ipcdisable"],
        )
        parser.add_argument(
            "--authrpc.addr",
            help="AUTH-RPC server listening interface",
            default=settings.ETH_NODE["execution"]["auth"].get("addr", "localhost"),
        )
        parser.add_argument(
            "--authrpc.port",
            help="AUTH-RPC server listening port",
            default=settings.ETH_NODE["execution"]["auth"].get("port", "8551"),
        )
        parser.add_argument(
            "--authrpc.vhosts",
            help="Comma separated list of domains from which to accept AUTH requests",
            nargs="+",
            default=settings.ETH_NODE["execution"]["auth"].get("origins", "localhost"),
        )
        parser.add_argument(
            "--signer",
            help="<addr>:<port> of the tool for signing transactions and data",
            default=settings.ETH_NODE["execution"].get("signer", "localhost:8550"),
        )

    ps_cmd = None
    is_newaccount_required = False
    options = dict()

    def handle(self, *args, **options):
        try:
            self.options = options
            if self.options["reset"]:
                shutil.rmtree(BASE_DIR, ignore_errors=True)

            dump_json(
                self.compose(["signer", "execution"]),
                settings.ETH_NODE["output"]["docker"]["json"],
            )
            wait_fd(
                settings.ETH_NODE["output"]["docker"]["json"],
                settings.ETH_NODE["wait_throttle_time"],
                True,
            )
            # TODO: Convert docker-compose.json to yml
            # dump_json(self.compose, settings.ETH_NODE['output']['docker']['yaml'])

            self.ps_cmd = self.up()

        except Exception as e:
            LOGGER.error("ERROR was not handled  %s", e)
            raise e
        finally:
            self.down()

    def up(self):
        self.ps_cmd = [
            "docker-compose",
            "-f",
            str(settings.ETH_NODE["output"]["docker"]["json"]),
            "up",
        ]
        subprocess.check_call(self.ps_cmd, cwd=BASE_DIR)
        return self.ps_cmd

    def init_signer(self):
        try:
            if self.options["reset"] or (
                self.options["newaccount"]
                and len(os.listdir(self.path_signer("data/keystore"))) == 0
            ):
                shutil.rmtree(self.path_signer(), ignore_errors=True)

            if not os.path.isdir(self.path_signer()):
                os.makedirs(self.path_signer("data/keystore"))
                touch(self.path_signer("tmp/stdin"))
                touch(self.path_signer("tmp/stdout"))
                # touch(self.signer_path("run/pcscd/pcscd.comm"))
                touch(
                    self.path_signer("config/rules.js"),
                    settings.ETH_NODE["signer"]["rules_js"],
                )
                touch(
                    self.path_signer("config/4byte.json"),
                    settings.ETH_NODE["signer"]["4BYTEDB_CUSTOM"],
                )
                if not settings.ETH_NODE["signer"]["api"]["ipc"]["ipcdisable"]:
                    os.makedirs(self.path_signer("clef"))

            cmd_init = [
                "docker",
                "run",
                # tty enable docker logs coloring
                *set_on("-t", self.options["tty"]),
                "--name",
                settings.ETH_NODE["signer"]["name"],
                "--rm",
                *Mapper.volumes(self.client_options_signer["volumes"]),
                # OPTIONAL: for SmartCard (character device file)
                # "-v",
                # "%s:/run/pcscd/pcscd.comm" % self.signer_path("run/pcscd/pcscd.comm"),
                "--entrypoint",
                settings.ETH_NODE["signer"]["entrypoint"][0],
                settings.ETH_NODE["signer"]["image"],
                *settings.ETH_NODE["signer"]["entrypoint"][1:],
            ]

            self.signer_seed(cmd_init)

            if (
                len(os.listdir(self.path_signer("data/keystore"))) == 0
                or self.options["password"]
            ):
                self.signer_newaccount(self.options["password"], cmd_init)

                self.signer_setpw(self.options["password"], cmd_init)

            self.signer_attest(settings.ETH_NODE["signer"]["master_password"], cmd_init)

            return True
        except Exception as e:
            self.handle_error("signer  init", e)

    def signer_attest(self, master_pwd, cmd):
        # Attest to rulesets integrity
        if os.path.isfile(self.path_signer("config/rules.js")):
            subprocess.check_call(
                [
                    *cmd,
                    " ".join(
                        [
                            settings.ETH_NODE["signer"]["bin"],
                            "--configdir",
                            "/app/data",
                            "--keystore",
                            "/app/data/keystore",
                            "--stdio-ui",
                            "attest",
                            self.sha256sum_rules_js,
                            ">/dev/null 2>&1 << EOF\n%sEOF"
                            % ("{0}\n").format(master_pwd),
                        ]
                    ),
                ],
                cwd=BASE_DIR,
            )
            cleanup_container(settings.ETH_NODE["signer"]["name"])

    def signer_setpw(self, user_pwd, cmd):
        # Store a credential for the generated keystore file
        if Validator.password(user_pwd):
            subprocess.check_call(
                [
                    *cmd,
                    " ".join(
                        [
                            settings.ETH_NODE["signer"]["bin"],
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
                                master=settings.ETH_NODE["signer"]["master_password"],
                            ),
                        ]
                    ),
                ],
                cwd=BASE_DIR,
            )
            cleanup_container(settings.ETH_NODE["signer"]["name"])

    def signer_newaccount(self, user_pwd, cmd):
        # Create account and Generate keystore (with the account password)
        if Validator.password(user_pwd):
            subprocess.check_call(
                [
                    *cmd,
                    " ".join(
                        [
                            settings.ETH_NODE["signer"]["bin"],
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
                cwd=BASE_DIR,
            )
            cleanup_container(settings.ETH_NODE["signer"]["name"])

    @on(Validator.password(settings.ETH_NODE["signer"]["master_password"]))
    def signer_seed(self, cmd):
        # Generate master seed to be able to store credentials
        subprocess.check_call(
            [
                *cmd,
                " ".join(
                    [
                        settings.ETH_NODE["signer"]["bin"],
                        "--configdir",
                        "/app/data",
                        "--stdio-ui",
                        "init",
                        ">/dev/null 2>&1 << EOF\n%sEOF"
                        % ("{0}\n" * 2).format(
                            settings.ETH_NODE["signer"]["master_password"]
                        ),
                    ]
                ),
            ],
            cwd=BASE_DIR,
        )
        cleanup_container(settings.ETH_NODE["signer"]["name"])

    def down(self):
        self.handle_event("down", "ethnode", self.ps_cmd)
        if self.ps_cmd is None:
            return
        subprocess.check_call(self.ps_cmd, cwd=BASE_DIR)

    def path_abs(self, *path):
        if len(path) == 0:
            return BASE_DIR
        return os.path.join(BASE_DIR, *path)

    def path_signer(self, *path):
        return self.path_abs("signer", *path)

    def path_execution(self, *path):
        return self.path_abs("execution", *path)

    def path_consensus(self, *path):
        return self.path_abs("consensus", *path)

    def handle_error(self, service="", e=Exception()):
        if isinstance(e, KeyboardInterrupt):
            LOGGER.error(
                "PROCESS STOP - %s  %s\n%s",
                service.upper(),
                e,
                LOG_SEPARATOR,
            )
        elif isinstance(e, subprocess.CalledProcessError):
            LOGGER.error(
                "PROCESS ERROR - %s  %s\n%s%s",
                service.upper(),
                e,
                e.output,
                LOG_SEPARATOR,
            )
        else:
            raise e

    def handle_event(self, event, name, details=""):
        try:
            LOGGER.warning(
                "PROCESS %s - %s  %s",
                event.upper(),
                name.upper(),
                details,
            )
        except Exception as e:
            LOGGER.error("EVENT not properly handled: %s", e)

    @property
    def wallet_address_eth(self):
        try:
            basename = os.listdir(self.path_signer("data/keystore"))[-1]
            return load_json(self.path_signer("data/keystore", basename))["address"]
        except (IndexError, KeyError) as e:
            LOGGER.error("ACCOUNT NOT FOUND  %s", e)

    @property
    def sha256sum_rules_js(self):
        try:
            with open(self.path_signer("config/rules.js"), "r") as fd:
                return sha256sum(fd.read())
        except FileNotFoundError as e:
            LOGGER.error("ACCOUNT NOT FOUND - rulesets  %s", e)

    def compose(self, selected=[]):
        props = {
            service: {
                **Mapper.service(
                    getattr(self, "client_options_%s" % service),
                ),
                "volumes": getattr(self, "volumes_%s" % service),
            }
            for service in selected
        }
        fragment = {}
        if "signer" in selected:
            fragment["signer"] = self.compose_service(
                {
                    **props["signer"],
                    "depends_on": [],
                    # can only communicate with `execution` service via `*.ipc` bind
                    "ipc": "service:execution",
                    "container_name": settings.ETH_NODE["signer"]["name"],
                    "client": "signer",
                }
            )
        if "consensus" in selected:
            fragment["consensus"] = self.compose_service(
                {
                    **props["consensus"],
                    "depends_on": [],
                    # do not communicate via volume of type bind `*.ipc` file
                    "ipc": None,
                    "container_name": settings.ETH_NODE["consensus"]["name"],
                    "client": "signer",
                }
            )
        if "execution" in selected:
            fragment["execution"] = self.compose_service(
                {
                    **props["execution"],
                    "depends_on": list(
                        filter(lambda i: i in selected, ["signer", "consensus"])
                    ),
                    # can only communicate with `signer` service via `*.ipc` bind
                    "ipc": "service:signer",
                    "container_name": settings.ETH_NODE["execution"]["name"],
                    "client": "signer",
                }
            )

        return {
            "name": Normalizer.label(__name__),
            "services": fragment,
        }

    def compose_service(self, props):
        return {
            "depends_on": props["depends_on"],
            "container_name": Normalizer.label(
                "{module}-{service}".format(
                    module=__name__,
                    service=props["container_name"],
                ),
            ),
            "image": settings.ETH_NODE[props["client"]]["image"],
            "entrypoint": settings.ETH_NODE[props["client"]]["entrypoint"][0],
            "tty": props["tty"],
            "working_dir": "/app",
            "command": [
                *settings.ETH_NODE[props["client"]]["entrypoint"][1:],
                settings.ETH_NODE[props["client"]]["bin"],
                " ".join(props["cmd"]),
            ],
            # ensure that communication channels are isolated from other containers
            "ipc": props["ipc"],
            # inter-service communition
            "expose": [
                "%s/%s"
                % (
                    p["target"],
                    p["protocol"],
                )
                for p in props["ports"]
            ],
            # host machine - container communication
            "ports": props["ports"],
            "volumes": props["volumes"],
        }

    @property
    def client_options_execution(self):
        try:
            if not os.path.isdir(self.path_consensus()):
                os.makedirs(self.path_consensus())

            ports = [
                ("--http.port", self.options["http.port"]),
                ("--ws.port", self.options["ws.port"]),
                ("--authrpc.port", self.options["authrpc.port"]),
            ]
            cmd = [
                ("--authrpc.addr", self.options["authrpc.addr"]),
                ("--authrpc.vhosts", self.options["authrpc.vhosts"]),
                ("--signer", self.options["signer"]),
                (
                    ("--ipcdisable", True)
                    if settings.ETH_NODE["execution"]["api"]["ipc"]["ipcdisable"]
                    else (
                        "--ipcpath",
                        settings.ETH_NODE["execution"]["api"]["ipc"]["ipcpath"]
                        or "/root/.ethereum/geth/geth.ipc",
                    )
                ),
                ("--http", "http" in self.options),
                ("--ws", "ws" in self.options),
            ]

            # Conditional
            required = {
                "http": "http" in self.options,
                "ws": "ws" in self.options,
            }
            if required["http"]:
                cmd.extend(
                    [
                        ("--http.addr", self.options["http.addr"]),
                        ("--http.api", self.options["http.api"]),
                        ("--http.corsdomain", self.options["http.corsdomain"]),
                    ]
                )
            if required["ws"]:
                cmd.extend(
                    [
                        ("--ws.addr", self.options["ws.addr"]),
                        ("--ws.api", self.options["ws.api"]),
                        ("--ws.origins", self.options["ws.origins"]),
                    ]
                )

            return {
                "tty": self.options["tty"],
                **Mapper.client_options(ports=ports, cmd=cmd),
            }
        except Exception as e:
            self.handle_error("execution config", e)

    @property
    def volumes_execution(self):
        return [
            {
                "type": "volume",
                "source": self.path_execution(),
                "target": "/root",
            },
            {
                "type": "bind",
                "source": self.path_execution(".ethereum/geth/geth.ipc"),
                "target": "/root/.ethereum/geth/geth.ipc",
                "bind": {
                    "selinux":
                    # shared only with `signer`, related to `ipc` docker property
                    "z"
                },
            },
        ]

    @property
    def client_options_signer(self):
        try:
            # Mandatory
            ports = []
            cmd = [
                ("--chainid", CHAIN_ID),
                ("--nousb", "nousb" in settings.ETH_NODE["signer"]),
                ("--lightkdf", "lightkdf" in settings.ETH_NODE["signer"]),
                (
                    ("--ipcdisable", True)
                    if settings.ETH_NODE["signer"]["api"]["ipc"]["ipcdisable"]
                    else (
                        "--ipcpath",
                        settings.ETH_NODE["signer"]["api"]["ipc"]["ipcpath"]
                        or "/app/clef/clef.ipc",
                    )
                ),
                # ("--pcscdpath", "/run/pcscd/pcscd.comm") # $GETH_PCSCDPATH,
                ("--http", "http" in settings.ETH_NODE["signer"]["api"]),
            ]

            # Conditional
            required = {"http": settings.ETH_NODE["signer"]["api"]["http"]}
            if required["http"]:
                ports.extend(
                    [
                        (
                            "--http.port",
                            settings.ETH_NODE["signer"]["api"]["http"].get(
                                "port", "8550"
                            ),
                        ),
                    ]
                )
                cmd.extend(
                    [
                        (
                            "--http.addr",
                            settings.ETH_NODE["signer"]["api"]["http"].get(
                                "addr", "localhost"
                            ),
                        ),
                        (
                            "--http.vhosts",
                            settings.ETH_NODE["signer"]["api"]["http"].get(
                                "vhosts", "localhost"
                            ),
                        ),
                    ]
                )

            return {
                "tty": self.options["tty"],
                **Mapper.client_options(ports=ports, cmd=cmd),
            }
        except Exception as e:
            self.handle_error("signer config", e)

    @property
    def volumes_signer(self):
        return [
            {
                "type": "volume",
                "source": self.path_signer("config/rules.js"),
                "target": "/app/config",
                # ensure integrity
                "read_only": True,
                "volume": {"nocopy": True},
            },
            {
                "type": "volume",
                "source": self.path_signer("config/4byte.json"),
                "target": "/app/config/4byte.json",
                # ensure integrity
                "read_only": True,
                "volume": {"nocopy": True},
            },
            {
                "type": "volume",
                "source": self.path_signer("data"),
                "target": "/app/data",
            },
            {
                "type": "tmpfs",
                "source": self.path_signer("tmp/stdin"),
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
                "source": self.path_signer("tmp/stdout"),
                "target": "/tmp/stdout",
                "tmpfs": {
                    "size": "1gb",
                    # restricted deletion, owner writable
                    "mode": 1200,
                },
            },
            {
                "type": "bind",
                "source": self.path_signer("clef/clef.ipc"),
                "target": "/app/clef/clef.ipc",
                "bind": {
                    "selinux":
                    # shared only with `execution`, related to `ipc` docker property
                    "z"
                },
            },
        ]

    @property
    def client_options_consensus(self):
        # TODO
        return {
            "tty": self.options["tty"],
            # **Mapper.client_options(ports=ports, cmd=cmd),
        }

    @property
    def volumes_consensus(self):
        return [
            # TODO
        ]
