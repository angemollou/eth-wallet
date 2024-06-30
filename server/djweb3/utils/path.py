import os

from djweb3.utils.models import SingletonAbstract


class Path(SingletonAbstract):
    __base_dir = None

    # TODO: Refactor into a better singleton
    # TODO: Take advantage of `Path` from `pathlib` embedded in django
    def __init__(self, base_dir):
        if Path.__base_dir:
            return
        Path.__base_dir = base_dir

    @classmethod
    def abs(cls, *path):
        if len(path) == 0:
            return cls.__base_dir
        return os.path.join(cls.__base_dir, *path)

    @classmethod
    def signer(cls, *path):
        return cls.abs("signer", *path)

    @classmethod
    def execution(cls, *path):
        return cls.abs("execution", *path)

    @classmethod
    def consensus(cls, *path):
        return cls.abs("consensus", *path)
