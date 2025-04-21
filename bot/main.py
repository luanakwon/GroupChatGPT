import logging
import bot.config.mylogger as mylogger
mylogger.set_logging()

from bot.config.credentials import DISCORD_TOKEN
from bot.discord.discord_client import MyDiscordClient

if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    try:
        1 / 0
    except Exception:
        logger.error("ZeroDivision!", exc_info=True)

    client = MyDiscordClient()
    client.run(DISCORD_TOKEN, log_handler=None)
    
    
