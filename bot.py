import discord
import json
from settings import config
#import requests
#import datetime
#import asyncio
#import configparser
import sys, traceback
from discord.ext import commands

# Grab our bot token from the config file
bot_token = config["BOT"]["TOKEN"]

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

initial_extensions = config["BOT"]["COGS"]
# Here we load our extensions(cogs) listed above in [initial_extensions].
if __name__ == '__main__':
	for extension in initial_extensions:
		try:
			bot.load_extension(extension)
		except Exception as e:
			print(f'Failed to load extension {extension}.', file=sys.stderr)
			traceback.print_exc()

@bot.event  # event decorator/wrapper. More on decorators here: https://pythonprogramming.net/decorators-intermediate-python-tutorial/
async def on_ready():  # method expected by client. This runs once when connected
	print(f'We have logged in as {bot.user}')  # notification of login.
	
	for server in bot.guilds:
		if server.name == "Super's Notes":
			break
	
	for channel in server.channels:
		if channel.name == "bot-test":
			break
	
	print(channel.id)
	await channel.send("Connected")

@bot.event
async def on_message(message):  # Event that triggers on each message
	await bot.process_commands(message) # This line needs to be here for commands to work

bot.run(bot_token, bot=True, reconnect=True) # Run the bot