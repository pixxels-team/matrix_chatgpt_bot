import asyncio
import json
import os
from pathlib import Path
import signal
import sys

from bot import Bot
from log import getlogger

logger = getlogger()


async def main():
    need_import_keys = False
    config_path = Path(os.path.dirname(__file__)).parent / "config.json"
    print(config_path)
    if os.path.isfile(config_path):
        try:
            fp = open(config_path, encoding="utf8")
            config = json.load(fp)
        except Exception:
            logger.error("config.json load error, please check the file")
            sys.exit(1)
        print(config.get("device_id"))
        matrix_bot = Bot(
            homeserver=config.get("homeserver"),
            user_id=config.get("user_id"),
            password=config.get("password"),
            device_id=config.get("device_id"),
            import_keys_path=config.get("import_keys_path"),
            import_keys_password=config.get("import_keys_password"),
            timeout=config.get("timeout"),
            superagent_url=config.get("superagent_url"),
            agent_id=config.get("agent_id"),
            api_key=config.get("api_key"),
            owner_id=config.get("owner_id")
        )
        if (
            config.get("import_keys_path")
            and config.get("import_keys_password") is not None
        ):
            need_import_keys = True

    else:
        matrix_bot = Bot(
            homeserver=os.environ.get("HOMESERVER"),
            user_id=os.environ.get("USER_ID"),
            password=os.environ.get("PASSWORD"),
            device_id=os.environ.get("DEVICE_ID"),
            import_keys_path=os.environ.get("IMPORT_KEYS_PATH"),
            import_keys_password=os.environ.get("IMPORT_KEYS_PASSWORD"),
            superagent_url=os.environ.get("SUPERAGENT_URL"),
            agent_id=os.environ.get("AGENT_ID"),
            api_key=os.environ.get("API_KEY"),
            timeout=os.environ.get("TIMEOUT"),
            owner_id=os.environ.get("OWNER_ID")
        )
        if (
            os.environ.get("IMPORT_KEYS_PATH")
            and os.environ.get("IMPORT_KEYS_PASSWORD") is not None
        ):
            need_import_keys = True

    await matrix_bot.login()
    if need_import_keys:
        logger.info("start import_keys process, this may take a while...")
        await matrix_bot.import_keys()

    sync_task = asyncio.create_task(
        matrix_bot.sync_forever(timeout=30000, full_state=True)
    )

    # handle signal interrupt
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        loop.add_signal_handler(
            getattr(signal, signame),
            lambda: asyncio.create_task(matrix_bot.close(sync_task)),
        )

    if matrix_bot.client.should_upload_keys:
        await matrix_bot.client.keys_upload()

    await sync_task


if __name__ == "__main__":
    logger.info("matrix chatgpt bot start.....")
    asyncio.run(main())
