import os
import subprocess
import shutil
from time import sleep
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

BASE_DIR = settings.ETH_NODE["BASE_DIR"]


class Command(BaseCommand):
    help = "Run a Geth Ethereum node via docker"

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
            "-c", "--clean", action="store_true", help="Clean volumes?"
        )  # on/off flag

    def handle(self, *args, **options):
        status = 0
        try:
            if options["clean"]:
                shutil.rmtree(BASE_DIR, ignore_errors=True)
            if not os.path.isdir(BASE_DIR):
                os.makedirs(os.path.join(BASE_DIR, "execution"))

            consensus_ps = self.generate_concensus(*args, **options)
            if not consensus_ps:
                return
            self.wait_ipc(),
            cmd = "docker run{detach} -t --name ethnode-execution --rm -p 8545:{http} -p 30303:{tcp} -v ./execution:/root ethereum/client-go --http.addr 0.0.0.0 --ipcpath=/root/concensus.ipc".format(
                detach=" -d" if options["detach"] else "",
                http=settings.ETH_NODE["EXECUTION"]["HTTP"] or 8545,
                tcp=settings.ETH_NODE["EXECUTION"]["TCP"] or 30303,
            )
            print("ETH Node - Execution client started!\n", cmd)
            status = subprocess.call(cmd.split(" "), cwd=BASE_DIR)
            consensus_ps.wait()
        except Exception as e:
            print(e)
        finally:
            # TODO: stop container
            exit(status)

    def wait_ipc(self):
        keys = list(
            map(
                lambda item: item.path,
                os.scandir(os.path.join(BASE_DIR, "concensus", "data", "keystore")),
            )
        )
        if not len(keys):
            sleep(settings.ETH_NODE["CONCENSUS"]["THROTTLE_TIME"])
            return self.wait_ipc()
        print({"lastest_ipc": keys})
        with open(keys[-1], "r") as src:
            with open(
                os.path.join(BASE_DIR, "execution", "concensus.ipc"), "w"
            ) as dest:
                return dest.write(src.read())

    def generate_concensus(self, *args, **options):
        try:
            is_newaccount_required = options["clean"] or options["newaccount"]
            if options["newaccount"]:
                shutil.rmtree(os.path.join(BASE_DIR, "concensus"), ignore_errors=True)
            if not os.path.isdir(os.path.join(BASE_DIR, "concensus")):
                os.makedirs(os.path.join(BASE_DIR, "concensus", "data", "keystore"))
                os.makedirs(os.path.join(BASE_DIR, "concensus", "tmp"))
                if options["password"]:
                    with open(
                        os.path.join(BASE_DIR, "concensus", "data", "password"), "w"
                    ) as fd:
                        fd.write(options["password"])
                    is_newaccount_required = True
                else:
                    exit("-w, --password is required")

            cmd = "docker run{detach} -t --name ethnode-concensus --rm -p 8550:{http} -v ./concensus/tmp:/tmp -v ./concensus/data:/app/data -e CLEF_CHAINID={chainid} ethersphere/clef{full}".format(
                detach=" -d" if options["detach"] else "",
                http=settings.ETH_NODE["CONCENSUS"]["HTTP"] or 8550,
                full=(" full" if is_newaccount_required else ""),
                chainid=(
                    11155111  # Sepolia testnet
                    if settings.DEBUG
                    else settings.ETH_NODE["CONCENSUS"]["CHAIN_ID"]
                ),
            )
            print("ETH Node - Consensus client started!\n", cmd)
            return subprocess.Popen(cmd.split(" "), cwd=BASE_DIR)
        except Exception as e:
            print(e)
        finally:
            # TODO: stop container
            pass
