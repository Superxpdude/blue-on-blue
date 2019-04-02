import discord
import json
from settings import config
#import requests
#import datetime
#import asyncio
#import configparser
import sys, traceback
from discord.ext import commands
from blueonblue.bot import bot

# Grab our bot token from the config file
bot_token = config["BOT"]["TOKEN"]

## Define the prefix function
#def get_prefix(client, message):
#	# Set the prefixes
#	prefixes = config["BOT"]["CMD_PREFIXES"]
#	
#	# Uncomment to allow for different prefixes in PMs
#	# if not message.guild:
#	#	#prefixes = ['$$']
#	
#	# Allow users to mention the bot instead of using a prefix
#	return commands.when_mentioned_or(*prefixes)(client, message)
#
## Define the bot
#bot = commands.Bot(
#	command_prefix=get_prefix, # Call the get_prefix function
#	description=config["BOT"]["DESC"], # Sets the bot description for the help command
#	case_insensitive=True # Allow commands to be case insensitive
#)

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

# Error handling event
@bot.event
async def on_command_error(ctx,error):
	"""The event triggered when an error is raised while invoking a command.
	ctx   : Context
	error : Exception"""
	
	# This prevents any commands with local handlers being handled here in on_command_error.
	if hasattr(ctx.command, "on_error"):
		return
	
	ignored = (commands.UserInputError)
	
	# Allows us to check for original exception raised and sent to CommandInvokeError
	# If nothing is found. We keep the exception passed to on_command_error.
	# Code taken from here: https://gist.github.com/EvieePy/7822af90858ef65012ea500bcecf1612
	error = getattr(error,"original",error)
	
	# Stop here if the error is in the ignored list
	if isinstance(error,ignored):
		return
	
	elif isinstance(error, commands.CommandNotFound):
		return await ctx.send("%s, you have typed an invalid command. You can use %shelp to view the command list." % (ctx.author.mention, ctx.prefix))
	
	# If we don't have a handler for that error type, execute the default error code.
	else:
		print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
		traceback.print_exception(type(exception), exception, exception.__traceback__, file=sys.stderr)

bot.run(bot_token, bot=True, reconnect=True) # Run the bot