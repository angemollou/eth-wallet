import re


class Normalizer:

    @classmethod
    def label(cls, name: str):
        return re.sub("[^a-z0-9_-]", "_", re.sub(r"^[^a-z0-9]", "_", name))
