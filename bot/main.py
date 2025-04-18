from bot.config.credentials import DISCORD_TOKEN
from bot.discord.discord_client import MyDiscordClient

# remove deprecated "heychat" command
# once removed, delete this code
from discord import app_commands
async def foo(client):
    client.tree = app_commands.CommandTree(client)
    client.tree.remove_command("heychat")
    await client.tree.sync()
    print('removed heychat')


if __name__ == "__main__":
    client = MyDiscordClient()
    client.run(DISCORD_TOKEN)
    foo(client)
    
