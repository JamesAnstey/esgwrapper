#!/usr/bin/env python

import logging
import sys

from pathlib import Path

from esgwrapper import SEND_STDOUT_TO_LOGFILE


class TeeStdoutToLogger:
    def __init__(self, logger, level=logging.INFO):
        self.logger = logger
        self.level = level
        self.terminal = sys.__stdout__  # Keep track of original stdout
    def write(self, message):
        # Avoid logging empty lines or pure whitespace from print endings
        if message.strip():
            # self.logger.log(self.level, message.strip())
            self.logger.log(self.level, message)
        self.terminal.write(message)  # Pass through to original console
    def flush(self):
        self.terminal.flush()  # Keep buffering behave correctly
    def fileno(self):
        # Delegate to the original stream's fileno if available
        if hasattr(self.original_stream, "fileno"):
            return self.original_stream.fileno()
        raise AttributeError("TeeStdoutToLogger does not have a fileno")


def init_logging(logger: logging.Logger, logfilename: str | Path) -> Path:

    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    logfile = log_dir / logfilename

    if SEND_STDOUT_TO_LOGFILE:
        sys.stdout = TeeStdoutToLogger(logger, logging.INFO)
    # logging.basicConfig(filename=logfile, filemode='w', level=logging.INFO)
    handlers = [logging.FileHandler(logfile, mode='w')]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers
    )
    return logfile
