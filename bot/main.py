import logging
import bot.config.mylogger as mylogger
mylogger.set_logging()

from bot.config.credentials import DISCORD_TOKEN, OPENAI_API_KEY
from bot.db.vector_db import Topic_VDB
from bot.discord.discord_client import MyDiscordClient
from bot.llm.llm_client import MyOpenAIClient
from bot.llm.llm_rag import LLM_RAG

if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    # instantiate clients
    discordClient = MyDiscordClient()
    topicVDB = Topic_VDB(
        persist_directory='./VDB_persist',
        topic_merge_threshold = 0.25,
        topic_query_threshold = 0.8,
        topic_CA_period = 10
    )
    openaiClient = MyOpenAIClient(api_key = OPENAI_API_KEY)
    RAG_module = LLM_RAG(retrieval_limit=50, recents_limit=10000)

    # set reference attributes
    discordClient.RAG = RAG_module
    topicVDB.set_llm_client(openaiClient)
    RAG_module.DB = topicVDB
    RAG_module.DiscordClient = discordClient
    RAG_module.LLMClient = openaiClient
    
    discordClient.run(DISCORD_TOKEN, log_handler=None)

    
    
