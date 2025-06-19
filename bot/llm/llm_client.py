from __future__ import annotations
from typing import TYPE_CHECKING, List

import logging
logger = logging.getLogger(__name__)

import openai
from openai import OpenAI

if TYPE_CHECKING:
    from bot.discord.simple_message import SimpleMessage

class MyOpenAIClient(OpenAI):
    def __init__(self,api_key):
        super().__init__(api_key=api_key)
        self.set_username('ChatGPT')
        self._model = "gpt-4.1"

    # no more summary, only answer is needed, now the model is provided retrieved context
    def set_username(self,username):
        self._username = username
        self._system_message_content = \
            f"""You, {self._username}, are a helpful and concise member of a Discord server. 
You will be provided a retrieved relative context, followed by some recent context as "retrieved-context", "recent-context", respectively.
Retrieved-context is a list of related messages retrieved by RAG. Recent-context is a list of most recent messages.
The last message mentions you. Please reply to the mention in plain text. Your entire response will be considered the reply to the mention."""

    def set_model(self,model):
        self._model = model

    def query(self,
              retreived_context: List[SimpleMessage], 
              recent_context: List[SimpleMessage]):
        # stringify both list
        ret_str = ""
        msg:SimpleMessage
        for msg in retreived_context:
            ret_str += msg.toJSON() + "\n"
        rec_str = ""
        for msg in recent_context:
            rec_str += msg.toJSON() + "\n"
        # create llm response (with system message)
        try:
            llm_response = self.responses.create(
                model=self._model,
                instructions=self._system_message_content,
                input=f"# retrieved-context\n{ret_str}\n# recent-context\n{rec_str}\n"
            )
            llm_response = llm_response.output_text
        except (
            openai.BadRequestError,
            openai.AuthenticationError,
            openai.PermissionDeniedError,
            openai.NotFoundError,
            openai.APIConnectionError,
            openai.InternalServerError) as e:
            logger.error(f"Error: {e}")
            raise ConnectionError from e
        except openai.UnprocessableEntityError as e:
            logger.error(f"Error: {e}")
            raise ValueError(e)
        except openai.RateLimitError as e:
            logger.error(f"Error: {e}")
            raise InterruptedError(e)
        
        # return answer
        return llm_response
    
    def get_embedding(self, texts):
        inputs = [txt for txt in texts if len(txt) > 0]
        if len(texts) != len(inputs):
            logger.warning(f"from get_embedding - unexpected empty string found in {texts}")

        response = self.embeddings.create(
            model='text-embedding-3-small',
            input=inputs,
            encoding_format='float'
        )
        return [e.embedding for e in response.data]