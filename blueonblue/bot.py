import aiohttp
import discord
from discord.ext import commands
import asqlite

import configparser
from datetime import datetime

from typing import Optional

import sys, traceback

from . import checks
from . import config

import logging
_log = logging.getLogger("blueonblue")

__all__ = ["BlueOnBlueBot"]

class BlueOnBlueBot(commands.Bot):
	"""Blue on Blue bot class.
	Subclass of discord.ext.commands.Bot"""
	# Class variable type hinting
	dbConnection: asqlite.Connection
	httpSession: aiohttp.ClientSession
	startTime: datetime
	firstStart: bool


	def __init__(self):
		# Set up our core config
		self.config = config.BotConfig("config/config.toml")

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
		self.slashDebugID: Optional[int] = None
		debugServerID = self.config.debug_server
		if debugServerID > 0: # If we have an ID present
			self.slashDebugID = debugServerID

		# Set up variables for type hinting
		self.firstStart = True

		# Set up our intents
		intents = discord.Intents.default()
		intents.members = True
		intents.message_content = True

		# Call the commands.Bot init
		super().__init__(
			command_prefix = commands.when_mentioned_or(self.config.prefix),
			description = "Blue on Blue",
			case_insensitive = True,
			intents = intents,
			tree_cls=BlueOnBlueTree
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
			"utils",
			"verify"
		]

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
			self.tree.clear_commands(guild = guild)
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

		# If we have a debug ID set, copy global commands to a guild
		if self.slashDebugID is not None:
			# Debug ID present, synchronize commands to guild
			guild = discord.Object(self.slashDebugID)
			self.tree.copy_global_to(guild = guild)

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

		# Command not found
		elif isinstance(error, commands.CommandNotFound):
			await ctx.send(f"{ctx.author.mention} Unknown command. This bot has migrated to slash commands. Try typing a `/` to see the list of commands.")

		# If we don't have a handler for that error type, execute default error code.
		else:
			_log.exception(f"Ignoring exception in command {ctx.command}:")
			traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

class BlueOnBlueTree(discord.app_commands.CommandTree):
	"""BlueOnBlue app commands tree
	Subclass of discord.app_commands.CommandTree used to override error handling"""

	async def on_error(
		self,
		interaction: discord.Interaction,
		error: discord.app_commands.AppCommandError
	):
		"""|coro|

		Error handling function called when an error occurs in an app command."""

		# Checks in this function should always occur *before* any response is sent to the interaction
		# So we should always be able to respond using the initial response function

		if isinstance(error, discord.app_commands.errors.NoPrivateMessage):
			# Guild-only command
			await interaction.response.send_message("This command cannot be used in private messages", ephemeral=True)

		elif (
			isinstance(error, discord.app_commands.errors.MissingRole) or
			isinstance(error, discord.app_commands.errors.MissingAnyRole) or
			isinstance(error, discord.app_commands.errors.MissingPermissions) or
			isinstance(error, checks.UserUnauthorized)
		):
			# User not authorized to use command
			await interaction.response.send_message("You are not authorized to use this command", ephemeral=True)

		elif isinstance(error, discord.app_commands.errors.BotMissingPermissions):
			# Bot is missing permissions for the command
			await interaction.response.send_message(f"The bot is missing the following permissions to use this command: `{error.missing_permissions}`")

		elif isinstance(error, checks.ChannelUnauthorized):
			# Command can only be used in specified channels
			assert isinstance(interaction.guild, discord.Guild)
			channels = []
			for c in error.channels:
				ch = interaction.guild.get_channel(c)
				if ch is not None:
					channels.append(ch.mention)

			if len(channels) > 1:
				message = f"{interaction.user.mention}, this command can only be used in the following channels: "
			elif len(channels) == 1:
				message = f"{interaction.user.mention}, this command can only be used in the following channel: "
			else:
				message = f"{interaction.user.mention}, this command cannot be used in this channel."

			# Add the channel idenfiers to the string
			message += ", ".join(channels)

			await interaction.response.send_message(message, ephemeral=True)

		# If we don't have a handler for that error type, execute default error code.
		else:
			if interaction.command is not None:
				_log.exception(f"Ignoring exception in app command {interaction.command}:")
			else:
				# Command is none
				_log.exception(f"Ignoring exception in command tree:")
			traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

		#await super().on_error(interaction, command, error)
