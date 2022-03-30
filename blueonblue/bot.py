import aiohttp
import discord
from discord.ext import commands
import asqlite

import configparser
from datetime import datetime

import sys, traceback

from . import checks

import logging
_log = logging.getLogger("blueonblue")

__all__ = ["BlueOnBlueBot"]

class BlueOnBlueBot(commands.Bot):
	"""Blue on Blue bot class.
	Subclass of discord.ext.commands.Bot"""
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
				"api_file": "config/google_api.json"
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

		# Set up variables for type hinting
		self.dbConnection: asqlite.Connection = None
		self.httpSession: aiohttp.ClientSession = None
		self.startTime: datetime = None
		self.firstStart: bool = True

		# Set up our intents
		intents = discord.Intents.default()
		intents.members = True
		intents.message_content = True

		# Call the commands.Bot init
		super().__init__(
			command_prefix = commands.when_mentioned_or(self.config.get("CORE", "prefix", fallback="$$")),
			description = "Blue on Blue",
			case_insensitive = True,
			intents = intents
		)

		# Define our list of initial extensions
		# Botcontrol and users must be first and second respectively
		self.initialExtensions = [
			"botcontrol",
			"users",
			"chatfilter",
			"gold",
			"jail",
			"missions",
			"pings",
			"verify"
		]

	def write_config(self):
		"""Write the current bot config to disk"""
		with open("config/config.ini", "w") as configFile:
			self.config.write(configFile)

	def write_serverConfig(self):
		"""Write the current server configs to disk"""
		with open("config/serverconfig.ini", "w") as configFile:
			self.serverConfig.write(configFile)

	async def syncAppCommands(self):
		"""|coro|

		Synchronizes app commands to discord.
		If a debug server is specified in config, commands will be synchronized to the specified guild instead of globally."""
		# Synchronize our app command tree
		if self.slashDebugID is not None:
			# Debug ID present, synchronize commands to guild
			guild = discord.Object(self.slashDebugID)
			# Remove existing commands from the guild list
			for type in [discord.AppCommandType.chat_input, discord.AppCommandType.user, discord.AppCommandType.message]:
				for command in self.tree.get_commands(guild = guild, type = type):
					self.tree.remove_command(command.name, guild = guild, type = type)
			self.tree.copy_global_to(guild = guild)
			await self.tree.sync(guild = guild)
		else:
			# Debug ID not present. Synchronize commands globally.
			await self.tree.sync()

	# Override the start function to set up our HTTP connection and SQLite DB
	async def start(self, *args, **kwargs):
		"""|coro|

		Overwritten start function to run the bot.
		Sets up the HTTP client and DB connections, then starts the bot."""
		async with aiohttp.ClientSession() as session:
			async with asqlite.connect("data/blueonblue.sqlite3") as connection:
				self.httpSession = session
				self.dbConnection = connection
				self.startTime = discord.utils.utcnow()
				await super().start(*args, **kwargs)

	# Setup hook function to load extensions
	async def setup_hook(self):
		# Load our extensions
		for ext in self.initialExtensions:
			try:
				await self.load_extension("cogs." + ext)
			except Exception as e:
				_log.exception(f"Failed to load extension: {ext}")
			else:
				_log.info(f"Loaded extension: {ext}")
		_log.info("Extensions loaded")

	# On connect. Runs immediately upon connecting to Discord
	async def on_connect(self):
		# Make sure we're on our first connection
		if self.firstStart:
			_log.info("Connected to Discord")

	# On ready. Runs when the bot connects to discord, and has received server info.
	# Can run multiple times if the bot is disconnected at any point
	async def on_ready(self):
		# Ensure that we have a config section for each server that we're in
		newGuilds = False
		for guild in self.guilds:
			if not self.serverConfig.has_section(str(guild.id)):
				self.serverConfig.add_section(str(guild.id))
				newGuilds = True
		# Write the server config (only if we have new guilds)
		if newGuilds:
			self.write_serverConfig()

		# Make some log messages
		_log.info(f"Connected to servers: {self.guilds}")
		_log.info("Blue on Blue ready.")

		# Set our "first start" variable to False
		self.firstStart = False

	# On message. Runs every time the bot receives a new message
	async def on_message(self, message: discord.Message):
		# Do not execute commands sent by bots
		if message.author.bot:
			return
		# Process commands in the message
		await self.process_commands(message)

	# On command completion. Runs every time a command is completed
	async def on_command_completion(self, ctx: commands.Context):
		_log.debug(f"Command {ctx.command} invoked by {ctx.author.name}")

	# On command error. Runs whenever a command fails (for any reason)
	async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
		# Check different error types
		# Not owner of the bot
		if isinstance(error, commands.NotOwner):
			await ctx.send(f"{ctx.author.mention}, you are not authorized to use the command `{ctx.command}`.")

		elif isinstance(error, checks.CommandChannelUnauthorized):
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

		# Command not found
		elif isinstance(error, commands.CommandNotFound):
			await ctx.send(f"{ctx.author.mention} Unknown command. This bot has migrated to slash commands. Try typing a `/` to see the list of commands.")

		# If we don't have a handler for that error type, execute default error code.
		else:
			_log.exception(f"Ignoring exception in command {ctx.command}:")
			traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
