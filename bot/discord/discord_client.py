from __future__ import annotations
from typing import TYPE_CHECKING, List

import logging
logger = logging.getLogger(__name__)

import discord
from .simple_message import SimpleMessage
import re

if TYPE_CHECKING:
    from bot.llm.llm_client import MyOpenAIClient

# safety limit of messages when fetching chat history with get_unstaged_history()
#   any messages exceeding this limit will never be updated to the DB
#   to prevent, update DB before hitting this limit
HISTORY_FETCH_SAFE_LIMIT = 500

class MyDiscordClient(discord.Client):
    def __init__(self):
        # set intents
        intents = discord.Intents.default()
        intents.message_content = True  # to access message.content
        super().__init__(intents=intents)

        self.hide_flag = "//pss"
        self.reserved_error_message = [
            "Sorry, I'm not available right now.."
        ]

        # Module reference
        self.llm: MyOpenAIClient = None 
        
    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        self.llm.configure(str(self.user))

    async def on_message(self, message: discord.Message):
        # skip self message
        if message.author == self.user:
            return
        
        # start sequence only when mentioned
        if self.user in message.mentions:
            try:
                async with message.channel.typing():
                    recent_messages:List[SimpleMessage] = \
                        await self.fetch_recent_messages(channel_id = message.channel.id, n = 10)
                    mode, val = self.llm.invoke(recent_messages)
                    if mode == 'response':
                        llm_answer = val
                    else: # mode == request
                        # TODO test and reset the value n
                        retrieved_messages:List[SimpleMessage] = \
                            await self.fetch_messages_matching_keywords(channel_id=message.channel.id, keywords=val, n=20)
                        _, llm_answer = self.llm.invoke(recent_messages, retrieved_messages)
            
            except Exception as e:
                logger.error(f"ERROR: {e}")
                await message.channel.send(self.reserved_error_message[0])
                return
            
            await message.channel.send(llm_answer)
            logger.debug(llm_answer)
            return

    async def fetch_recent_messages(self, channel_id:int, n:int):
        channel = self.get_channel(channel_id)
        messages = []
        msg: discord.Message
        async for msg in channel.history(limit=n):
            # process message (nontext, hidden, mention, reply)
            content = convert_nontext2str(msg)
            content = omit_hidden_message(content,self.hide_flag)
            content = replace_mention_id2name(content,msg)
            if msg.type == discord.MessageType.reply and msg.reference:
                try:
                    replied_message = await msg.channel.fetch_message(msg.reference.message_id)
                    replied_author = f"**@{replied_message.author.display_name}**" if replied_message.author else "someone"
                    replied_content = convert_nontext2str(replied_message)
                    replied_content = omit_hidden_message(replied_content, self.hide_flag)
                    replied_content = replace_mention_id2name(replied_content, replied_message)
                    
                    content = f"(in reply to {replied_author}: \"{replied_content}\")\n{content}"
                except Exception as e:
                    logger.error(f"Failed to fetch replied message: {e}")
                    content = f"(in reply to someone: \"\")\n{content}"
                        
            formatted_message = SimpleMessage(
                author=str(msg.author),
                created_at=msg.created_at,
                content=str(content)
            )
   
            messages.append(formatted_message)
        
        # reverse into oldest first
        messages = messages[::-1]

        # compress messages to reduce token
        messages = [m for m in messages if len(m.content) > 0]
        if len(messages) > 0:
            compressed = [messages[0]]
            m0:SimpleMessage
            m1:SimpleMessage
            for m1 in messages[1:]:
                m0 = compressed[-1]
                # compress same author,short time window
                if m0.author == m1.author:
                    if m0.created_at.isoformat(timespec='minutes') == m1.created_at.isoformat(timespec='minutes'):
                        m0.content += "\n" + m1.content
                        continue
                compressed.append(m1)

            # returns list[SimpleMessage]
            return compressed
        else:
            return []    

    async def fetch_messages_matching_keywords(self, channel_id:int, keywords:List[str], n:int):
        channel = self.get_channel(channel_id)
        messages = []
        msg: discord.Message
        async for msg in channel.history(limit=HISTORY_FETCH_SAFE_LIMIT):
            # process message (nontext, hidden, mention, reply)
            content = convert_nontext2str(msg)
            content = omit_hidden_message(content,self.hide_flag)
            content = replace_mention_id2name(content,msg)
            if msg.type == discord.MessageType.reply and msg.reference:
                try:
                    replied_message = await msg.channel.fetch_message(msg.reference.message_id)
                    replied_author = f"**@{replied_message.author.display_name}**" if replied_message.author else "someone"
                    replied_content = convert_nontext2str(replied_message)
                    replied_content = omit_hidden_message(replied_content, self.hide_flag)
                    replied_content = replace_mention_id2name(replied_content, replied_message)
                    
                    content = f"(in reply to {replied_author}: \"{replied_content}\")\n{content}"
                except Exception as e:
                    logger.error(f"Failed to fetch replied message: {e}")
                    content = f"(in reply to someone: \"\")\n{content}"

            # Simple keyword filter
            # TODO - Think. compress->filter vs filter->compress
            # compress->filter
            #   likely to include short messages in between relevant messages
            #   might result in more messages
            #   more to compress
            # filter->compress
            #   less to compress
            #   only include strictly relevant messages
            # conclusion - lets go with compress->filter
            # BUT, fetching to its limit every time would be inefficient
            # so once a certain amount of relavant messages are found, stop fetching
            formatted_message = SimpleMessage(
                author=str(msg.author),
                created_at=msg.created_at,
                content=str(content)
            )
            # if it's the first message, insert
            if len(messages) <= 0:
                messages.insert(0,formatted_message)
            else:
                m0: SimpleMessage = messages[0]
                # if it can be compressed, compress
                if ( 
                        m0.author == formatted_message.author
                        and
                        (
                            m0.created_at.isoformat(timespec='minutes') 
                            ==
                            formatted_message.created_at.isoformat(timespec='minutes')
                        )
                    ):
                    m0.content = formatted_message.content + '\n' + m0.content
                # if not
                else:
                    # check relevance of the existing message
                    is_relevant = False
                    for kw in keywords:
                        if kw in m0.content:
                            is_relevant = True
                            break
                    # if it is relevant, keep it, and insert new
                    if is_relevant:
                        messages.insert(0,formatted_message)
                    # if it is not relevant, pop it, and insert new
                    else:
                        messages[0] = formatted_message

                    # if number of relevant messages (excluding messages[0]) reaches n, return
                    if len(messages)-1 >= n:
                        return messages[1:]
        # even if the number of relevant messages does not reach n, return except messages[0]
        return messages[1:]
                    
# --- message handling functions ---

def convert_nontext2str(message:discord.Message)->str:
    # TODO More sementic aware implemtation later
    parts = []

    # 1. Stickers
    if message.stickers:
        for sticker in message.stickers:
            parts.append(f"[sticker: {sticker.name}]")

    # 2. Attachments
    if message.attachments:
        for att in message.attachments:
            if att.description:
                parts.append(f"[attachment: {desc}]")
            else:
                parts.append("[attachment: unsupported-data]")

    # 3. Embeds (only if not already in content)
    if message.embeds:
        for embed in message.embeds:
            # extract probably useful info
            label = embed.provider.name if embed.provider else 'embed'
            title = getattr(embed, 'title', 'null')
            desc = getattr(embed, 'description', 'null')
            url = getattr(embed, 'url', 'null')
            
            # remove if url is already in content
            if url and message.content:
                pattern = re.compile(fr"{url}\S*")
                for substr in pattern.findall(message.content):
                    message.content = message.content.replace(substr,'')

            # trim down unnecessarily long url to save token
            if len(url) > 50:
                url = url[:100]+'...'

            parts.append(f"[{label}: title-{title} desc-{desc} url-{url}]")

    # 4. Text content
    if message.content:
        parts.append(message.content.strip())

    return "\n".join(parts).strip()

def omit_hidden_message(content:str,flag:str)->str:
    # omit hidden message
    flag_idx = content.find(flag)
    if flag_idx >= 0:
        content = content[:flag_idx]
    return content


def replace_mention_id2name(content:str, message:discord.Message):
    replacements = {
        "@everyone":"**@everyone**",
        "@here":"**@here**"
    }

    # Users: <@123> or <@!123>
    for user in message.mentions:
        mention_str = f"<@{user.id}>"
        mention_str_nick = f"<@!{user.id}>"
        replacements[mention_str] = f"**@{user.display_name}**"
        replacements[mention_str_nick] = f"**@{user.display_name}**"

    # Channels: <#123>
    for channel in message.channel_mentions:
        replacements[f"<#{channel.id}>"] = f"**#{channel.name}**"

    # Roles: <@&123>
    for role in message.role_mentions:
        replacements[f"<@&{role.id}>"] = f"**@{role.name}**"

    # Replace all in content
    for k, v in replacements.items():
        content = content.replace(k, v)

    return content
