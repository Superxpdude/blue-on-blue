import aiohttp
import discord
from discord.ext import commands
import slash_util
import asqlite

import configparser
from datetime import datetime

import sys, traceback

from . import checks

import logging
log = logging.getLogger("blueonblue")

__all__ = ["BlueOnBlueBot", "debugServerID"]

class BlueOnBlueBot(slash_util.Bot):
	def __init__(self):
		# Set up our core config
		self.config = configparser.ConfigParser(allow_no_value=True)
		# Set default values
		self.config.read_dict({
			"CORE": {
				"prefix": "$$",
				"bot_token": None,
				"debug_server": -1
			},
			"STEAM": {
				"api_token": None
			},
			"GOOGLE": {
				"api_file": "data/google_api.json"
			}
		})
		# Read local config file
		self.config.read("config/config.ini")
		# Write config back to disk
		self.write_config()

		# Set up our server config
		self.serverConfig = configparser.ConfigParser(allow_no_value=True)
		# Read local config file
		self.serverConfig.read("config/serverconfig.ini")
		# Set default values
		self.serverConfig.read_dict({
			"DEFAULT": {
				"channel_bot": -1,
				"channel_mod_activity": -1,
				"channel_check_in": -1,
				"channel_mission_audit": -1,
				"role_admin": -1,
				"role_moderator": -1,
				"role_member": -1,
				"role_jail": -1,
				"role_gold": -1,
				"steam_group_id": -1,
				"group_apply_url": None,
				"mission_sheet_key": None,
				"mission_worksheet": "Schedule",
				"mission_wiki_url": None
			}
		})
		# Write serverconfig back to disk
		self.write_serverConfig()

		# Store our "debug server" value for slash command testing
		self.slashDebugID = None
		debugServerID = self.config.getint("CORE", "debug_server", fallback = -1)
		if debugServerID > 0: # If we have an ID present
			self.slashDebugID = debugServerID

		# Database variables for type hinting
		self.db_connection: asqlite.Connection = None

		# Set up an aioHTTP session
		self.http_session: aiohttp.ClientSession = aiohttp.ClientSession()

		# Set up our intents
		intents = discord.Intents.default()
		intents.members = True

		super().__init__(
			command_prefix = commands.when_mentioned_or(self.config.get("CORE", "prefix", fallback="$$")),
			description = "Blue on Blue",
			case_insensitive = True,
			intents = intents
		)

		# Load extensions
		# Botcontrol and users must be first and second respectively
		self.initial_extensions = [
			"botcontrol",
			"users",
			"chatfilter",
			"gold",
			"jail",
			"missions",
			"pings",
			"verify"
		]

		# extensions = []
		# for cog in self.config["COGS"]:
		# 	if self.config["COGS"].getboolean(cog, fallback=True):
		# 		extensions.append(cog)
		# for ext in ["botcontrol","users"]:
		# 	if ext in extensions:
		# 		extensions.remove(ext)
		# extensions.insert(0,"users") # Always load users second
		# extensions.insert(0,"botcontrol") # Always load BotControl first

		# for ext in self.initial_extensions:
		# 	try:
		# 		self.load_extension("cogs." + ext)
		# 	except Exception as e:
		# 		log.exception(f"Failed to load extension: {ext}")
		# 	else:
		# 		log.info(f"Loaded extension: {ext}")
		# log.info("Extensions loaded")

	def write_config(self):
		"""Write the current bot config to disk"""
		with open("config/config.ini", "w") as configFile:
			self.config.write(configFile)

	def write_serverConfig(self):
		"""Write the current server configs to disk"""
		with open("config/serverconfig.ini", "w") as configFile:
			self.serverConfig.write(configFile)

	# Override the start function to connect to the sqlite db
	async def start(self, *args, **kwargs):
		async with asqlite.connect("data/blueonblue.sqlite3") as connection:
			self.db_connection = connection
			# Load our extensions
			for ext in self.initial_extensions:
				try:
					self.load_extension("cogs." + ext)
				except Exception as e:
					log.exception(f"Failed to load extension: {ext}")
				else:
					log.info(f"Loaded extension: {ext}")
			log.info("Extensions loaded")
			# Start the bot
			await super().start(*args, **kwargs)

	# On connect. Runs immediately upon connecting to Discord
	async def on_connect(self):
		if not hasattr(self, "_uptime"):
			log.info("Connected to Discord")

	# On ready. Runs when bot is connected to Discord, and has received server info
	# Can run multiple times if the bot is disconnected at any point
	async def on_ready(self):
		if hasattr(self, "_uptime"):
			return

		# Ensure that we have a config section for each server that we're in
		for g in self.guilds:
			if not self.serverConfig.has_section(str(g.id)):
				self.serverConfig.add_section(str(g.id))
		self.write_serverConfig()

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
	async def on_command_error(self, ctx: commands.Context, error, error_force=False):
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

		elif isinstance(error, checks.ChannelUnauthorized):
			channels = []
			for c in error.channels:
				ch = ctx.guild.get_channel(c)
				if ch is not None:
					channels.append(ch.mention)

			if len(channels) > 1:
				message = f"{ctx.author.mention}, the command `{ctx.command.qualified_name}` can only be used in the following channels: "
			elif len(channels) == 1:
				message = f"{ctx.author.mention}, the command `{ctx.command.qualified_name}` can only be used in the following channel: "
			else:
				message = f"{ctx.author.mention}, the command `{ctx.command.qualified_name}` cannot be used in this channel."

			# Add the channel idenfiers to the string
			message += ", ".join(channels)

			await ctx.send(message)

		elif (isinstance(error, checks.UserUnauthorized)) or (isinstance(error, commands.NotOwner)):
			await ctx.send(f"{ctx.author.mention}, you are not authorized to use the command `{ctx.command}`.")

		# If we don't have a handler for that error type, execute default error code.
		else:
			log.exception(f"Ignoring exception in command {ctx.command}:")
			traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

	# On slash command error
	async def slash_command_error(self, ctx: slash_util.Context, error):
		"""The event triggered when an error is raised while invoking a slash command.
		ctx   : Context
		error : Exception"""
		if (isinstance(error, checks.UserUnauthorized)) or (isinstance(error, commands.NotOwner)):
			await ctx.send(f"You are not authorized to use the command `{ctx.command}`.", ephemeral=True)

		elif isinstance(error, checks.ChannelUnauthorized):
			channels = []
			for c in error.channels:
				ch = ctx.guild.get_channel(c)
				if ch is not None:
					channels.append(ch.mention)

			if len(channels) > 1:
				message = f"The command `{ctx.command.name}` can only be used in the following channels: "
			elif len(channels) == 1:
				message = f"The command `{ctx.command.name}` can only be used in the following channel: "
			else:
				message = f"The command `{ctx.command.name}` cannot be used in this channel."

			# Add the channel idenfiers to the string
			message += ", ".join(channels)

			await ctx.send(message, ephemeral=True)

		# Generic handler
		else:
			log.exception(f"Ignoring exception in command {ctx.command.name}:")
			traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)




# This part is needed to handle slash command guild_id values for debug use
def _getDebugServerID () -> int | None:
	_debugServerConfig = configparser.ConfigParser(allow_no_value=True)
	_debugServerConfig.read("config/config.ini")
	_serverID = _debugServerConfig.getint("CORE", "debug_server", fallback = -1)
	if _serverID > 0:
		return _serverID
	else:
		return None

debugServerID = _getDebugServerID()
