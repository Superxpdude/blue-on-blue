import logging
import sys
import traceback
from datetime import datetime

import aiohttp
import discord
from discord.ext import commands

from . import checks, config, db

_log = logging.getLogger(__name__)

__all__ = ["BlueOnBlueBot", "BlueOnBlueTree"]

initial_extensions = [
	"botcontrol",
	# "users",
	"arma_stats",
	"config",
	# "gold",
	# "jail",
	# "missions",
	"pings",
	# "raffle",
	"utils",
	# "verify",
]


class BlueOnBlueBot(commands.Bot):
	"""Blue on Blue bot class.
	Subclass of discord.ext.commands.Bot"""

	# Class variable type hinting
	httpSession: aiohttp.ClientSession
	startTime: datetime
	firstStart: bool

	def __init__(self):
		# Set up our core config
		self.config = config.BotConfig()

		# Set up our DB
		self.db = db.DB("data/blueonblue.sqlite3")

		# Initialize the server config
		self.serverConfig = config.ServerConfig(self)

		# Set up variables for type hinting
		self.firstStart = True

		# Set up our intents
		intents = discord.Intents.default()
		intents.members = True
		intents.message_content = True

		if self.config.prefix is not None:
			prefix = commands.when_mentioned_or(self.config.prefix)
		else:
			prefix = commands.when_mentioned

		# Call the commands.Bot init
		super().__init__(
			command_prefix=prefix,
			description="Blue on Blue",
			case_insensitive=True,
			intents=intents,
			tree_cls=BlueOnBlueTree,
		)

	async def syncAppCommands(self):
		"""|coro|

		Synchronizes app commands to discord.
		If a debug server is specified in config, commands will be synchronized to the specified guild instead of globally."""
		# Synchronize our app command tree
		if self.config.debug_server is not None:
			# Debug ID present, synchronize commands to guild
			guild = discord.Object(self.config.debug_server)
			# Remove existing commands from the guild list
			self.tree.clear_commands(guild=guild)
			self.tree.copy_global_to(guild=guild)
			await self.tree.sync(guild=guild)
		else:
			# Debug ID not present. Synchronize commands globally.
			await self.tree.sync()

	# Override the start function to set up our HTTP connection and SQLite DB
	async def start(self, *args, **kwargs):
		"""|coro|

		Overwritten start function to run the bot.
		Sets up the HTTP client and DB connections, then starts the bot."""
		# Validate our DB version
		await self.db.migrate_version()

		self.httpSession = aiohttp.ClientSession(raise_for_status=True)
		self.startTime = discord.utils.utcnow()
		await super().start(*args, **kwargs)

	async def close(self):
		"""|coro|

		Overwritten close function to stop the bot.
		Closes down the HTTP session when the bot is stopped."""
		await self.httpSession.close()
		await super().close()

	# Setup hook function to load extensions
	async def setup_hook(self):
		# Load our extensions
		for ext in initial_extensions:
			try:
				await self.load_extension("cogs." + ext)
			except Exception:
				_log.exception(f"Failed to load extension: {ext}")
			else:
				_log.info(f"Loaded extension: {ext}")
		_log.info("Extensions loaded")

		# If we have a debug ID set, copy global commands to a guild
		if self.config.debug_server is not None:
			# Debug ID present, synchronize commands to guild
			guild = discord.Object(self.config.debug_server)
			self.tree.copy_global_to(guild=guild)

	# On connect. Runs immediately upon connecting to Discord
	async def on_connect(self):
		# Make sure we're on our first connection
		if self.firstStart:
			_log.info("Connected to Discord")

	# On ready. Runs when the bot connects to discord, and has received server info.
	# Can run multiple times if the bot is disconnected at any point
	async def on_ready(self):
		# Make some log messages
		_log.info(f"Connected to {len(self.guilds)} servers")
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
	async def on_command_error(
		self, ctx: commands.Context, error: commands.CommandError
	):
		# Check different error types
		# Not owner of the bot
		if isinstance(error, commands.NotOwner):
			await ctx.send(
				f"{ctx.author.mention}, you are not authorized to use the command `{ctx.command}`."
			)

		# Command not found
		elif isinstance(error, commands.CommandNotFound):
			await ctx.send(
				f"{ctx.author.mention} Unknown command. This bot has migrated to slash commands. Try typing a `/` to see the list of commands."
			)

		# If we don't have a handler for that error type, execute default error code.
		else:
			_log.exception(f"Ignoring exception in command {ctx.command}:")
			traceback.print_exception(
				type(error), error, error.__traceback__, file=sys.stderr
			)


class BlueOnBlueTree(discord.app_commands.CommandTree):
	"""BlueOnBlue app commands tree
	Subclass of discord.app_commands.CommandTree used to override error handling"""

	async def on_error(
		self,
		interaction: discord.Interaction,
		error: discord.app_commands.AppCommandError,
	):
		"""|coro|

		Error handling function called when an error occurs in an app command."""

		# Checks in this function should always occur *before* any response is sent to the interaction
		# So we should always be able to respond using the initial response function

		if isinstance(error, discord.app_commands.errors.NoPrivateMessage):
			# Guild-only command
			await interaction.response.send_message(
				"This command cannot be used in private messages", ephemeral=True
			)

		elif (
			isinstance(error, discord.app_commands.errors.MissingRole)
			or isinstance(error, discord.app_commands.errors.MissingAnyRole)
			or isinstance(error, discord.app_commands.errors.MissingPermissions)
			or isinstance(error, checks.UserUnauthorized)
		):
			# User not authorized to use command
			await interaction.response.send_message(
				"You are not authorized to use this command", ephemeral=True
			)

		elif isinstance(error, discord.app_commands.errors.BotMissingPermissions):
			# Bot is missing permissions for the command
			await interaction.response.send_message(
				f"The bot is missing the following permissions to use this command: `{error.missing_permissions}`"
			)

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

		elif isinstance(error, checks.MissingServerConfigs):
			# Bot is missing server config options for the command
			settings = ", ".join(error.configs)
			message = f"{interaction.user.mention}, this server is missing the following config settings for this command.\n```{settings}```"
			await interaction.response.send_message(message)

		# If we don't have a handler for that error type, execute default error code.
		else:
			if interaction.command is not None:
				_log.exception(
					f"Ignoring exception in app command {interaction.command.name}:"
				)
			else:
				# Command is none
				_log.exception("Ignoring exception in command tree:")
			traceback.print_exception(
				type(error), error, error.__traceback__, file=sys.stderr
			)

		# await super().on_error(interaction, command, error)
