"""Configuration management for AI School Assistant.

Validates all required environment variables at startup.
Never use os.getenv directly in application code - use the config object.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))


class ConfigurationError(Exception):
    pass


class Config:
    # Core vars required for API + agent + RAG
    REQUIRED_ENV_VARS = [
        'SUPABASE_URL',
        'SUPABASE_SERVICE_ROLE_KEY',
        'ANTHROPIC_API_KEY',
        'OPENAI_API_KEY',
    ]

    # Telegram vars only required when running the userbot
    TELEGRAM_ENV_VARS = [
        'TELEGRAM_API_ID',
        'TELEGRAM_API_HASH',
        'TELEGRAM_PHONE',
    ]

    def __init__(self):
        # Telegram
        try:
            self.TELEGRAM_API_ID: int = int(os.getenv('TELEGRAM_API_ID', '0'))
        except (ValueError, TypeError):
            self.TELEGRAM_API_ID = 0
        self.TELEGRAM_API_HASH: str = os.getenv('TELEGRAM_API_HASH', '')
        self.TELEGRAM_PHONE: str = os.getenv('TELEGRAM_PHONE', '')
        self.SESSION_NAME: str = os.getenv('TELETHON_SESSION_NAME', 'school_assistant_userbot')
        self.TELEGRAM_SESSION: str = os.getenv('TELEGRAM_SESSION', '')
        self.TELEGRAM_2FA_PASSWORD: str = os.getenv('TELEGRAM_2FA_PASSWORD', '')

        # Device spoofing
        self.DEVICE_MODEL: str = os.getenv('DEVICE_MODEL', 'Desktop')
        self.SYSTEM_VERSION: str = os.getenv('SYSTEM_VERSION', 'Windows 10')
        self.APP_VERSION: str = os.getenv('APP_VERSION', '4.16.8')
        self.LANG_CODE: str = os.getenv('LANG_CODE', 'ru')
        self.SYSTEM_LANG_CODE: str = os.getenv('SYSTEM_LANG_CODE', 'ru-RU')

        # Supabase
        self.SUPABASE_URL: str = os.getenv('SUPABASE_URL', '')
        self.SUPABASE_SERVICE_ROLE_KEY: str = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '')

        # LLM
        self.ANTHROPIC_API_KEY: str = os.getenv('ANTHROPIC_API_KEY', '')
        self.OPENAI_API_KEY: str = os.getenv('OPENAI_API_KEY', '')

        # Letta Memory (optional)
        self.LETTA_API_KEY: str = os.getenv('LETTA_API_KEY', '')
        # BYOK model handle — use your own LLM key instead of Letta credits.
        # Format: "{provider-name}/{model}" e.g. "open-ai-api/gpt-4.1-mini"
        # The provider name must match what you configured at app.letta.com/models
        self.LETTA_BYOK_MODEL: str = os.getenv('LETTA_BYOK_MODEL', '')

        # Admin auth (optional — if not set, API is open for local dev)
        self.ADMIN_API_KEY: str = os.getenv('ADMIN_API_KEY', '')

        # CORS origins (comma-separated). Defaults to localhost for dev.
        self.ALLOWED_ORIGINS: list[str] = [
            o.strip() for o in os.getenv('ALLOWED_ORIGINS', '').split(',') if o.strip()
        ] or [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:3700",
            "http://localhost:3800",
        ]

        # Telegram username to notify on API errors (without @)
        self.ADMIN_TELEGRAM_USERNAME: str = os.getenv('ADMIN_TELEGRAM_USERNAME', '')

        # App
        self.LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
        self.FASTAPI_PORT: int = int(os.getenv('FASTAPI_PORT', '8000'))

    def __repr__(self) -> str:
        return (
            f"Config("
            f"TELEGRAM_API_ID={self.TELEGRAM_API_ID}, "
            f"TELEGRAM_PHONE=***REDACTED***, "
            f"SESSION_NAME={self.SESSION_NAME}, "
            f"SUPABASE_URL={self.SUPABASE_URL[:30]}..., "
            f"LOG_LEVEL={self.LOG_LEVEL})"
        )

    @classmethod
    def validate(cls) -> None:
        missing = []
        for env_var in cls.REQUIRED_ENV_VARS:
            value = os.getenv(env_var, '')
            if not value or value.strip() == '':
                missing.append(env_var)

        if missing:
            missing = list(dict.fromkeys(missing))
            print('=' * 60, file=sys.stderr)
            print('FATAL: Missing required environment variables:', file=sys.stderr)
            for var_name in missing:
                print(f'  - {var_name}', file=sys.stderr)
            print('', file=sys.stderr)
            print('Copy .env.example to .env and fill in your values.', file=sys.stderr)
            print('=' * 60, file=sys.stderr)
            raise ConfigurationError(f"Missing: {', '.join(missing)}")

    @classmethod
    def validate_telegram(cls) -> None:
        """Validate Telegram-specific env vars. Call before starting the userbot."""
        missing = []
        for env_var in cls.TELEGRAM_ENV_VARS:
            value = os.getenv(env_var, '')
            if not value or value.strip() == '':
                missing.append(env_var)
        # TELEGRAM_API_ID must be a nonzero integer
        try:
            if int(os.getenv('TELEGRAM_API_ID', '0')) == 0:
                if 'TELEGRAM_API_ID' not in missing:
                    missing.append('TELEGRAM_API_ID')
        except (ValueError, TypeError):
            if 'TELEGRAM_API_ID' not in missing:
                missing.append('TELEGRAM_API_ID')

        if missing:
            raise ConfigurationError(
                f"Telegram vars missing: {', '.join(missing)}. "
                "Userbot will not start — running in API-only mode."
            )


def get_config() -> Config:
    """Get validated config. Call this instead of importing config directly
    so tests can mock it."""
    Config.validate()
    return Config()
