import logging
import shutil


TERMINAL_SIZE = shutil.get_terminal_size()
LOG_SEPARATOR = "\n{}\n".format(
    "-" * int(TERMINAL_SIZE[0] * 80 / 100)
    if TERMINAL_SIZE[0] > 80
    else TERMINAL_SIZE[0]
)
logging.basicConfig(format="[%(asctime)s]  %(name)s  %(message)s")
LOGGER = logging.getLogger(__name__)

import shutil
import subprocess
from django.core.exceptions import ValidationError


class Logger:
    # TODO: all logs templates
    @classmethod
    def error(cls, service, e=Exception()):
        if isinstance(e, KeyboardInterrupt):
            LOGGER.error(
                "PROCESS STOP - %s  %s\n%s",
                service.upper(),
                e,
                LOG_SEPARATOR,
            )
        elif isinstance(e, subprocess.CalledProcessError):
            LOGGER.error(
                "PROCESS ERROR - %s  %s\n%s%s",
                service.upper(),
                e,
                e.output,
                LOG_SEPARATOR,
            )
        elif isinstance(e, ValidationError):
            LOGGER.error("BAD INPUT - %s", e.message)
        else:
            raise e

    @classmethod
    def info(cls, event, service, details=""):
        try:
            LOGGER.warning(
                "PROCESS %s - %s  %s",
                event.upper(),
                service.upper(),
                details,
            )
        except Exception as e:
            LOGGER.error("EVENT not properly handled: %s", e)
