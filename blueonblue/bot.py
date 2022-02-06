import discord
from discord.ext import commands
import slash_util
import asqlite

import configparser
from datetime import datetime

import sys, traceback

import logging
log = logging.getLogger("blueonblue")

__all__ = ["bot", "BlueonBlueBot"]

class BlueonBlueBot(slash_util.Bot):
	def __init__(self):
		# Set up our config
		self.config = configparser.ConfigParser(allow_no_value=True)

		# Set default values
		self.config.read_dict({
			"CORE": {
				"prefix": "$$",
				"bot_token": None
			},
			"COGS": {}
		})

		# Read local config file
		self.config.read("config/config.ini")

		# Write config back to disk
		self.write_config()

		# Set up our intents
		intents = discord.Intents.default()
		intents.members = True

		super().__init__(
			command_prefix = commands.when_mentioned_or(self.config["CORE"].get("prefix","$$")),
			description = "Blue on Blue",
			case_insensitive = True,
			intents = intents
		)

		# Load extensions
		extensions = []
		for cog in self.config["COGS"]:
			if self.config["COGS"].getboolean(cog, fallback=True):
				extensions.append(cog)
		for ext in ["botcontrol","users"]:
			if ext in extensions:
				extensions.remove(ext)
		#extensions.insert(0,"users") # Always load users second
		extensions.insert(0,"botcontrol") # Always load BotControl first

		for ext in extensions:
			try:
				self.load_extension("cogs." + ext)
			except Exception as e:
				log.exception(f"Failed to load extension: {ext}")
			else:
				log.info(f"Loaded extension: {ext}")
		log.info("Extensions loaded")

	def write_config(self):
		with open("config/config.ini", "w") as configfile:
			self.config.write(configfile)

	# Rewritten start function to connect to sqlite db
	async def blueonblue_start(self):
		async with asqlite.connect("data/blueonblue.sqlite3") as connection:
			self.db_connection = connection
			await self.start(self.config["CORE"].get("bot_token"), reconnect=True)

	# On connect. Runs immediately upon connecting to Discord
	async def on_connect(self):
		if not hasattr(self, "_uptime"):
			log.info("Connected to Discord")

	# On ready. Runs when bot is connected to Discord, and has received server info
	# Can run multiple times if the bot is disconnected at any point
	async def on_ready(self):
		if hasattr(self, "_uptime"):
			return

		self._uptime = datetime.utcnow()

		log.info(f"Connected to servers: {self.guilds}")
		log.info("Blue on Blue ready.")

	# On message. Runs every time the bot receives a new message
	async def on_message(self, message):
		if message.author.bot:
			return
		await self.process_commands(message) # This needs to be here for commands to work

	# On command completion. Runs every time a command is completed
	async def on_command_completion(self, ctx):
		log.debug(f"Command {ctx.command} invoked by {ctx.author.name}")

	# On command error. Runs whenever a command fails (for any reason)
	async def on_command_error(self, ctx, error, error_force=False):
		"""The event triggered when an error is raised while invoking a command.
		ctx   : Context
		error : Exception"""

		# Allow commands to override default error handling behaviour
		# To continue to this error handler from a command-specific handler, use the following code
		# await ctx.bot.on_command_error(ctx, getattr(error, "original", error), error_force=True)
		if not error_force:
			if hasattr(ctx.command, "on_error"):
				return

			#if ctx.cog:
			#	if commands.Cog._get_overridden_method(ctx.cog.cog_command_error) is not None:
			#		return

		ignored = ()

		# Allows us to check for original exception raised and sent to CommandInvokeError
		# If nothing is found. We keep the exception passed to on_command_error.
		# Code taken from here: https://gist.github.com/EvieePy/7822af90858ef65012ea500bcecf1612
		error = getattr(error,"original",error)

		# Stop here if the error is in the ignored list
		if isinstance(error,ignored):
			return

		elif isinstance(error, commands.MissingRequiredArgument):
			await ctx.send(f"{ctx.author.mention}, you're missing some arguments.")
			await ctx.send_help(ctx.command)

		elif isinstance(error, commands.ArgumentParsingError):
			await ctx.send_help(ctx.command)

		elif isinstance(error, commands.UserInputError):
			await ctx.send_help()

		elif isinstance(error, commands.CommandInvokeError):
			await ctx.send(f"Error in command `{ctx.command.qualified_name}`. Please check the logs for details.")
			log.exception(f"Ignoring exception in command {ctx.command}:")

		elif isinstance(error, commands.CommandOnCooldown):
			await ctx.send(f"The command `{ctx.command}` is on cooldown. Try again in {round(error.retry_after)} seconds.")

		elif isinstance(error, commands.NoPrivateMessage):
			await ctx.send("That command cannot be used in private messages.")

		# Channel and user unauthorized goes here

		elif isinstance(error, commands.NotOwner):
			await ctx.send(f"{ctx.author.mention}, you are not authorized to use the command `{ctx.command}`.")

		# If we don't have a handler for that error type, execute default error code.
		else:
			log.exception(f"Ignoring exception in command {ctx.command}:")
			traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

bot = BlueonBlueBot()
