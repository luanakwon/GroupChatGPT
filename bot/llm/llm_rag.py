from __future__ import annotations
from typing import TYPE_CHECKING, List

import logging
logger = logging.getLogger(__name__)

import datetime
MINUTE = datetime.timedelta(minutes=1)


if TYPE_CHECKING:
    from bot.db.vector_db import Topic_VDB
    from bot.discord.discord_client import MyDiscordClient
    from .llm_client import MyOpenAIClient
    from bot.discord.simple_message import SimpleMessage


# TODO Debugging sucks, especially the RAG querying part. 
# I can't tell out of what, what are retrieved, what are filtered and what are truncated. 

class LLM_RAG:
    def __init__(self, retrieval_limit, recents_limit):
        """
        retrieval_limit: max number of messages to be retrieved
        recents_limit: max number of characters before embedding them
        """
        self.retrieval_limit = retrieval_limit 
        self.recents_limit = recents_limit 

        # time window (default 5min) to pick recent messages as a question for retrieval
        self._context_query_window = datetime.timedelta(minutes=5)

        # Module reference 
        self.DB: Topic_VDB = None
        self.DiscordClient : MyDiscordClient = None
        self.LLMClient: MyOpenAIClient = None

    async def invoke(self, channel_id, recent_context):
        # method 1 - limit by number of characters(approx) 
        char_count = 0
        half_idx = 0
        for i, context in enumerate(reversed(recent_context)):
            char_count += len(context.content)
            if char_count > self.recents_limit//2 and half_idx == 0:
                half_idx = i
            if char_count > self.recents_limit:
                half_idx = len(recent_context) - half_idx
                to_embed_context = recent_context[:half_idx]
                recent_context = recent_context[half_idx:]
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
        # TODO properly set k (not 1. 1 is useless.)
        ret_context_timestamp = self.DB.query(channel_id, question, k=3)

        logger.debug(f"len ret_context_timestamp = {len(ret_context_timestamp)}")

        # limit the size of retrieved context (truncate less relevant ones)
        if len(ret_context_timestamp) > 0:
            if len(ret_context_timestamp) > self.retrieval_limit:
                ret_context_timestamp = ret_context_timestamp[:self.retrieval_limit]
            # request actual messages that match the timestamp
            ret_context = await self.DiscordClient.get_message(channel_id, ret_context_timestamp)
        else:
            ret_context = []

        logger.debug(f"Retrieval Done: ({len(ret_context)}|{len(recent_context)})")

        # query llm
        llm_answer = self.LLMClient.query(
            ret_context, recent_context
        )
        
        return llm_answer
    
    # recent_context:List[SimpleMessage]
    async def update(self, channel_id, recent_context:List[SimpleMessage]):
        # documents - a batch of consecutive messages
        # timestamp - t_first, t_last of batch
        # discordClient.set_channel_timestamp(channel_id, timestamp):
        #   set channel's recent timestamp to the last message's timestamp
        
        # max num of chars in batch 
        # if this is smaller than the longest single message,
        # it will be set to that length with warning.
        # (in discord, max chars per message is 2K)
        # TODO where should I assign this?
        batch_size = 2500 
        stride = 500 # approx num of chars that overlap in each batch
        documents:List[str] = []
        timestamps:List[List[datetime.datetime,datetime.datetime]] = []

        # No need to do anything if empty
        if len(recent_context) == 0:
            return

        for ctx in recent_context:
            if len(ctx.content) > batch_size:
                batch_size = len(ctx.content)
                logger.warning(f"batch size smaller than single message. It will be scaled up to fit the longest message({batch_size}).")
                logger.debug(f"msglen > batchsize from {ctx.content[:20]}...")

        
        i = 0
        b_count = 0
        s_count = 0
        docs:List[str] = []

        while True:
            # end of list
            if i >= len(recent_context):
                if len(docs) > 0:
                    documents.append('\n'.join(docs))
                    timestamps.append([t_first,t_last+MINUTE])
                break

            ctx = recent_context[i]

            # starting new docs batch
            if s_count == 0:
                # document this
                docs.append(ctx.content)
                b_count += len(ctx.content)
                t_first = ctx.created_at
                t_last = ctx.created_at
                
                # stride front
                j = i-1
                while j >= 0:
                    ctx0 = recent_context[j]
                    if (len(ctx0.content) + b_count <= batch_size and 
                        len(ctx0.content) + s_count <= stride):

                        docs.insert(0,ctx0.content)
                        s_count += len(ctx0.content)
                        b_count += len(ctx0.content)
                        t_first = ctx0.created_at
                        j -= 1

                    else:
                        s_count += 1 # to indicate that stride_front is done
                        break

                i += 1
         
            # concat to existing docs batch
            else:
                if b_count + len(ctx.content) <= batch_size:
                    docs.append(ctx.content)
                    b_count += len(ctx.content)
                    i += 1

                # batch full, append and reset batch
                else:
                    documents.append('\n'.join(docs))
                    timestamps.append([t_first,t_last+MINUTE])
                    docs = []
                    b_count = 0
                    s_count = 0

        # documents = [r.content for r in recent_context]
        # timestamps = [r.created_at for r in recent_context]

        # TODO - think async situation
        # push to db - not likely to happen at the same time, since messages has to stack up certain amount
        #   even if it happens, it will only cost small increase in computation
        #   since DB only stores timestamps, and actual messages will be fetched once from overlapping timestamps.
        # query from db - might happen while db is being updated
        #   in this case, about-to-be-updated messages are better to be included in the recent_messages
        #   even if they are duplicated
        #   rather than being omitted
        # ==> So, update channel timestamp after the DB update is finished.

        self.DB.push(channel_id, documents, timestamps)
        self.DiscordClient.set_channel_timestamp(channel_id,timestamps[-1][-1]-MINUTE)
        