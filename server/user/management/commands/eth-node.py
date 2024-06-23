import os
import subprocess
import shutil
from time import sleep
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

BASE_DIR = settings.ETH_NODE["BASE_DIR"]
CHAIN_ID = str(
    11155111  # Sepolia testnet
    if settings.DEBUG
    else settings.ETH_NODE["CONCENSUS"]["CHAIN_ID"]
)


def touch(path):
    os.makedirs(os.path.dirname(path))
    open(path, "a").close()


class Command(BaseCommand):
    help = "Run a Geth Ethereum node via docker"

    gateway_ps = None
    consensus_ps = None

    def add_arguments(self, parser):
        parser.add_argument(
            "-u",
            "--newaccount",
            action="store_true",
            help="Request a new wallet address?",
        )  # on/off flag
        parser.add_argument(
            "-w",
            "--password",
            help="A password that is at least 10 characters long",
            default="1234567890" if settings.DEBUG else None,
            type=str,
        )
        parser.add_argument(
            "-d", "--detach", action="store_true", help="Run containers in background?"
        )  # on/off flag
        parser.add_argument(
            "-r", "--reset", action="store_true", help="Clean volumes?"
        )  # on/off flag

    def handle(self, *args, **options):
        try:
            if options["reset"]:
                shutil.rmtree(BASE_DIR, ignore_errors=True)
            self.start_gateway(*args, **options)
        except Exception as e:
            # TODO: handle e
            raise e
            print(e)
        finally:
            self.cleanup()

    def start_gateway(self, *args, **options):
        try:
            if not os.path.isdir(os.path.join(BASE_DIR, "gateway")):
                os.makedirs(os.path.join(BASE_DIR, "gateway"))

            self.consensus_ps = self.start_concensus(*args, **options)
            if isinstance(self.consensus_ps, subprocess.Popen):
                # TODO: stop if concensus_ps failed to start
                if self.consensus_ps.poll() is not None:
                    return
                self.wait_concensus()
            cmd = [
                "docker",
                "run",
                *(["-d"] if options["detach"] else []),
                "-t",
                "--name",
                "ethnode-gateway",
                "--rm",
                "-p",
                "8545:%d" % (settings.ETH_NODE["GATEWAY"]["HTTP"] or 8545),
                "-p",
                "30303:%d" % (settings.ETH_NODE["GATEWAY"]["TCP"] or 30303),
                "-v",
                os.path.join(BASE_DIR, "gateway/:/root/"),
                "-v",
                os.path.join(BASE_DIR, "consensus/keystore:/keystore:ro"),
                "ethereum/client-go",
                "--http.addr",
                "0.0.0.0",
                "--ipcpath",
                "/root/.ethereum/geth/geth.ipc",
                "--keystore",
                "/keystore",
            ]
            print("ETH Node - Gateway client started!\n", cmd)
            self.gateway_ps = subprocess.run(cmd, cwd=BASE_DIR)
            self.consensus_ps.wait()
        except Exception as e:
            # TODO: handle Error
            raise e
            print(e)

    def start_concensus(self, *args, **options):
        try:
            is_newaccount_required = options["reset"] or options["newaccount"]
            if options["newaccount"]:
                shutil.rmtree(os.path.join(BASE_DIR, "consensus"), ignore_errors=True)
            if not os.path.isdir(os.path.join(BASE_DIR, "consensus")):
                os.makedirs(os.path.join(BASE_DIR, "consensus", "keystore"))
                touch(os.path.join(BASE_DIR, "consensus", "run", "pcscd", "pcscd.comm"))
                if options["password"]:
                    with open(
                        os.path.join(BASE_DIR, "consensus", "password"), "w"
                    ) as fd:
                        fd.write(options["password"])
                    is_newaccount_required = True
                else:
                    raise ValueError("-w, --password is required")

            cmd = [
                "docker",
                "run",
                "-t",
                *(["-d"] if options["detach"] else []),
                "--name",
                "ethnode-concensus",
                "--rm",
                "-p",
                "8550:%s" % (settings.ETH_NODE["CONCENSUS"]["HTTP"] or 8550),
                "-v",
                os.path.join(BASE_DIR, "consensus:/app/data"),
                "-v",
                os.path.join(BASE_DIR, "consensus/password:/app/data/password:ro"),
                "-v",
                os.path.join(
                    BASE_DIR, "gateway/.ethereum/geth/geth.ipc:/app/geth/geth.ipc:rw"
                ),
                "ethersphere/clef",
                "init" if is_newaccount_required else "",
            ]
            subprocess.check_call(cmd, cwd=BASE_DIR)
            cmd[-1] = " ".join(
                [
                    "/usr/local/bin/bee-clef",
                    "--stdio-ui",
                    "--keystore",
                    "/app/data/keystore",
                    "--configdir",
                    "/app/data/",
                    "--chainid",
                    CHAIN_ID,
                    "--http",
                    "--http.addr",
                    "0.0.0.0",
                    "--http.port",
                    "8550",
                    "--http.vhosts",
                    "'*'",
                    "--rules",
                    "/app/config/rules.js",
                    "--nousb",
                    "--lightkdf",
                    "--ipcpath",
                    "/app/geth/geth.ipc",
                    "--4bytedb-custom ",
                    "/app/config/4byte.json",
                    "--pcscdpath",
                    "/app/data/run/pcscd/pcscd.comm",
                    "--auditlog",
                    "''",
                    "--loglevel",
                    "3",
                ]
            )
            print("ETH Node - Consensus client started!\n", cmd)
            return subprocess.Popen(cmd, cwd=BASE_DIR)
        except Exception as e:
            # TODO: handle Error
            raise e
            print(e)

    def cleanup_container(self, name):
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

    def wait_concensus(self):
        keys = []
        if os.path.isdir(os.path.join(BASE_DIR, "consensus", "keystore")):
            keys = list(
                map(
                    lambda item: item.path,
                    os.scandir(os.path.join(BASE_DIR, "consensus", "keystore")),
                )
            )
        if not len(keys):
            sleep(settings.ETH_NODE["CONCENSUS"]["THROTTLE_TIME"])
            self.wait_concensus()
            return False
        # TODO: rm debug codes
        # subprocess.call(["code", keys[-1]])
        return True

    def cleanup(self):
        if self.consensus_ps:
            self.consensus_ps.terminate()
        if self.gateway_ps:
            print("exit ", self.gateway_ps.returncode)
        self.cleanup_container("ethnode-concensus")
        self.cleanup_container("ethnode-gateway")
