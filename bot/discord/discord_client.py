from __future__ import annotations
from typing import TYPE_CHECKING

import logging
logger = logging.getLogger(__name__)

import discord
from .simple_message import SimpleMessage
from bot.db.channel_db import ChannelTimestampDB
import datetime
import re

if TYPE_CHECKING:
    from bot.llm.llm_rag import LLM_RAG

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

        # timestamp per channel
        self.TimestampDB:ChannelTimestampDB = ChannelTimestampDB()
        # Module reference
        self.RAG:LLM_RAG = None 
        
    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        self.RAG.LLMClient.set_username(str(self.user))

    async def on_message(self, message: discord.Message):
        # skip self message
        if message.author == self.user:
            return
        
        channel = message.channel

        # 1. Handle messages that mention the bot
        if self.user in message.mentions:
            timestamp = self.TimestampDB.get_memory(channel.id)
            if timestamp is not None:
                timestamp = datetime.datetime.fromisoformat(timestamp)
            try:            
                context = await self.get_unstaged_history(
                    channel=channel, 
                    after=timestamp,
                    limit=10
                )

                llm_answer = await self.RAG.invoke(channel.id, context)

            except Exception as e:
                logger.error(f"ERROR: {e}")
                await channel.send(self.reserved_error_message[0])
                return

            channel.send(llm_answer)
            logger.debug(llm_answer)
            return
        
    # method to set channel's timestamp for discord client.
    # this is called after staged messages are embedded & stored.
    def set_channel_timestamp(self, channel_id:int, timestamp:datetime.datetime):
        self.TimestampDB.set_memory(
            channel_id=channel_id,
            timestamp=timestamp.isoformat())

    async def get_unstaged_history(self, channel_id:int, after=None, limit=10):
        channel = self.get_channel(channel_id)
        context = []
        msg: discord.Message
        async for msg in channel.history(after=after, limit=limit):
            # if message is from self, meaning it is staged
            if msg.author == self.user:
                # regard self-error message as regular message
                if msg.content in self.reserved_error_message:
                    pass
                elif after is None: # after=None -> oldest_first=False
                    # this is the recent self message
                    break
                else: # after=timestamp -> oldest_first=True
                    # this is the oldest self message
                    context = []
                    continue

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
   
            if after is None: # after=None -> oldest_first=False -> append front
                context.insert(0,formatted_message)
            else: # after=timestamp -> oldest_first=True -> append rear
                context.append(formatted_message)

        # TODO resolve unexpected error here: IndexError context[0]
        # async for never looped? logically doesnt make sense (mention should have called this func)
        # probably after is messed up.
        # retry without after?
        # I still have no idea how this happened, and I could not reproduce this error.
        if len(context) == 0:
            logger.error("0 context error")
            logger.error(after)
            logger.error(context)
            if after is None:
                assert(len(context) > 0)
            else:
                return await self.get_unstaged_history(channel,None,limit)

        # compress messages to reduce token
        compressed = [context[0]]
        m0:SimpleMessage
        m1:SimpleMessage
        for m1 in context[1:]:
            m0 = compressed[-1]
            # compress same author,short time window
            if m0.author == m1.author:
                if m0.created_at.isoformat(timespec='minutes') == m1.created_at.isoformat(timespec='minutes'):
                    m0.content += "\n" + m1.content
                    continue
            compressed.append(m1)

        # returns list[SimpleMessage]
        return compressed     

    async def get_message(self, channel_id, timestamps):
        out = []

        # get channel from id
        channel = self.get_channel(channel_id)
        # sort timestamp
        timestamps = iter(sorted(timestamps))
        # use seconds isoformat to compare same-second messages
        iso_tstamp = next(timestamps).isoformat(timespec='seconds')
        # assert(len(timestamps) > 0)

        # loop through message history after the first timestamp
        msg: discord.Message
        async for msg in channel.history(after=datetime.datetime.fromisoformat(iso_tstamp)):
            t_msg = msg.created_at.isoformat(timespec='seconds')
            
            if t_msg < iso_tstamp:
                # proceed to next in the history
                continue
            elif t_msg == iso_tstamp:
                # retrieve message, proceed history
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
                # {
                # 'metadata':[str(msg.author),msg.created_at],
                # 'content':[str(content)]}

                out.append(formatted_message)
            else:
                # proceed to next timestamp in timestamps
                iso_tstamp = next(timestamps).isoformat(timespec='seconds')

        # compress messages to reduce token
        compressed = [out[0]]
        m0:SimpleMessage
        m1:SimpleMessage
        for m1 in out[1:]:
            m0 = compressed[-1]
            # compress same author,short time window
            if m0.author == m1.author:
                if m0.created_at.isoformat(timespec='minutes') == m1.created_at.isoformat(timespec='minutes'):
                    m0.content += "\n" + m1.content
                    continue
            compressed.append(m1)

        return compressed
    
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
