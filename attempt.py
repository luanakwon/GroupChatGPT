from credentials import TOKEN, OPENAI_API_KEY

import discord
import openai
from openai import OpenAI

import datetime
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

    @MyOpenAIClient.error_handler
    def query_LLM(self, summary, query):
        user_message_content = f"###Previous Summary:\n\n{summary}\n###Recent Messages:\n\n{query}"

        llm_response = self.responses.create(
            model=self._model,
            instructions=self._system_message_content,
            input=user_message_content
        )
        llm_response = llm_response.output_text

        try:
            llm_response = json.loads(llm_response)
            answer = llm_response['answer']
            summary = llm_response['summary']
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"LLM returned malformed JSON: {llm_response}") from e
        
        
        # llm_response = '{"answer":"fake_ai_answer","summary":"fake_ai_summary"}'
        # llm_response = json.loads(llm_response)

        # answer = llm_response['answer']
        # summary = llm_response['summary']

        return answer, summary
    
    def error_handler(self,func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (
                openai.BadRequestError,
                openai.AuthenticationError,
                openai.PermissionDeniedError,
                openai.NotFoundError,
                openai.APIConnectionError,
                openai.InternalServerError) as e:
                print(f"Error: {e}")
                raise ConnectionError(e)
            except openai.UnprocessableEntityError as e:
                print(f"Error: {e}")
                raise ValueError(e)
            except openai.RateLimitError as e:
                print(f"Error: {e}")
                raise InterruptedError(e)
        return wrapper
    
    error_handler = staticmethod(error_handler)

# a = [{'a':'aa','b':'bb'},{'a':'cc'}]
# print(json.dumps(a))
# exit()

class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Needed to access message.content
        intents.members = True # Needed to access guild.fetch_members
        super().__init__(intents=intents)
        
        # following 3 dicts can be switched to DB later
        self.summarized_context = {}
        self.last_staged = {}
        self.unstaged_count = {}

        self.hide_flag = "//pss"

        self.llm = MyOpenAIClient(OPENAI_API_KEY)
        self.llm.set_model('gpt-4.1')
        
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        self.member_dict = {}
        for guild in self.guilds:
            async for member in guild.fetch_members(limit=None):  # fetch all
                self.member_dict[member.id] = member.display_name

        self.llm.set_username(str(self.user))
        

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        channel = message.channel
        c_id = channel.id

        # 1. Handle messages that mention the bot
        if self.user in message.mentions:
            print('start await history')

            summary = self.summarized_context.get(c_id, '')

            context = await self.get_unstaged_history(
                channel=channel, 
                limit=10
            )

            llm_answer, llm_summary = query_LLM(
                summary = summary,
                query=context)

            await channel.send(llm_answer)
            self.last_staged[c_id] = datetime.datetime.now(datetime.timezone.utc)
            self.unstaged_count[c_id] = 0
            self.summarized_context[c_id] = llm_summary
            return
        
        # increase count for every other message
        else:
            self.unstaged_count[c_id] = self.unstaged_count.get(c_id,0) + 1

    async def get_unstaged_history(self, channel, limit=10):
        context = []
        after = self.last_staged.get(channel.id, None)
        async for msg in channel.history(after=after, limit=limit):
            # if message is from self, meaning it is staged
            if msg.author == self.user:
                if after is None: # after=None -> oldest_first=False
                    # this is the recent self message
                    break
                else: # after=timestamp -> oldest_first=True
                    # this is the oldest self message
                    self.last_staged[channel.id] = msg.created_at
                    self.unstaged_count[channel.id] = 0
                    context = []
                    continue
            # non-text message : skip for now
            if not msg.content:
                continue
            # skip hidden message
            if msg.content.lower().startswith(self.hide_flag):
                continue 
            
            # --- for regular messages ---

            # replace mention_id with mention_name
            content = str(msg.content)
            s0 = 0
            while s0 < len(content):
                # later switch to regex parsing r"<@!?(?P<id>\d+)>"
                i0 = content.find('<@',s0)
                if i0 >= 0:
                    i1 = content.find('>',i0)
                    if i1 > i0:
                        mem_id = int(content[i0+2:i1])
                        mem_name = self.member_dict.get(mem_id,mem_id)
                        content = content[:i0]+f"**@{mem_name}**"+content[i1+1:]
                        s0 = i1+1
                        continue
                break
            
            formatted_message = {
                'metadata':[str(msg.author),msg.created_at.strftime('%y%m%d %H:%M %Z')],
                'content':[str(content)]}
            if after is None: # after=None -> oldest_first=False -> append front
                context.insert(0,formatted_message)
            else: # after=timestamp -> oldest_first=True -> append rear
                context.append(formatted_message)

        print(context)

        # compress messages to reduce token
        compressed = [context[0]]
        for m1 in context[1:]:
            m0 = compressed[-1]
            # compress same author,short time window
            if m0['metadata'][0] == m1['metadata'][0]:
                if m0['metadata'][1] == m1['metadata'][1]:
                    m0['content'] += m1['content']
                    continue
            compressed.append(m1)

        print(compressed)

        return json.dumps(compressed)

    def query_LLM(self, summary, query):
        system_message_content = \
f"""You, {self.user}, are a helpful and concise member of a Discord server. 
You will be provided a summary of the previous context, followed by recent messages after the summarized context. 
The last message mentions you. Please reply to the mention and also update the summary to reflect all messages up to your reply.
Respond in JSON format like this: {{"answer": "<your_reply>", "summary": "<updated_summary>"}}
Always respond with a valid JSON object using double quotes. Do not add any commentary outside the JSON."""
        user_message_content = \
f"""Previous Summary:
{summary}
Recent Messages:
{query}
"""
        llm_response = openai.ChatCompletion.create(
            model=self.llm,
            messages=[
                {"role": "system", "content": system_message_content},
                {"role": "user", "content": user_message_content}
            ],
            temperature=0.7
        )
        llm_response = llm_response["choices"][0]["message"]["content"]
        try:
            llm_response = json.loads(llm_response)
            answer = llm_response['answer']
            summary = llm_response['summary']
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"LLM returned malformed JSON: {llm_response}") from e
        
        # llm_response = "llm_response_create(prompt)"
        llm_response = '{"answer":"fake_ai_answer","summary":"fake_ai_summary"}'
        llm_response = json.loads(llm_response)

        answer = llm_response['answer']
        summary = llm_response['summary']

        return answer, summary

client = MyClient()
client.run(TOKEN)

# # Slash command: /heychat
# @client.tree.command(name="heychat", description="Trigger the AI bot")
# async def heychat(interaction: discord.Interaction):
#     await interaction.response.send_message("helloworld")


            # await message.channel.send(f"AI heard: {user_msg}")
            # print(f"Message ID: {message.id}")
            # print(f"Author: {message.author} ({message.author.id})")
            # print(f"Channel: {message.channel.name} ({message.channel.id})")
            # print(f"Guild: {message.guild.name if message.guild else 'DM'}")
            # print(f"Created at: {message.created_at}")
            # print(f"Content: {message.content}")
            # print("-----")

                    # if content.lower().startswith("read_history"):
        #     context = []
        #     print(self.timestamps)
        #     async for msg in message.channel.history(after=self.timestamps[0], limit=10):
        #         if msg.content.lower().startswith('pss'):
        #             continue  # Skip this one
        #         context.append(msg)
        #     print(context)

