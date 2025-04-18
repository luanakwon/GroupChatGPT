import openai
from openai import OpenAI

import json

class MyOpenAIClient(OpenAI):
    def __init__(self,api_key):
        super().__init__(api_key=api_key)
        self.set_username('ChatGPT')
        self._model = "gpt-4.1"
            
    def set_username(self,username):
        self._username = username
        self._system_message_content = \
            f"""You, {self._username}, are a helpful and concise member of a Discord server. 
You will be provided a summary of the previous context, followed by recent messages after the summarized context. 
The last message mentions you. Please reply to the mention and also update the summary to reflect all messages up to your reply.
Respond in JSON format like this: {{"answer": "<your_reply>", "summary": "<updated_summary>"}}
Always respond with a valid JSON object using double quotes. Do not add any commentary outside the JSON."""

    def set_model(self,model):
        self._model = model

    def query_LLM(self, summary, query):
        user_message_content = f"###Previous Summary:\n\n{summary}\n###Recent Messages:\n\n{query}"

        try:
            llm_response = self.responses.create(
                model=self._model,
                instructions=self._system_message_content,
                input=user_message_content
            )
            llm_response = llm_response.output_text
        except (
            openai.BadRequestError,
            openai.AuthenticationError,
            openai.PermissionDeniedError,
            openai.NotFoundError,
            openai.APIConnectionError,
            openai.InternalServerError) as e:
            print(f"Error: {e}")
            raise ConnectionError from e
        except openai.UnprocessableEntityError as e:
            print(f"Error: {e}")
            raise ValueError(e)
        except openai.RateLimitError as e:
            print(f"Error: {e}")
            raise InterruptedError(e)

        try:
            llm_response = json.loads(llm_response)
            answer = llm_response['answer']
            summary = llm_response['summary']
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"LLM returned malformed JSON: {llm_response}") from e

        return answer, summary 
