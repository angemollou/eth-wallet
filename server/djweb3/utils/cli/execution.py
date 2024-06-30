import os
from djweb3.utils.cli.common import touch
from djweb3.utils.event import Logger
from djweb3.utils.mapper import Mapper
from djweb3.utils.models import SingletonAbstract


class Execution(SingletonAbstract):
    def __init__(self, **kwargs) -> None:
        self.path = kwargs["path"]
        self.jwtsecret = kwargs["jwtsecret"]

        try:
            if not os.path.isdir(self.path()):
                os.makedirs(self.path())
                touch(self.path(".ethereum/geth/jwtsecret"), self.jwtsecret)

            Logger.info("init", "execution", "success")
        except Exception as e:
            Logger.error("signer", e)

    @classmethod
    def parse_options(cls, options):
        try:
            ports = [
                ("--http.port", options["http.port"]),
                ("--ws.port", options["ws.port"]),
                ("--authrpc.port", options["authrpc.port"]),
            ]
            cmd = [
                # ("--sepolia", options["sepolia"]),
                ("--networkid", options["chainid"]),
                ("--authrpc.addr", options["authrpc.addr"]),
                ("--authrpc.vhosts", options["authrpc.vhosts"]),
                ("--signer", options["signer"]),
                (
                    ("--ipcdisable", True)
                    if options["ipcdisable"]
                    else (
                        "--ipcpath",
                        options["ipcpath"] or "/app/.ethereum/geth/geth.ipc",
                    )
                ),
                ("--http", "http" in options),
                ("--ws", "ws" in options),
            ]

            # Conditional
            required = {
                "http": "http" in options,
                "ws": "ws" in options,
            }
            if required["http"]:
                cmd.extend(
                    [
                        ("--http.addr", options["http.addr"]),
                        ("--http.api", options["http.api"]),
                        ("--http.corsdomain", options["http.corsdomain"]),
                    ]
                )
            if required["ws"]:
                cmd.extend(
                    [
                        ("--ws.addr", options["ws.addr"]),
                        ("--ws.api", options["ws.api"]),
                        ("--ws.origins", options["ws.origins"]),
                    ]
                )

            return {
                "tty": options["tty"],
                **Mapper.client_options(ports=ports, cmd=cmd),
            }
        except Exception as e:
            Logger.error("execution config", e)

    @classmethod
    def volumes(cls, path):
        return [
            {
                "type": "bind",
                "source": path(".ethereum/geth/jwtsecret"),
                "target": "/root/.ethereum/geth/jwtsecret",
                # ensure integrity
                "read_only": True,
            },
            {
                "type": "bind",
                "source": path(),
                "target": "/root/",
            },
        ]
