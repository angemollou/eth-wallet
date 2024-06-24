import os
import subprocess
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from user.utils.cli import (
    wait,
    logger,
    set_on,
    map_options,
    cleanup_container,
    validate_password,
    on,
    touch,
    LOG_SEPARATOR,
    load_json,
    sha256sum,
)

BASE_DIR = settings.ETH_NODE["BASE_DIR"]
CHAIN_ID = (
    11155111  # Sepolia testnet
    if settings.DEBUG
    else settings.ETH_NODE["SIGNER"]["CHAIN_ID"]
)


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
        parser.add_argument(
            "--signer",
            help="<addr>:<port> of the tool for signing transactions and data",
            default=settings.ETH_NODE["EXECUTION"].get("SIGNER", "localhost:8550"),
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

            cmd = self.start_execution(*args, **options)
            self.handle_event("start", "execution", cmd)
            self.ps["execution"] = subprocess.Popen(cmd, cwd=BASE_DIR)
            wait(
                self.path_execution(".ethereum/geth/jwtsecret"),
                True,
                settings.ETH_NODE["WAIT_THROTTLE_TIME"],
            )

            # Start all dependencies then hold on until Execution client exits
            self.ps["execution"].wait()

        except Exception as e:
            logger.error("ERROR was not handled  %s", e)
            raise e
        finally:
            self.cleanup()

    def start_execution(self, *_, **options):
        try:
            if not os.path.isdir(self.path_execution()):
                os.makedirs(self.path_execution())
            clients_options = self.config_execution(self, *_, **options)
            cmd = [
                "docker",
                "run",
                # tty enable docker logs coloring
                *set_on("-t", options["tty"]),
                "--name",
                settings.ETH_NODE["EXECUTION"]["NAME"],
                "--rm",
                "-p",
                "30303:%d" % (settings.ETH_NODE["EXECUTION"]["P2P"]["ETH"] or 30303),
                *clients_options["ports"],
                "-v",
                "%s:/root" % self.path_execution(),
                # Constraint: must be generated by SIGNER
                "-v",
                "%s:/root/.ethereum/keystore:ro" % self.path_signer("data/keystore"),
                # Constraint: must be created inside EXECUTION container
                # "-v",
                # "%s:/root/.ethereum/geth/geth.ipc"
                # % self.execution_path(".ethereum/geth/geth.ipc"),
                *clients_options["volumes"],
                settings.ETH_NODE["EXECUTION"]["IMAGE"],
                "--keystore",
                "/root/.ethereum/keystore",
                # Constraint: must be created inside EXECUTION container for CONSENSUS
                "--authrpc.jwtsecret",
                "/root/.ethereum/geth/jwtsecret",
                *clients_options["entrypoint"],
            ]
            print(cmd)
            return cmd
        except Exception as e:
            self.handle_error("execution", e)

    def config_execution(self, *_, **options):
        try:
            if not os.path.isdir(self.path_consensus()):
                os.makedirs(self.path_consensus())

            ports = [
                ("--http.port", options["http.port"]),
                ("--ws.port", options["ws.port"]),
                ("--authrpc.port", options["authrpc.port"]),
            ]
            entrypoint = [
                ("--http", options["http"]),
                ("--http.addr", options["http.addr"]),
                ("--http.api", options["http.api"]),
                ("--http.corsdomain", options["http.corsdomain"]),
                ("--ws", options["ws"]),
                ("--ws.addr", options["ws.addr"]),
                ("--ws.api", options["ws.api"]),
                ("--ws.origins", options["ws.origins"]),
                (
                    ("--ipcdisable", options["ipcdisable"])
                    if options["ipcdisable"]
                    else ("--ipcpath", "/root/.ethereum/geth/geth.ipc")
                ),
                ("--authrpc.addr", options["authrpc.addr"]),
                ("--authrpc.vhosts", options["authrpc.vhosts"]),
                # SIGNER
                # (--pcscdpath, "/run/pcscd/pcscd.comm") # $GETH_PCSCDPATH,
                ("--signer", options["signer"]),
            ]
            volumes = [
                *set_on(
                    (self.path_signer("clef/clef.ipc"), "/root/clef/clef.ipc"),
                    os.path.isfile(options["signer"])
                    and "IPC" in settings.ETH_NODE["SIGNER"],
                )
            ]
            return map_options(ports=ports, entrypoint=entrypoint, volumes=volumes)
        except Exception as e:
            self.handle_error("execution config", e)

    def start_signer(self, *_, **options):
        try:
            clients_options = self.config_signer(self, *_, **options)

            if not self.init_signer(self, *_, **options):
                return

            cmd = [
                "docker",
                "run",
                # tty enable docker logs coloring
                *set_on("-t", options["tty"]),
                "--name",
                settings.ETH_NODE["SIGNER"]["NAME"],
                "--rm",
                *clients_options["ports"],
                "-v",
                "%s:/app/data" % self.path_signer("data"),
                "-v",
                "%s:/tmp" % self.path_signer("tmp"),
                # OPTIONAL: for SmartCard (character device file)
                # "-v",
                # "%s:/run/pcscd/pcscd.comm" % self.signer_path("run/pcscd/pcscd.comm"),
                "-v",
                "%s:/app/config/rules.js" % self.path_signer("config/rules.js"),
                "-v",
                "%s:/app/config/4byte.json" % self.path_signer("config/4byte.json"),
                "-v",
                "%s:/app/clef" % self.path_signer("clef"),
                "--entrypoint",
                "bash",
                settings.ETH_NODE["SIGNER"]["IMAGE"],
                "-c",
                " ".join(
                    [
                        "/usr/local/bin/bee-clef",
                        "--stdio-ui",
                        "--configdir",
                        "/app/data",
                        "--keystore",
                        "/app/data/keystore",
                        "--rules",
                        "/app/config/rules.js",
                        "--4bytedb-custom",
                        "/app/config/4byte.json",
                        "--pcscdpath",
                        "''",
                        "--auditlog",
                        "''",
                        "--loglevel",
                        "3",
                        *clients_options["entrypoint"],
                        "<",
                        "/tmp/stdin",
                        "|",
                        "tee",
                        "/tmp/stdout",
                    ]
                ),
            ]
            return cmd
        except Exception as e:
            self.handle_error("signer", e)

    def init_signer(self, *_, **options):
        try:
            cmd_init = [
                "docker",
                "run",
                # tty enable docker logs coloring
                *set_on("-t", options["tty"]),
                "--name",
                settings.ETH_NODE["SIGNER"]["NAME"],
                "--rm",
                "-v",
                "%s:/app/data" % self.path_signer("data"),
                "-v",
                "%s:/tmp" % self.path_signer("tmp"),
                # OPTIONAL: for SmartCard (character device file)
                # "-v",
                # "%s:/run/pcscd/pcscd.comm" % self.signer_path("run/pcscd/pcscd.comm"),
                "--entrypoint",
                "bash",
                settings.ETH_NODE["SIGNER"]["IMAGE"],
                "-c",
            ]

            self.signer_seed(cmd_init)

            if (
                len(os.listdir(self.path_signer("data/keystore"))) == 0
                or options["password"]
            ):
                self.signer_newaccount(options["password"], cmd_init)

                self.signer_setpw(options["password"], cmd_init)

            self.signer_attest(settings.ETH_NODE["SIGNER"]["MASTER_PASSWORD"], cmd_init)

            return True
        except Exception as e:
            self.handle_error("new account", e)

    def signer_attest(self, master_pwd, cmd_init):
        # Attest to rulesets integrity
        if os.path.isfile(self.path_signer("config/rules.js")):
            subprocess.check_call(
                [
                    *cmd_init,
                    " ".join(
                        [
                            "/usr/local/bin/bee-clef",
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
            cleanup_container(settings.ETH_NODE["SIGNER"]["NAME"])

    def signer_setpw(self, user_pwd, cmd_init):
        # Store a credential for the generated keystore file
        if validate_password(user_pwd):
            subprocess.check_call(
                [
                    *cmd_init,
                    " ".join(
                        [
                            "/usr/local/bin/bee-clef",
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
                                master=settings.ETH_NODE["SIGNER"]["MASTER_PASSWORD"],
                            ),
                        ]
                    ),
                ],
                cwd=BASE_DIR,
            )
            cleanup_container(settings.ETH_NODE["SIGNER"]["NAME"])

    def signer_newaccount(self, user_pwd, cmd_init):
        # Create account and Generate keystore (with the account password)
        if validate_password(user_pwd):
            subprocess.check_call(
                [
                    *cmd_init,
                    " ".join(
                        [
                            "/usr/local/bin/bee-clef",
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
            cleanup_container(settings.ETH_NODE["SIGNER"]["NAME"])

    @on(validate_password(settings.ETH_NODE["SIGNER"]["MASTER_PASSWORD"]))
    def signer_seed(self, cmd_init):
        # Generate master seed to be able to store credentials
        subprocess.check_call(
            [
                *cmd_init,
                " ".join(
                    [
                        "/usr/local/bin/bee-clef",
                        "--configdir",
                        "/app/data",
                        "--stdio-ui",
                        "init",
                        ">/dev/null 2>&1 << EOF\n%sEOF"
                        % ("{0}\n" * 2).format(
                            settings.ETH_NODE["SIGNER"]["MASTER_PASSWORD"]
                        ),
                    ]
                ),
            ],
            cwd=BASE_DIR,
        )
        cleanup_container(settings.ETH_NODE["SIGNER"]["NAME"])

    def config_signer(self, *_, **options):
        try:
            if options["reset"] or (
                options["newaccount"]
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
                    settings.ETH_NODE["SIGNER"]["RULES_JS"],
                )
                touch(
                    self.path_signer("config/4byte.json"),
                    settings.ETH_NODE["SIGNER"]["4BYTEDB_CUSTOM"],
                )
                if "IPC" in settings.ETH_NODE["SIGNER"]:
                    os.makedirs(self.path_signer("clef"))

            ports = []
            entrypoint = [
                ("--chainid", str(CHAIN_ID)),
                *set_on(("--nousb", True), "NOUSB" in settings.ETH_NODE["SIGNER"]),
                *set_on(
                    ("--lightkdf", True), "LIGHTKDF" in settings.ETH_NODE["SIGNER"]
                ),
                # (--pcscdpath, "/run/pcscd/pcscd.comm") # $GETH_PCSCDPATH,
                *set_on(
                    ("--ipcpath", "/app/clef/clef.ipc"),
                    "IPC" in settings.ETH_NODE["SIGNER"],
                    ("--ipcdisable", "IPC" not in settings.ETH_NODE["SIGNER"]),
                ),
            ]
            if "HTTP" in settings.ETH_NODE["SIGNER"]:
                entrypoint.extend(
                    [
                        ("--http", "HTTP" in settings.ETH_NODE["SIGNER"]),
                        (
                            "--http.addr",
                            settings.ETH_NODE["SIGNER"]["HTTP"].get(
                                "ADDR", "localhost"
                            ),
                        ),
                        (
                            "--http.vhosts",
                            settings.ETH_NODE["SIGNER"]["HTTP"].get(
                                "VHOSTS", "localhost"
                            ),
                        ),
                        (
                            "--http.port",
                            settings.ETH_NODE["SIGNER"]["HTTP"].get("PORT", 8550),
                        ),
                    ]
                )
            return map_options(ports=ports, entrypoint=entrypoint)
        except Exception as e:
            self.handle_error("signer config", e)

    def cleanup(self):
        logger.warning("CLEANUP")
        if self.ps.get("signer"):
            self.handle_event("exit", "signer", self.ps["signer"])
        if self.ps.get("execution"):
            self.handle_event("exit", "execution", self.ps["execution"])

        cleanup_container(settings.ETH_NODE["SIGNER"]["NAME"])
        cleanup_container(settings.ETH_NODE["EXECUTION"]["NAME"])

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

    @property
    def wallet_address_eth(self):
        try:
            basename = os.listdir(self.path_signer("data/keystore"))[-1]
            return load_json(self.path_signer("data/keystore", basename))["address"]
        except (IndexError, KeyError) as e:
            logger.error("ACCOUNT NOT FOUND  %s", e)

    @property
    def sha256sum_rules_js(self):
        try:
            with open(self.path_signer("config/rules.js"), "r") as fd:
                return sha256sum(fd.read())
        except FileNotFoundError as e:
            logger.error("ACCOUNT NOT FOUND - rulesets  %s", e)
