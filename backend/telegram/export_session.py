"""Export Telethon session to StringSession for cloud deployment."""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from config import get_config


async def export_session():
    config = get_config()

    print("=" * 60)
    print("TELEGRAM SESSION EXPORT TOOL")
    print("=" * 60)
    print(f"Phone: {config.TELEGRAM_PHONE}")
    print(f"Device: {config.DEVICE_MODEL} ({config.SYSTEM_VERSION})")
    print("=" * 60 + "\n")

    client = TelegramClient(
        config.SESSION_NAME,
        config.TELEGRAM_API_ID,
        config.TELEGRAM_API_HASH,
        device_model=config.DEVICE_MODEL,
        system_version=config.SYSTEM_VERSION,
        app_version=config.APP_VERSION,
        lang_code=config.LANG_CODE,
        system_lang_code=config.SYSTEM_LANG_CODE,
    )

    await client.connect()

    if await client.is_user_authorized():
        print("Session is already authorized!")
        me = await client.get_me()
        print(f"Logged in as: {me.first_name} (@{me.username})\n")
    else:
        print("Starting fresh authentication...\n")
        await client.send_code_request(config.TELEGRAM_PHONE)
        print("Verification code sent to your Telegram app.")
        code = input("Enter the verification code: ").strip()

        try:
            await client.sign_in(config.TELEGRAM_PHONE, code)
            print("Successfully authenticated!")
        except SessionPasswordNeededError:
            print("\nYour account has 2FA enabled.")
            if config.TELEGRAM_2FA_PASSWORD:
                password = config.TELEGRAM_2FA_PASSWORD
            else:
                password = input("Enter your 2FA password: ").strip()
            await client.sign_in(password=password)
            print("Successfully authenticated with 2FA!")

        me = await client.get_me()
        print(f"\nLogged in as: {me.first_name} (@{me.username})")

    string_session = StringSession.save(client.session)

    print("\n" + "=" * 60)
    print("SUCCESS! Copy the string below:")
    print("=" * 60)
    print("\n" + string_session + "\n")
    print("=" * 60)
    print("\nSet TELEGRAM_SESSION in your .env file with this value.")
    print("=" * 60)

    await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(export_session())
    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
