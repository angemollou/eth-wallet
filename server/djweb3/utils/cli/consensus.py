import os
from djweb3.utils.cli.common import touch
from djweb3.utils.event import Logger
from djweb3.utils.mapper import Mapper
from djweb3.utils.models import SingletonAbstract


class Consensus(SingletonAbstract):
    def __init__(self, **kwargs) -> None:
        self.path = kwargs["path"]

        try:
            if not os.path.isdir(self.path()):
                os.makedirs(self.path())

            Logger.info("init", "consensus", "success")
        except Exception as e:
            Logger.error("signer", e)

    @classmethod
    def parse_options(cls, env, options):
        try:
            ports = []
            cmd = [
                ("--network", options["network"]),
                ("--checkpoint-sync-url", options["checkpoint-sync-url"]),
                (
                    "--allow-insecure-genesis-sync",
                    options["allow-insecure-genesis-sync"],
                ),
                ("--http", "http" in options["api"]),
                ("--execution-endpoint", options["execution-endpoint"]),
                # ("--execution-jwt", "/tmp/jwtsecret"),
                ("--execution-jwt-secret-key", options["execution-jwt-secret-key"]),
            ]
            # Conditional
            required = {"http": options["api"]["http"]}
            if required["http"]:
                ports.extend(
                    [
                        (
                            "--http-port",
                            options["api"]["http"].get("port", "5052"),
                        ),
                    ]
                )
                cmd.extend(
                    [
                        (
                            "--http-address",
                            options["api"]["http"].get("address", "localhost"),
                        ),
                        (
                            "--http-allow-origin",
                            options["api"]["http"].get("allow-origin", "'*'"),
                        ),
                    ]
                )
                if required["http"]["enable-tls"]:
                    cmd.extend(
                        [
                            (
                                "--http-enable-tls",
                                options["api"]["http"].get("enable-tls", False),
                            ),
                            (
                                "--http-tls-cert",
                                options["api"]["http"].get("tls-cert"),
                            ),
                            (
                                "--http-tls-key",
                                options["api"]["http"].get("tls-key"),
                            ),
                        ]
                    )
            mapping = Mapper.client_options(ports=ports, cmd=cmd)

            return {
                "tty": options["tty"],
                "ports": [
                    *mapping["ports"],
                    {"protocol": "tcp", "port": 9000},
                    {"protocol": "udp", "port": 9000},
                    {"protocol": "udp", "port": 9001},
                ],
                "cmd": [
                    *env["bin"],
                    *mapping["cmd"],
                ],
            }
        except Exception as e:
            Logger.error("consensus config", e)

    @classmethod
    def volumes(cls, path):
        return [
            # {
            #     "type": "bind",
            #     "source": os.path.join(os.path.dirname(path()), "tmp/jwtsecret"),
            #     "target": "/tmp/jwtsecret",
            #     # ensure integrity
            #     "read_only": True,
            # },
            {
                "type": "bind",
                "source": path(),
                "target": "/root/",
            },
        ]
