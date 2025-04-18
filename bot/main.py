from bot.config.credentials import DISCORD_TOKEN
from bot.discord.discord_client import MyDiscordClient

if __name__ == "__main__":
    client = MyDiscordClient()
    client.run(DISCORD_TOKEN)

    
    
