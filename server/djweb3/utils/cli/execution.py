import os
import shutil
from djweb3.utils.event import Logger
from djweb3.utils.models import SingletonAbstract


class Execution(SingletonAbstract):
    def __init__(self, **kwargs) -> None:
        self.path = kwargs["path"]

        try:
            if not os.path.isdir(self.path()):
                os.makedirs(self.path())
                os.makedirs(self.path(".ethereum/geth/"))

            Logger.info("init", "execution", "success")
        except Exception as e:
            Logger.error("signer", e)
