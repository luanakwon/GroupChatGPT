from __future__ import annotations
from typing import TYPE_CHECKING

import logging
logger = logging.getLogger(__name__)

import datetime

if TYPE_CHECKING:
    from bot.db.vector_db import Topic_VDB
    from bot.discord.discord_client import MyDiscordClient
    from .llm_client import MyOpenAIClient
    from bot.discord.simple_message import SimpleMessage

class LLM_RAG:
    def __init__(self, retrieval_limit, recents_limit):
        self.retrieval_limit = retrieval_limit # max number of messages to be retrieved
        self.recents_limit = recents_limit # max number of characters before embedding them

        # time window (default 5min) to pick recent messages as a question for retrieval
        self._context_query_window = datetime.timedelta(minutes=5)

        # Module reference 
        self.DB: Topic_VDB = None
        self.DiscordClient : MyDiscordClient = None
        self.LLMClient: MyOpenAIClient = None

    async def invoke(self, channel_id, recent_context):
        # method 1 - limit by number of charactors(approx) 
        char_count = 0
        half_idx = 0
        for i, context in enumerate(recent_context):
            char_count += len(context.content)
            if char_count > self.recents_limit//2 and half_idx == 0:
                half_idx = i
            if char_count > self.recents_limit:
                to_embed_context = recent_context[half_idx:]
                recent_context = recent_context[:half_idx]
                await self.update(channel_id, to_embed_context)
                break

        logger.debug(f"after embedding overflows -> len(recent_context)={len(recent_context)}")

        # # method 2 - limit by number of messages(short messages within one minute is collapsed into one)
        # # if recent context exceeds the limit, embed some
        # if len(recent_context) > self.recents_limit:
        #     to_embed_context = recent_context[self.recents_limit//2:]
        #     recent_context = recent_context[:self.recents_limit//2]
        #     await self.update(channel_id,to_embed_context)

        # pick messages in recent 5 minutes as a question for retrieval
        question = []
        t1 = recent_context[-1].created_at
        context: SimpleMessage
        for context in reversed(recent_context):
            if t1 - context.created_at < self._context_query_window:
                question.insert(0,context.content)
        question = "\n".join(question)

        # query db
        ret_context_timestamp = self.DB.query(channel_id, question, k=1)

        logger.debug(f"len ret_context_timestamp = {len(ret_context_timestamp)}")

        # limit the size of retrieved context
        if len(ret_context_timestamp) > 0:
            if len(ret_context_timestamp) > self.retrieval_limit:
                ret_context_timestamp = ret_context_timestamp[:self.retrieval_limit]
            # request actual messages that match the timestamp
            ret_context = await self.DiscordClient.get_message(ret_context_timestamp)
        else:
            ret_context = []

        logger.debug(f"len ret_context = {len(ret_context)}")

        # query llm
        llm_answer = self.LLMClient.query(
            ret_context, recent_context
        )
        
        return llm_answer
    
    # recent_context:List[SimpleMessage]
    async def update(self, channel_id, recent_context):
        documents = [r.content for r in recent_context]
        timestamps = [r.created_at for r in recent_context]
        
        self.DiscordClient.set_channel_timestamp(channel_id,timestamps[-1])
        self.DB.push(channel_id, documents, timestamps)