"""Central config — reads from environment / .env file. FREE stack (Groq)."""
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(v: str, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


class Config:
    # Brain — Groq (free, OpenAI-compatible)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    MODEL = os.getenv("MODEL", "llama-3.3-70b-versatile")

    # Control panel
    APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")

    # Email
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
    EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
    IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))

    # WhatsApp
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "verify-123")

    # Misc
    TZ = os.getenv("TZ", "Asia/Kolkata")
    REQUIRE_CONFIRMATION = _bool(os.getenv("REQUIRE_CONFIRMATION"), True)

    OUTPUT_DIR = os.getenv("OUTPUT_DIR", os.path.join(os.getcwd(), "outputs"))
    DB_PATH = os.getenv("DB_PATH", os.path.join(os.getcwd(), "office.db"))

    @classmethod
    def check(cls):
        if not cls.GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY missing - .env file mein daalo (free key: console.groq.com)")
        os.makedirs(cls.OUTPUT_DIR, exist_ok=True)


config = Config()
