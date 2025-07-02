import logging
import bot.config.mylogger as mylogger
mylogger.set_logging()

from bot.config.credentials import DISCORD_TOKEN, OPENAI_API_KEY
from bot.discord.discord_client import MyDiscordClient
from bot.llm.llm_client import MyOpenAIClient

if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    # instantiate clients
    discordClient = MyDiscordClient()
    openaiClient = MyOpenAIClient(api_key = OPENAI_API_KEY)

    # set reference attributes
    discordClient.llm = openaiClient
    
    # start
    discordClient.run(DISCORD_TOKEN, log_handler=None)

    
    
