import discord

from bot.config.credentials import OPENAI_API_KEY
from bot.llm.llm_client import MyOpenAIClient
from bot.db.channel_db import ChannelMemoryDB

import datetime
import json

class MyDiscordClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Needed to access message.content
        intents.members = True # Needed to access guild.fetch_members
        super().__init__(intents=intents)
        
        # following 3 dicts can be switched to DB later
        self.db = ChannelMemoryDB()

        self.hide_flag = "//pss"

        self.llm = MyOpenAIClient(OPENAI_API_KEY)
        self.llm.set_model('gpt-4.1')

        self.reserved_error_message = [
            "Sorry, I'm not available right now.."
        ]
        
    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        self.member_dict = {}
        for guild in self.guilds:
            async for member in guild.fetch_members(limit=None):  # fetch all
                self.member_dict[member.id] = member.display_name

        self.llm.set_username(str(self.user))
        

    async def on_message(self, message: discord.Message):
        # skip self message
        if message.author == self.user:
            return

        channel = message.channel
        c_id = channel.id

        # 1. Handle messages that mention the bot
        if self.user in message.mentions:
            db_row = self.db.get_memory(c_id)
            if db_row is None:
                timestamp = None
                summary = ''
            else:
                timestamp = datetime.datetime.fromisoformat(db_row[0])
                summary = db_row[1]
            
            # summary = self.summarized_context.get(c_id, '')
            context = await self.get_unstaged_history(
                channel=channel, 
                after=timestamp,
                limit=10
            )

            try:
                llm_answer, llm_summary = self.llm.query_LLM(
                    summary = summary,
                    query=context)
            except BaseException as e:
                print(f"ERROR: {e}")
                await channel.send(self.reserved_error_message[0])
                return

            await channel.send(llm_answer)
            self.db.set_memory(c_id,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
                llm_summary)

            # self.last_staged[c_id] = datetime.datetime.now(datetime.timezone.utc)
            # self.summarized_context[c_id] = llm_summary

            print(datetime.datetime.now(datetime.timezone.utc).isoformat())
            print(summary, context, llm_answer, llm_summary)

            return

    async def get_unstaged_history(self, channel, after=None, limit=10):
        context = []
        async for msg in channel.history(after=after, limit=limit):
            # if message is from self, meaning it is staged
            if msg.author == self.user:
                # regard error message as regular message
                if msg.content in self.reserved_error_message:
                    pass
                elif after is None: # after=None -> oldest_first=False
                    # this is the recent self message
                    break
                else: # after=timestamp -> oldest_first=True
                    # this is the oldest self message
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

        return json.dumps(compressed)