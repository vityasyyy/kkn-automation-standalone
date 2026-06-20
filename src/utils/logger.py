import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_FILE = LOG_DIR / "kkn.log"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(1024 * 1024)))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "7"))

_configured = False


def setup_logging(level: str | None = None, headless: bool = False) -> logging.Logger:
  global _configured
  logger = logging.getLogger("kkn")

  if _configured:
    if level:
      logger.setLevel(level.upper())
    return logger

  effective_level = (level or LOG_LEVEL).upper()
  logger.setLevel(effective_level)
  logger.propagate = False

  if not headless:
    console_handler = RichHandler(show_time=True, show_level=True, show_path=False, markup=True, rich_tracebacks=True)
    console_handler.setLevel(effective_level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

  try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8")
    file_handler.setLevel(effective_level)
    file_handler.setFormatter(
      logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)
  except OSError:
    pass

  _configured = True
  return logger


def get_logger(name: str | None = None) -> logging.Logger:
  if not _configured:
    setup_logging()
  return logging.getLogger("kkn" if name is None else f"kkn.{name}")
