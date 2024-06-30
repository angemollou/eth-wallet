class Mapper:

    @classmethod
    def client_options(cls, env=[], ports=[], cmd=[]):
        env_map = []
        for pair in env:
            result = cls.env(pair)
            if len(result) != 0:
                env_map.extend(result)

        ports_map = []
        for pair in ports:
            ports_map.append(cls.port(pair))

        cmd_map = []
        for pair in [*ports, *cmd]:
            cmd_map.extend(cls.cmd(pair))

        return {
            "env": env_map,
            "ports": ports_map,
            "cmd": cmd_map,
        }

    @classmethod
    def service(cls, client_options):
        return {
            "tty": client_options["tty"],
            "cmd": client_options["cmd"],
            "ports": [
                {
                    "target": s["port"],
                    "published": s["port"],
                    # only with the host's loopback network interface
                    "host_ip": "127.0.0.1",
                    # specific to the client, defaults to `tcp`, from docker spec
                    "protocol": "tcp",
                    # port will not be load balanced
                    "mode": "host",
                }
                for s in client_options["ports"]
            ],
            "volumes": None,
        }

    @classmethod
    def env(cls, s: tuple[str, str]):
        key, value = s
        if value in (None,):
            return []
        return [key, value]

    @classmethod
    def port(cls, s: tuple[str, str]):
        """
        @param s: e.g. (--http.port, '111'), (--http-port, '111')
        """
        key, value = s
        try:
            return {
                "protocol": key.removeprefix("--").removesuffix(
                    ".port" if "." in key else "-port"
                ),
                "port": int(value),
            }
        except ValueError:
            raise ValueError("%s=%s" % (key, value), "cannot be a port number")

    @classmethod
    def cmd(cls, s: tuple[str, str]):
        key, value = s
        if value in ("", None, False, 0):
            return []
        elif value in (True, 1):
            return [key]
        return [key, value]

    @classmethod
    def volumes(cls, props):
        return [
            (
                "--mount",
                ",".join(
                    [
                        cls.volume_opt(
                            volume.pop(volume["type"])
                            if volume.get(volume["type"])
                            else None
                        ),
                        *map(
                            lambda pair: "%s=%s" % pair,
                            volume.items(),
                        ),
                    ]
                ),
            )
            for volume in props
        ]

    @classmethod
    def volume_opt(cls, opts):
        if opts is None:
            return ""
        return 'volume-opt="%s"' % ",".join(
            map(
                lambda pair: "%s=%s" % pair,
                opts.items(),
            )
        )
