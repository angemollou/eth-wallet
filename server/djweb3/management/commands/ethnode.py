import os
import subprocess
import shutil
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from djweb3.utils import (
    dump_json,
    dump_yaml,
)
from djweb3.utils.event import Logger
from djweb3.utils.mapper import Mapper
from djweb3.utils.cli.signer import Signer
from djweb3.utils.cli.execution import Execution
from djweb3.utils.validator import Validator
from djweb3.utils.normalizer import Normalizer
from djweb3.utils.path import Path

Path = Path(str(settings.ETH_NODE["output"]["container"]))


NETWORKS = settings.ETH_NODE["signer"]["chain_id"]
CHAIN_ID = next(filter(lambda k: NETWORKS[k], NETWORKS))


class Command(BaseCommand):
    help = "Run a Ethereum node via docker"

    def add_arguments(self, parser):
        # COMMAND/ACTION
        parser.add_argument(
            "-r",
            "--reset",
            action="store_true",
            help="Clean all data",
        )
        parser.add_argument(
            "--start",
            action="store_true",
            help="Start the node",
        )
        parser.add_argument(
            "--generate",
            action="store_true",
            help="Generate docker-compose yml",
        )
        # TODO: Use subparser
        parser.add_argument(
            "--generate.json",
            action="store_true",
            help="Generate docker-compose.json",
        )
        parser.add_argument(
            "--init",
            action="store_true",
            help="Generate files to be able to start",
        )
        parser.add_argument(
            "--up",
            action="store_true",
            help="Start containers",
        )
        parser.add_argument(
            "--down",
            action="store_true",
            help="Stop containers",
        )
        parser.add_argument(
            "-u",
            "--newaccount",
            action="store_true",
            help="Request a new wallet address",
        )
        # OPTIONS
        parser.add_argument(
            "-t",
            "--tty",
            action="store_true",
            help="Enable the TTY of runtime sys",
        )
        parser.add_argument(
            "-w",
            "--password",
            help="A password that is at least 10 characters long",
        )
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

    options = dict()

    def handle(self, *args, **options):
        try:
            self.options = options
            for action in [
                "reset",
                "start",
                "generate",
                "init",
                "up",
                "down",
                "newaccount",
            ]:
                if self.options[action]:
                    getattr(self, action)()

        except Exception as e:
            Logger.error(__name__.split(".")[-1], e)
            self.down()
            raise e

    def reset(self):
        if self.options["reset"]:
            shutil.rmtree(Path.abs(), ignore_errors=True)
            for output in ["json", "yaml"]:
                if os.path.isfile(settings.ETH_NODE["output"]["compose"][output]):
                    os.remove(settings.ETH_NODE["output"]["compose"][output])

    def start(self):
        self.init()
        self.up()

    def generate(self):
        compose_dict = self.compose(["signer", "execution"])
        if self.options["generate.json"]:
            dump_json(
                compose_dict,
                settings.ETH_NODE["output"]["compose"]["json"],
            )
        dump_yaml(
            compose_dict,
            settings.ETH_NODE["output"]["compose"]["yaml"],
        )

    def init(self):
        self.generate()
        # TODO REF/DP: Dependency injection | Builder
        self.signer = Signer(
            path=Path.signer,
            env=settings.ETH_NODE["signer"],
            cmd={
                "entrypoint": self.cmd["run"]["signer"],
                "bin": settings.ETH_NODE["signer"]["bin"],
                "cwd": Path.abs(),
            },
        )
        self.execution = Execution(
            path=Path.execution,
        )

    def up(self):
        subprocess.check_call(self.cmd["up"], cwd=Path.abs())

    def down(self):
        subprocess.check_call(self.cmd["down"], cwd=Path.abs())

    def newaccount(self):
        if Validator.password(self.options["password"]):
            self.signer_newaccount(self.options["password"], self.cmd["run"]["signer"])

            self.signer_setpw(self.options["password"], self.cmd["run"]["signer"])

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
                    "container_name": settings.ETH_NODE["signer"]["name"],
                    "client": "signer",
                    "working_dir": "/app",
                }
            )
        if "consensus" in selected:
            fragment["consensus"] = self.compose_service(
                {
                    **props["consensus"],
                    "depends_on": [],
                    "container_name": settings.ETH_NODE["consensus"]["name"],
                    "client": "consensus",
                    "working_dir": "/app/",
                }
            )
        if "execution" in selected:
            fragment["execution"] = self.compose_service(
                {
                    **props["execution"],
                    "depends_on": list(
                        filter(lambda i: i in selected, ["signer", "consensus"])
                    ),
                    "container_name": settings.ETH_NODE["execution"]["name"],
                    "client": "execution",
                    "working_dir": "/app/",
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
                "{service}".format(
                    service=props["container_name"],
                ),
            ),
            "image": settings.ETH_NODE[props["client"]]["image"],
            "entrypoint": " ".join(settings.ETH_NODE[props["client"]]["entrypoint"]),
            "tty": props["tty"],
            "working_dir": props["working_dir"],
            "command": [
                # *settings.ETH_NODE[props["client"]]["entrypoint"][1:],
                settings.ETH_NODE[props["client"]]["bin"],
                " ".join(props["cmd"]),
            ],
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
            if not os.path.isdir(Path.consensus()):
                os.makedirs(Path.consensus())

            ports = [
                ("--http.port", self.options["http.port"]),
                ("--ws.port", self.options["ws.port"]),
                ("--authrpc.port", self.options["authrpc.port"]),
            ]
            cmd = [
                ("--networkid", CHAIN_ID),
                ("--authrpc.addr", self.options["authrpc.addr"]),
                ("--authrpc.vhosts", self.options["authrpc.vhosts"]),
                ("--signer", self.options["signer"]),
                (
                    ("--ipcdisable", True)
                    if settings.ETH_NODE["execution"]["api"]["ipc"]["ipcdisable"]
                    else (
                        "--ipcpath",
                        settings.ETH_NODE["execution"]["api"]["ipc"]["ipcpath"]
                        or "/app/.ethereum/geth/geth.ipc",
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
            Logger.error("execution config", e)

    @property
    def volumes_execution(self):
        return [
            {
                "type": "bind",
                "source": Path.execution(),
                "target": "/app/",
            },
            {
                "type": "bind",
                "source": Path.execution(".ethereum/geth/"),
                "target": "/app/.ethereum/geth/",
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
            Logger.error("signer config", e)

    @property
    def volumes_signer(self):
        return [
            {
                "type": "bind",
                "source": Path.signer("config/rules.js"),
                "target": "/app/config/rules.js",
                # ensure integrity
                "read_only": True,
            },
            {
                "type": "bind",
                "source": Path.signer("config/4byte.json"),
                "target": "/app/config/4byte.json",
                # ensure integrity
                "read_only": True,
            },
            {
                "type": "bind",
                "source": Path.signer("data"),
                "target": "/app/data/",
            },
            {
                "type": "tmpfs",
                # "source": Path.signer("tmp/stdin"),
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
                # "source": Path.signer("tmp/stdout"),
                "target": "/tmp/stdout",
                "tmpfs": {
                    "size": "1gb",
                    # restricted deletion, owner writable
                    "mode": 1200,
                },
            },
            {
                "type": "bind",
                "source": Path.signer("clef/"),
                "target": "/app/clef/",
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

    @property
    def cmd(self):

        filename = (
            settings.ETH_NODE["output"]["compose"]["yaml"]
            if os.path.isfile(settings.ETH_NODE["output"]["compose"]["yaml"])
            else settings.ETH_NODE["output"]["compose"]["json"]
        )

        return {
            "up": [
                "docker-compose",
                "-f",
                filename,
                "up",
            ],
            "down": [
                "docker-compose",
                "-f",
                filename,
                "down",
            ],
            "run": {
                "signer": [
                    "docker-compose",
                    "-f",
                    filename,
                    "run",
                    "--rm",
                    "signer",
                ]
            },
        }
