# Blue on blue bot file
# Handles actually running the bot
import asyncio
import discord
from discord.ext import commands
from blueonblue.config import config
import logging
log = logging.getLogger("blueonblue")

__all__ = ["bot"]

# Define some variables
loop = asyncio.get_event_loop()

# Function to determine bot prefixes
def get_prefix(client, message):
	# Set the prefixes
	prefixes = config["BOT"]["CMD_PREFIXES"]
	
	# Allow users to mention the bot instead of using a prefix
	return commands.when_mentioned_or(*prefixes)(client, message)

intents = discord.Intents.default()
intents.members = True

# Define the bot
bot = commands.Bot(
	command_prefix=get_prefix, # Call the get_prefix function
	description=config["BOT"]["DESC"], # Sets the bot description for the help command
	case_insensitive=True, # Allow commands to be case insensitive
	intents=intents # Enable the members intent
)

# Assign some values to the bot
bot._uptime = None
bot._config = config
bot._guild = None
bot._log = log