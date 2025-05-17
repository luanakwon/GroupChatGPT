import datetime
from bot.db.vector_db import Topic_VDB
from bot.discord.discord_client import MyDiscordClient
from llm.llm_client import MyOpenAIClient

class LLM_RAG:
    def __init__(self, retrieval_limit):
        self.retrieval_limit = retrieval_limit
        self.DB: Topic_VDB = None
        self.DiscordClient : MyDiscordClient = None
        self.LLMClient: MyOpenAIClient = None

    async def invoke(self, channel_id, recent_context):
        # pick messages in recent 5 minutes as a question for retrieval
        question = []
        t1 = recent_context[-1]['metadata'][1]
        for context in reversed(recent_context):
            if t1 - context['metadata'][1] < datetime.timedelta(minutes=5):
                question.insert(0,context['content'])
        question = "\n".join(question)

        # query db
        ret_context_timestamp = self.DB.query(channel_id, question, k=1)

        # limit the size of retrieved context
        if len(ret_context_timestamp) > 0:
            if len(ret_context_timestamp) > self.retrieval_limit:
                ret_context_timestamp = ret_context_timestamp[:self.retrieval_limit]
            # request actual messages that match the timestamp
            ret_context = await self.DiscordClient.get_message(ret_context_timestamp)
        else:
            ret_context = []

        # query llm
        llm_answer = await self.LLMClient.query(
            ret_context, recent_context
        )
        
        # update DB
        self.update(channel_id, recent_context, llm_answer)
        return llm_answer
    
    async def update(self, channel_id, recent_context, llm_answer):
        documents = [r['content'] for r in recent_context]
        documents.append(llm_answer)
        timestamps = [r['metadata'][1] for r in recent_context]
        timestamps.append(datetime.datetime.now(datetime.timezone.utc))

        self.DB.push(channel_id, documents, timestamps)
