"""
Centralized logging configuration for the behaviour rig system.

This handles **infrastructure logging only** — warnings, errors, and
debug messages from the core modules (session controller, peripheral
manager, camera manager, etc.). These go to the console and a log file.

Protocol-level messages that the user sees in the GUI session log
(e.g. "Trial 5: SUCCESS") continue to use the existing event system
(``self.log()`` → ``_emit("log")`` → ``"protocol_log"`` → GUI panel).
The two systems serve different purposes and coexist cleanly.

Usage in modules::

    import logging
    logger = logging.getLogger(__name__)

    logger.info("session started")
    logger.warning("could not remove signal file: %s", err)

Call ``configure_logging()`` once in ``main.py`` at startup.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# Logger names to configure. Because the project uses bare imports
# All hexcontrol.* loggers inherit from "hexcontrol". The workspace
# member packages (DAQLink, etc.) get their own top-level entries.
_LOGGER_NAMES = [
    "hexcontrol",   # covers hexcontrol.core, hexcontrol.gui, etc.
    "DAQLink", "ScalesLink", "BehavLink",  # workspace member packages
]

# Also exported so main.py can get a logger that hits the same handlers.
ROOT_LOGGER_NAME = "hexcontrol"

# Default log directory: %LOCALAPPDATA%\BehaviourRigSystem\logs
# On Windows this is typically C:\Users\<name>\AppData\Local\BehaviourRigSystem\logs
_DEFAULT_LOG_DIR = Path(
    os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
) / "BehaviourRigSystem" / "logs"


def configure_logging(
    level: str = "INFO",
    log_dir: Optional[str | Path] = None,
) -> None:
    """
    Set up console + file logging for infrastructure messages.

    Args:
        level:   Minimum log level ("DEBUG", "INFO", "WARNING", "ERROR").
        log_dir: Directory for log files. Defaults to
                 ``%LOCALAPPDATA%\\BehaviourRigSystem\\logs``.
                 Set to ``None`` to use the default.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Check if already configured (avoid duplicates on restart)
    first_logger = logging.getLogger(_LOGGER_NAMES[0])
    if first_logger.handlers:
        return

    # --- Build handlers ---
    console_fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(console_fmt)

    log_path = Path(log_dir) if log_dir else _DEFAULT_LOG_DIR
    log_path.mkdir(parents=True, exist_ok=True)

    filename = datetime.now().strftime("%Y-%m-%d") + ".log"
    filepath = log_path / filename

    file_fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s\n"
        "    %(message)s\n",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    from logging.handlers import RotatingFileHandler
    fh = RotatingFileHandler(
        str(filepath),
        maxBytes=10 * 1024 * 1024,  # 10 MB per file
        backupCount=30,             # keep ~1 month of logs
        encoding="utf-8",
    )
    fh.setFormatter(file_fmt)

    # --- Attach handlers to every top-level package logger ---
    for name in _LOGGER_NAMES:
        lgr = logging.getLogger(name)
        lgr.setLevel(log_level)
        lgr.addHandler(console)
        lgr.addHandler(fh)

    logging.getLogger(_LOGGER_NAMES[0]).info(f"Log file: {filepath}")
