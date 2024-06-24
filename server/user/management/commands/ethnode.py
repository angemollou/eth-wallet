import os
import subprocess
import shutil
from time import sleep
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import logging


TERMINAL_SIZE = shutil.get_terminal_size()
LOG_SEPARATOR = "\n{}\n".format(
    "-" * int(TERMINAL_SIZE[0] * 80 / 100)
    if TERMINAL_SIZE[0] > 80
    else TERMINAL_SIZE[0]
)
logging.basicConfig(format="[%(asctime)s]  %(name)s  %(message)s")
logger = logging.getLogger(__name__)
BASE_DIR = settings.ETH_NODE["BASE_DIR"]
CHAIN_ID = (
    11155111  # Sepolia testnet
    if settings.DEBUG
    else settings.ETH_NODE["SIGNER"]["CHAIN_ID"]
)


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


class Command(BaseCommand):
    help = "Run a Ethereum node via docker"

    def add_arguments(self, parser):
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
        parser.add_argument(
            "-t",
            "--tty",
            action="store_true",
            help="Enable the TTY of runtime sys",
        )
        # CONSENSUS options
        parser.add_argument(
            "--http",
            action="store_true",
            help="Enable the HTTP-RPC server",
            default="HTTP" in settings.ETH_NODE["EXECUTION"],
        )
        parser.add_argument(
            "--http.addr",
            help="HTTP-RPC server listening interface",
            default=(
                settings.ETH_NODE["EXECUTION"]["HTTP"].get("ADDR", "localhost")
                if "HTTP" in settings.ETH_NODE["EXECUTION"]
                else None
            ),
        )
        parser.add_argument(
            "--http.port",
            help="HTTP-RPC server listening port",
            default=(
                str(settings.ETH_NODE["EXECUTION"]["HTTP"].get("PORT", 8545))
                if "HTTP" in settings.ETH_NODE["EXECUTION"]
                else None
            ),
        )
        parser.add_argument(
            "--http.api",
            help="Namespaces accessible over the HTTP-RPC interface",
            nargs="+",
            default=(
                settings.ETH_NODE["EXECUTION"]["HTTP"].get("API", "eth,net,web3")
                if "HTTP" in settings.ETH_NODE["EXECUTION"]
                else None
            ),
        )
        parser.add_argument(
            "--http.corsdomain",
            help="Comma separated list of domains from which to accept cross origin requests (browser enforced)",
            nargs="+",
            default=(
                settings.ETH_NODE["EXECUTION"]["HTTP"].get("CORSDOMAIN")
                if "HTTP" in settings.ETH_NODE["EXECUTION"]
                else None
            ),
        )
        parser.add_argument(
            "--ws",
            action="store_true",
            help="Enable the WS-RPC server",
            default="WS" in settings.ETH_NODE["EXECUTION"],
        )
        parser.add_argument(
            "--ws.addr",
            help="WS-RPC server listening interface",
            default=(
                settings.ETH_NODE["EXECUTION"]["WS"].get("ADDR", "localhost")
                if "WS" in settings.ETH_NODE["EXECUTION"]
                else None
            ),
        )
        parser.add_argument(
            "--ws.port",
            help="WS-RPC server listening port",
            default=(
                str(settings.ETH_NODE["EXECUTION"]["WS"].get("PORT", 3334))
                if "WS" in settings.ETH_NODE["EXECUTION"]
                else None
            ),
        )
        parser.add_argument(
            "--ws.api",
            help="Namespaces accessible over the WS-RPC interface",
            nargs="+",
            default=(
                settings.ETH_NODE["EXECUTION"]["WS"].get("API", "eth,net,web3")
                if "WS" in settings.ETH_NODE["EXECUTION"]
                else None
            ),
        )
        parser.add_argument(
            "--ws.origins",
            help="Comma separated list of domains from which to accept WebSocket requests",
            nargs="+",
            default=(
                settings.ETH_NODE["EXECUTION"]["WS"].get("ORIGINS", "localhost")
                if "WS" in settings.ETH_NODE["EXECUTION"]
                else None
            ),
        )
        parser.add_argument(
            "--ipcdisable",
            action="store_true",
            help="Disable the IPC-RPC server",
            default="IPC" not in settings.ETH_NODE["EXECUTION"],
        )
        parser.add_argument(
            "--authrpc.addr",
            help="AUTH-RPC server listening interface",
            default=settings.ETH_NODE["EXECUTION"]["AUTH"].get("ADDR", "localhost"),
        )
        parser.add_argument(
            "--authrpc.port",
            help="AUTH-RPC server listening port",
            default=str(settings.ETH_NODE["EXECUTION"]["AUTH"].get("PORT", 8551)),
        )
        parser.add_argument(
            "--authrpc.vhosts",
            help="Comma separated list of domains from which to accept AUTH requests",
            nargs="+",
            default=settings.ETH_NODE["EXECUTION"]["AUTH"].get("ORIGINS", "localhost"),
        )

    ps = dict()
    is_newaccount_required = False

    def handle(self, *args, **options):
        try:
            if options["reset"]:
                shutil.rmtree(BASE_DIR, ignore_errors=True)

            cmd = self.start_signer(*args, **options)
            self.handle_event("start", "signer", cmd)
            self.ps["signer"] = subprocess.Popen(cmd, cwd=BASE_DIR)
            self.wait(self.signer_path("data/keystore"), log=True)

            cmd = self.start_execution(*args, **options)
            self.handle_event("start", "execution", cmd)
            self.ps["execution"] = subprocess.Popen(cmd, cwd=BASE_DIR)
            self.wait(self.execution_path(".ethereum/geth/jwtsecret"), log=True)

            # Start all dependencies then hold on until Execution client exits
            self.ps["execution"].wait()

        except Exception as e:
            logger.error("ERROR was not handled  %s", e)
            raise e
        finally:
            self.cleanup()

    def start_execution(self, *_, **options):
        try:
            if not os.path.isdir(self.execution_path()):
                os.makedirs(self.execution_path())
            consensus_options = self.sync_consensus(self, *_, **options)
            cmd = [
                "docker",
                "run",
                # tty enable docker logs coloring
                *(["-t"] if options["tty"] else []),
                "--name",
                settings.ETH_NODE["EXECUTION"]["NAME"],
                "--rm",
                "-p",
                "30303:%d" % (settings.ETH_NODE["EXECUTION"]["P2P"]["ETH"] or 30303),
                *consensus_options["ports"],
                "-v",
                "%s:/root" % self.execution_path(),
                # Constraint: must be generated by SIGNER
                "-v",
                "%s:/root/.ethereum/keystore:ro" % self.signer_path("data/keystore"),
                # Constraint: must be created inside EXECUTION container
                # "-v",
                # "%s:/root/.ethereum/geth/geth.ipc"
                # % self.execution_path(".ethereum/geth/geth.ipc"),
                settings.ETH_NODE["EXECUTION"]["IMAGE"],
                "--keystore",
                "/root/.ethereum/keystore",
                # CONCENCUS
                # Constraint: must be created inside EXECUTION container for CONSENSUS
                "--authrpc.jwtsecret",
                "/root/.ethereum/geth/jwtsecret",
                *consensus_options["entrypoint_args"],
            ]
            print(cmd)
            return cmd
        except Exception as e:
            self.handle_error("execution", e)

    def start_signer(self, *_, **options):
        try:
            cmd = self.init_signer(self, *_, **options)
            cmd[-1] = "run"
            return cmd
        except Exception as e:
            self.handle_error("signer", e)

    def sync_consensus(self, *_, **options):
        try:
            if not os.path.isdir(self.consensus_path()):
                os.makedirs(self.consensus_path())

            ports = [
                ("--http.port", options["http.port"]),
                ("--ws.port", options["ws.port"]),
                ("--authrpc.port", options["authrpc.port"]),
            ]
            others = [
                ("--http", options["http"]),
                ("--http.addr", options["http.addr"]),
                ("--http.api", options["http.api"]),
                ("--http.corsdomain", options["http.corsdomain"]),
                ("--ws", options["ws"]),
                ("--ws.addr", options["ws.addr"]),
                ("--ws.api", options["ws.api"]),
                ("--ws.origins", options["ws.origins"]),
                ("--ipcdisable", options["ipcdisable"]),
                *(
                    []
                    if options["ipcdisable"]
                    else [("--ipcpath", "/root/.ethereum/geth/geth.ipc")]
                ),
                ("--authrpc.addr", options["authrpc.addr"]),
                ("--authrpc.vhosts", options["authrpc.vhosts"]),
                # (--pcscdpath, "/run/pcscd/pcscd.comm") # $GETH_PCSCDPATH
            ]
            ports_map = []
            for pair in map(lambda p: ("-p", "%s:%s" % (p[1], p[1])), ports):
                try:
                    int(pair[0])
                except ValueError as e:
                    continue
                ports_map.extend(pair)
            others_map = []
            for opt in [*ports, *others]:
                name, value = opt

                if value in ("", None, False, 0):
                    continue
                elif value in (True, 1):
                    others_map.append(name)
                    continue

                others_map.extend((name, value))

            return {"ports": ports_map, "entrypoint_args": others_map}
        except Exception as e:
            self.handle_error("execution", e)

    def init_signer(self, *_, **options):
        try:
            self.is_newaccount_required = options["reset"] or options["newaccount"]
            if options["newaccount"]:
                shutil.rmtree(self.signer_path(), ignore_errors=True)
            if not os.path.isdir(self.signer_path()):
                if options["password"]:
                    if len(options["password"]) < 10:
                        raise ValueError(
                            "-w, --password must be at least 10 characters"
                        )
                    # CONSTRAINT: password file must be stored in "$DATA" for initialization
                    touch(self.signer_path("data/password"), options["password"])
                    self.is_newaccount_required = True
                else:
                    raise ValueError("-w, --password is required")
                # CONSTRAINT: --keystore path must identical to "$DATA"/keystore for initialization
                os.makedirs(self.signer_path("data/keystore"))
                touch(self.signer_path("tmp/stdin"))
                touch(self.signer_path("tmp/stdout"))
                # touch(self.signer_path("run/pcscd/pcscd.comm"))

            cmd = [
                "docker",
                "run",
                # tty enable docker logs coloring
                *(["-t"] if options["tty"] else []),
                "--name",
                settings.ETH_NODE["SIGNER"]["NAME"],
                "--rm",
                "-p",
                "8550:%s" % (settings.ETH_NODE["SIGNER"]["HTTP"]["PORT"] or 8550),
                "-e",
                "DATA=/app/data",  # --configdir=$DATA
                "-e",
                "CLEF_CHAINID=%d" % CHAIN_ID,  # --chainid=$CLEF_CHAINID
                "-v",
                "%s:/app/data" % self.signer_path("data"),
                "-v",
                "%s:/tmp" % self.signer_path("tmp"),
                # OPTIONAL: for SmartCard (character device file)
                # "-v",
                # "%s:/run/pcscd/pcscd.comm" % self.signer_path("run/pcscd/pcscd.comm"),
                settings.ETH_NODE["SIGNER"]["IMAGE"],
                "init",
            ]

            if self.is_newaccount_required:
                subprocess.check_call(cmd, cwd=BASE_DIR)
                self.cleanup_container(settings.ETH_NODE["SIGNER"]["NAME"])

            return cmd
        except Exception as e:
            self.handle_error("new account", e)

    def cleanup_container(self, name):
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
                    cwd=BASE_DIR,
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
                    cwd=BASE_DIR,
                    stderr=subprocess.DEVNULL,
                )
                subprocess.call(
                    [
                        "docker",
                        "container",
                        "rm",
                        name,
                    ],
                    cwd=BASE_DIR,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            logger.warning("Clean up container - Error not handled  %s", e)

    def wait(self, path, log=False):
        logger.warning("WAIT  %s", path)
        keys = []
        if os.path.isfile(path):
            keys = [path]
        elif os.path.isdir(path):
            keys = list(
                map(
                    lambda item: item.path,
                    os.scandir(path),
                )
            )
        if len(keys) == 0:
            sleep(settings.ETH_NODE["WAIT_THROTTLE_TIME"])
            self.wait(path)
            return False
        if log:
            logger.warning("WAIT LOG  %s%s\n", keys[-1], LOG_SEPARATOR)
        return keys[-1]

    def cleanup(self):
        logger.warning("CLEANUP")
        if self.ps.get("signer"):
            self.handle_event("exit", "signer", self.ps["signer"])
        if self.ps.get("execution"):
            self.handle_event("exit", "execution", self.ps["execution"])

        self.cleanup_container(settings.ETH_NODE["SIGNER"]["NAME"])
        self.cleanup_container(settings.ETH_NODE["EXECUTION"]["NAME"])

    def abs_path(self, *path):
        if len(path) == 0:
            return BASE_DIR
        return os.path.join(BASE_DIR, *path)

    def signer_path(self, *path):
        return self.abs_path("signer", *path)

    def execution_path(self, *path):
        return self.abs_path("execution", *path)

    def consensus_path(self, *path):
        return self.abs_path("consensus", *path)

    def handle_error(self, service="", e=Exception()):
        if isinstance(e, KeyboardInterrupt):
            logger.error(
                "PROCESS STOP - %s  %s\n%s",
                service.upper(),
                e,
                LOG_SEPARATOR,
            )
        elif isinstance(e, subprocess.CalledProcessError):
            logger.error(
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
            logger.warning(
                "PROCESS %s - %s  %s",
                event.upper(),
                name.upper(),
                details,
            )
        except Exception as e:
            logger.error("EVENT not properly handled: %s", e)
