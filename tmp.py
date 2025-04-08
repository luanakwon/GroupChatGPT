from credentials import TOKEN

import discord
from discord import app_commands

last_processed_id = None

class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # Needed to access message.content
        super().__init__(intents=intents)
        
        self.last_staged = {}
        self.unstaged_count = {}
        

    # async def setup_hook(self):
    #     # Sync slash commands when bot is ready
    #     # await self.tree.sync()
        # print("Slash commands synced.")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        content = message.content.strip()

        # 1. Handle messages that mention the bot
        if self.user in message.mentions:
            user_msg = content.replace(f"<@{self.user.id}>", "").strip()
            # await message.channel.send(f"AI heard: {user_msg}")
            # print(f"Message ID: {message.id}")
            # print(f"Author: {message.author} ({message.author.id})")
            # print(f"Channel: {message.channel.name} ({message.channel.id})")
            # print(f"Guild: {message.guild.name if message.guild else 'DM'}")
            # print(f"Created at: {message.created_at}")
            # print(f"Content: {message.content}")
            # print("-----")
            context = get_unstaged_history(channel, after, hide_flag)
            LLM_response = query_LLM(context,user_msg)
            await message.channel.send(LLM_response)
            # Optionally: mark this message ID as excluded from context
            return

        # # 2. Handle "pss" command
        # if content.lower().startswith("pss"):
        #     secret_msg = content[3:].strip()
        #     print(f"secretly eavesdropped {secret_msg}")
        #     await message.channel.send("🤫 Noted. This won’t be shared with AI.")
        #     # Optionally: mark this message ID as excluded from context
        #     return
        
        if content.lower().startswith("read_history"):
            context = []
            print(self.timestamps)
            async for msg in message.channel.history(after=self.timestamps[0], limit=10):
                if msg.content.lower().startswith('pss'):
                    continue  # Skip this one
                context.append(msg)
            print(context)


        else:
            print("background listening")
            print(content)
            print(message.mentions)
            self.timestamps.append(message.created_at)


client = MyClient()

# # Slash command: /heychat
# @client.tree.command(name="heychat", description="Trigger the AI bot")
# async def heychat(interaction: discord.Interaction):
#     await interaction.response.send_message("helloworld")


client.run(TOKEN)
