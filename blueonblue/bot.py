# Blue on blue bot file
# Handles actually running the bot
import asyncio
import discord
from discord.ext import commands

from blueonblue.config import config, init_config

__all__ = ["bot"]

init_config()

# Define some variables
loop = asyncio.get_event_loop()
bot_token = config["BOT"]["TOKEN"] # Grab our bot token from the config file
initial_extensions = config["BOT"]["COGS"] # Initial cogs to load

# Function to determine bot prefixes
def get_prefix(client, message):
	# Set the prefixes
	prefixes = config["BOT"]["CMD_PREFIXES"]
	
	# Allow users to mention the bot instead of using a prefix
	return commands.when_mentioned_or(*prefixes)(client, message)

# Define the bot
bot = commands.Bot(
	command_prefix=get_prefix, # Call the get_prefix function
	description=config["BOT"]["DESC"], # Sets the bot description for the help command
	case_insensitive=True # Allow commands to be case insensitive
)

bot._uptime = None

# Try to load extensions
#print("Loading extensions...")
#for ext in initial_extensions:
#	try:
#		bot.load_extension("cogs." + ext)
#	except Exception as e:
#		print(f'Failed to load extension: {ext}.')
#		traceback.print_exc()
#	else:
#		print(f'Loaded extension: {ext}.')
#print("Extensions loaded.")

# Here we load our extensions(cogs) listed above in [initial_extensions].
#if __name__ == '__main__':
#	for extension in initial_extensions:
#		try:
#			bot.load_extension("cogs." + extension)
#		except Exception as e:
#			print(f'Failed to load extension {extension}.', file=sys.stderr)
#			traceback.print_exc()