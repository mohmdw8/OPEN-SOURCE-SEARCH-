import sys
import os
import logging
from datetime import datetime

LOG_FILE = "opss.log"


class _FileLogger:
    def __init__(self):
        self._enabled = False
        self._path = ""
        self._log = logging.getLogger("opss")

    def init(self, log_dir: str = ""):
        try:
            log_dir = log_dir or os.path.dirname(os.path.abspath(__file__))
            self._path = os.path.join(log_dir, LOG_FILE)
            handler = logging.FileHandler(self._path, encoding="utf-8")
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            ))
            self._log.addHandler(handler)
            self._log.setLevel(logging.WARNING)
            self._enabled = True
        except Exception:
            pass

    def debug(self, msg: str):
        if self._enabled:
            self._log.debug(msg)

    def info(self, msg: str):
        if self._enabled:
            self._log.info(msg)

    def warning(self, msg: str):
        if self._enabled:
            self._log.warning(msg)

    def error(self, msg: str):
        if self._enabled:
            self._log.error(msg)

    def exception(self, msg: str):
        if self._enabled:
            self._log.exception(msg)


logger = _FileLogger()
