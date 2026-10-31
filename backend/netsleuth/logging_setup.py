import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging(level: str = "INFO", log_file: Path | None = None, console: bool = True) -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)

    formatter = logging.Formatter(_FORMAT)
    if console:
        stream = logging.StreamHandler(sys.stderr)
        stream.setFormatter(formatter)
        root.addHandler(stream)
    if log_file:
        rotating = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=5, encoding="utf-8")
        rotating.setFormatter(formatter)
        root.addHandler(rotating)

    # Third-party chatter
    logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
