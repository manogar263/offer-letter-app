import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")

DATABASE_URL = os.getenv(
    "DATABASE_URL", f"sqlite:///{BASE_DIR.parent / 'offer_letters.db'}"
)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "static" / "uploads"))
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = os.getenv("SMTP_PORT", "587")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")

MAX_UPLOAD_BYTES = 2 * 1024 * 1024  # 2 MB per image
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}

EMPLOYMENT_TYPES = ["Full Time", "Part Time", "Internship", "Contract"]
LETTER_STATUSES = ["Issued", "Accepted"]
