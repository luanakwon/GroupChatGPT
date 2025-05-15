from langchain.chat_models import init_chat_model
import datetime

# TODO 
class LLM_RAG:
    def __init__(self):
        self.DB = TopicDB
        self.DiscordClient

    async def invoke(self, channel_id, recent_context):
        # pick messages in recent 5 minutes as a question for retrieval
        question = []
        t1 = recent_context[-1]['metadata'][1]
        for context in reversed(recent_context):
            if t1 - context['metadata'][1] < datetime.timedelta(minutes=5):
                question.insert(0,context['content'])
        question = "\n".join(question)
        # query db
        ret_context_timestamp = self.DB.topK(channel_id, question, k=1)
        # request actual messages that match the timestamp
        ret_context = await self.DiscordClient.get_message(ret_context_timestamp)
        # query llm
        llm_answer = await self.LLM.query(
            ret_context, recent_context
        )
        self.update(recent_context,llm_answer)
        return llm_answer
    
    async def update(self, recent_context, llm_answer):
        for context in recent_context:
            self.DB.push(context['content'],context['metadata'])
        self.DB.push(
            llm_answer, 
            datetime.datetime.now(datetime.timezone.utc)             
        )
