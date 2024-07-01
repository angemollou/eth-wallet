class ConnectionError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.message = "Connection to Ethereum node failed!"
