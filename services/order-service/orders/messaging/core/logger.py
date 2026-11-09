import logging
import sys

_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def get_logger(name: str) -> logging.Logger:
    module_logger = logging.getLogger(name)
    module_logger.setLevel(logging.INFO)

    if not module_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FORMAT))
        module_logger.addHandler(handler)

    module_logger.propagate = False
    return module_logger



