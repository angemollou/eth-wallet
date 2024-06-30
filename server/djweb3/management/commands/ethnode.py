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
    signer = None
    execution = None
    consensus = None

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
                "entrypoint": self.cmd["signer"]["run"],
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
            self.signer_newaccount(self.options["password"], self.cmd["signer"]["run"])

            self.signer_setpw(self.options["password"], self.cmd["signer"]["run"])

    def compose(self, selected=[]):
        fragment = {}
        if "signer" in selected:
            fragment["signer"] = self.compose_service(
                {
                    **Mapper.service(
                        Signer.parse_options(
                            {
                                "chainid": CHAIN_ID,
                                "tty": self.options["tty"],
                                **settings.ETH_NODE["signer"],
                            }
                        )
                    ),
                    "volumes": Signer.volumes(Path.signer),
                    "depends_on": [],
                    "container_name": settings.ETH_NODE["signer"]["name"],
                    "client": "signer",
                    "working_dir": "/app",
                }
            )
        if "consensus" in selected:
            fragment["consensus"] = self.compose_service(
                {
                    **Mapper.service(
                        # Consensus.parse_options(
                        #     {
                        #         "chainid": CHAIN_ID,
                        #         "tty": self.options["tty"],
                        #         **settings.ETH_NODE["consensus"],
                        #     }
                        # )
                    ),
                    # "volumes": Consensus.volumes(Path.signer),
                    "depends_on": [],
                    "container_name": settings.ETH_NODE["consensus"]["name"],
                    "client": "consensus",
                    "working_dir": "/app/",
                }
            )
        if "execution" in selected:
            fragment["execution"] = self.compose_service(
                {
                    **Mapper.service(
                        Execution.parse_options(
                            {
                                "chainid": CHAIN_ID,
                                # "sepolia": settings.DEBUG,
                                "ipcdisable": settings.ETH_NODE["execution"]["api"][
                                    "ipc"
                                ]["ipcdisable"],
                                "ipcpath": settings.ETH_NODE["execution"]["api"]["ipc"][
                                    "ipcpath"
                                ],
                                **self.options,
                            }
                        )
                    ),
                    "volumes": Execution.volumes(Path.execution),
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
    def cmd(self):

        filename = (
            settings.ETH_NODE["output"]["compose"]["yaml"]
            if os.path.isfile(settings.ETH_NODE["output"]["compose"]["yaml"])
            else settings.ETH_NODE["output"]["compose"]["json"]
        )

        result = {
            service: {
                "up": ["docker-compose", "-f", filename, "up", service],
                "down": ["docker-compose", "-f", filename, "down", service],
                "run": ["docker-compose", "-f", filename, "run", "--rm", service],
            }
            for service in ["signer", "execution", "consensus"]
        }
        result["up"] = ["docker-compose", "-f", filename, "up"]
        result["down"] = ["docker-compose", "-f", filename, "down"]

        return result
