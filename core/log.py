"""One log file per day in logs/, plus the same messages in the console."""
import logging
from datetime import date
from pathlib import Path


def setup_logging(log_dir):
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"run_{date.today()}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler()],
        force=True,
    )
    return path
