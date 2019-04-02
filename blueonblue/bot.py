import discord
from settings import config
from discord.ext import commands

# Bot definition moved to this file so that we can import it later if needed.

# Define the prefix function
def get_prefix(client, message):
	# Set the prefixes
	prefixes = config["BOT"]["CMD_PREFIXES"]
	
	# Uncomment to allow for different prefixes in PMs
	# if not message.guild:
	#	#prefixes = ['$$']
	
	# Allow users to mention the bot instead of using a prefix
	return commands.when_mentioned_or(*prefixes)(client, message)

# Define the bot
bot = commands.Bot(
	command_prefix=get_prefix, # Call the get_prefix function
	description=config["BOT"]["DESC"], # Sets the bot description for the help command
	case_insensitive=True # Allow commands to be case insensitive
)