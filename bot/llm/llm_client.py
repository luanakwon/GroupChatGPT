from __future__ import annotations
from typing import TYPE_CHECKING, List, Dict

import logging
logger = logging.getLogger(__name__)

import openai
from openai import OpenAI
import json
from . import prompt

if TYPE_CHECKING:
    from bot.discord.simple_message import SimpleMessage

class MyOpenAIClient(OpenAI):
    def __init__(self,api_key):
        super().__init__(api_key=api_key)
        self.configure('ChatGPT')
        self._model = "gpt-4.1"

    # no more summary, only answer is needed, now the model is provided retrieved context
    def configure(self,username):
        self._username = username
        self._system_message_first_query = prompt.SYSTEM_MESSAGE_RECENT_ONLY(username)
        self._system_message_second_query = prompt.SYSTEM_MESSAGE_RECENT_N_RETRIEVED(username)

    def invoke(self, 
               recent_messages: List[SimpleMessage],
               retrieved_messages: List[SimpleMessage] = None):
        # mode 1. invoke(recent)->
        # query llm, and return response/request
        # mode 2. invoke(recent, retrieved)
        # query llm, return response
        if retrieved_messages is None:
            mode = 0
        else: 
            mode = 1
        
        # stringify messages
        msg:SimpleMessage
        rec_str = ""
        for msg in recent_messages:
            rec_str += msg.toJSON() + "\n"

        if mode == 1:
            ret_str = ""
            for msg in retrieved_messages:
                ret_str += msg.toJSON() + '\n'
            
        # query llm 
        # expected answer 1: {"respond_user":MESSAGE}
        # expected answer 2: {"request_system":KEYWORDS}
        if mode == 0:
            res_dict = self._query_0(rec_str)
            if "respond_user" in res_dict:
                out_mode= 'response'
                out_val = res_dict['respond_user']
            elif "request_system" in res_dict:
                out_mode = 'request'
                out_val = res_dict['request_system']
            else:
                raise ValueError(f"LLM returned malformed JSON: {res_dict}")
        else:
            res_str = self._query_1(ret_str,rec_str)
            out_mode='response'
            out_val=res_str
            
        return out_mode, out_val
    
    def set_model(self,model):
        self._model = model

    def _query_0(self,
              rec_str:str) -> Dict:
        # create llm response (with system message)
        try:
            llm_response = self.responses.create(
                model=self._model,
                instructions=self._system_message_first_query,
                input=f"# recent-context\n{rec_str}\n"
            )
            out = llm_response.output_text
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
        
        # convert response to dict
        try:
            out_dict:Dict = json.loads(out)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned malformed JSON: {llm_response}") from e

        # return dict response
        return out_dict

    def _query_1(self,
              ret_str: str, 
              rec_str: str):
        # create llm response (with system message)
        try:
            llm_response = self.responses.create(
                model=self._model,
                instructions=self._system_message_second_query,
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