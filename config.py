"""Project settings. Any value can be overridden in a .env file next to this one."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent
load_dotenv(PROJECT_DIR / ".env")

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", PROJECT_DIR / "output"))
LOG_DIR = Path(os.getenv("LOG_DIR", PROJECT_DIR / "logs"))
DEFAULT_PAGES = int(os.getenv("DEFAULT_PAGES", "50"))
