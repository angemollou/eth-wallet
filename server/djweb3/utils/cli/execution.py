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
                touch(
                    os.path.join(os.path.dirname(self.path()), "tmp/jwtsecret"),
                    self.jwtsecret,
                )

            Logger.info("init", "execution", "success")
        except Exception as e:
            Logger.error("signer", e)

    @classmethod
    def parse_options(cls, env, options):
        try:
            ports = [
                ("--http.port", options["http.port"]),
                ("--ws.port", options["ws.port"]),
                ("--authrpc.port", options["authrpc.port"]),
            ]
            cmd = [
                ("--authrpc.addr", options["authrpc.addr"]),
                ("--authrpc.vhosts", options["authrpc.vhosts"]),
                ("--authrpc.jwtsecret", "/tmp/jwtsecret"),
                ("--signer", options["signer"]),
                (
                    ("--ipcdisable", True)
                    if options["ipcdisable"]
                    else (
                        "--ipcpath",
                        options["ipcpath"] or "/root/.ethereum/geth/geth.ipc",
                    )
                ),
                ("--http", "http" in options),
                ("--ws", "ws" in options),
                ("--%s" % options["network"], True),
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

            mapping = Mapper.client_options(ports=ports, cmd=cmd)
            return {
                "tty": options["tty"],
                "ports": mapping["ports"],
                "cmd": [
                    *env["bin"],
                    *mapping["cmd"],
                ],
            }
        except Exception as e:
            Logger.error("execution config", e)

    @classmethod
    def volumes(cls, path):
        return [
            {
                "type": "bind",
                "source": os.path.join(os.path.dirname(path()), "tmp/jwtsecret"),
                "target": "/tmp/jwtsecret",
                # ensure integrity
                "read_only": True,
            },
            {
                "type": "bind",
                "source": path(),
                "target": "/root/",
            },
        ]

    @classmethod
    def get_jwtsecret(cls, path):
        filename = os.path.join(os.path.dirname(path()), "tmp/jwtsecret")
        with open(filename, "r") as fd:
            return fd.read()
