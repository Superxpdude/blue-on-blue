# Blue on Blue command checks
import discord
from discord import app_commands
from discord.ext import commands

import logging

from blueonblue import bot as blueonbluebot
log = logging.getLogger("blueonblue")


# App command error classes
class UserUnauthorized(app_commands.AppCommandError):
	"""Command can only be used by specified users"""
	pass


class ChannelUnauthorized(app_commands.AppCommandError):
	"""Command can only be used in specified channels"""
	def __init__(self, channels = tuple[int], *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.channels: tuple[int]
		if isinstance(channels, tuple):
			self.channels = channels
		else:
			self.channels = (channels,)


# App command check functions
def is_admin() -> bool:
	"""Checks if a user is part of the admin group."""
	async def predicate(interaction: discord.Interaction):
		bot: blueonbluebot.BlueOnBlueBot = interaction.client
		isOwner = await bot.is_owner(interaction.user)
		# Check if the command was executed in a server or not
		if interaction.guild is not None:
			# Command was used in a server
			adminID = bot.serverConfig.getint(str(interaction.guild.id), "role_admin", fallback = -1)
			adminRole = interaction.guild.get_role(adminID)

			if isOwner or (adminRole in interaction.user.roles):
				# User is owner, admin, or moderator
				return True
			else:
				# Not owner, admin, or moderator
				raise UserUnauthorized
		else:
			# Command was used in a DM
			if isOwner:
				# User is owner, let them use the command
				return True
			else:
				# Not owner. Raise an unauthorized error.
				raise UserUnauthorized

	return app_commands.check(predicate)


def is_moderator() -> bool:
	"""Checks if a user is part of the moderator or admin groups."""
	async def predicate(interaction: discord.Interaction):
		bot: blueonbluebot.BlueOnBlueBot = interaction.client
		isOwner = await bot.is_owner(interaction.user)
		# Check if the command was executed in a server or not
		if interaction.guild is not None:
			# Command was used in a server
			moderatorID = bot.serverConfig.getint(str(interaction.guild.id), "role_moderator", fallback = -1)
			moderatorRole = interaction.guild.get_role(moderatorID)
			adminID = bot.serverConfig.getint(str(interaction.guild.id), "role_admin", fallback = -1)
			adminRole = interaction.guild.get_role(adminID)

			if isOwner or (adminRole in interaction.user.roles) or (moderatorRole in interaction.user.roles):
				# User is owner, admin, or moderator
				return True
			else:
				# Not owner, admin, or moderator
				raise UserUnauthorized
		else:
			# Command was used in a DM
			if isOwner:
				# User is owner, let them use the command
				return True
			else:
				# Not owner. Raise an unauthorized error.
				raise UserUnauthorized

	return app_commands.check(predicate)


def in_guild() -> bool:
	"""Checks if the command was used in a guild"""
	async def predicate(interaction: discord.Interaction):
		if interaction.guild is not None:
			return True
		else:
			raise app_commands.errors.NoPrivateMessage

	return app_commands.check(predicate)


def in_channel_bot() -> bool:
	"""Checks if the command was used in the specified bot channel"""
	async def predicate(interaction: discord.Interaction):
		bot: blueonbluebot.BlueOnBlueBot = interaction.client
		# Check if the command was executed in a server or not
		if interaction.guild is not None:
			# Command was used in a server
			botChannelID = bot.serverConfig.getint(str(interaction.guild.id), "channel_bot", fallback = -1)
			if interaction.channel.id == botChannelID:
				# Used in bot channel
				return True
			else:
				# Not in bot channel
				raise ChannelUnauthorized(botChannelID)
		else:
			# Not used in guild
			# For this, we don't specifically care if it was used in a DM or not. If it shouldn't be used in DMs, a "in_guild" check should be done as well.
			return True

	return app_commands.check(predicate)


# async def _check_roles(ctx: commands.Context, *roles: int) -> bool:
# 	"""Checks if a user has any of the specified roles (or is an owner of the bot)."""
# 	guild: discord.Guild = ctx.bot.get_guild(ctx.bot.config.getint("SERVER", "server_id")) # Get the guild object
# 	guildMember: discord.Member = guild.get_member(ctx.author.id) # Get the member object

# 	if guildMember is None: # If the member doesn't exist (i.e. not in guild)
# 		return False

# 	if await ctx.bot.is_owner(ctx.author): # If author is owner, allow the command
# 		return True

# 	for r in guildMember.roles:
# 		if r.id in roles:
# 			return True

# 	# If the user didn't pass the check, raise the error
# 	return False


def in_channel_checkin() -> bool:
	"""Checks if the command was used in the specified bot channel"""
	async def predicate(ctx: commands.Context):
		bot: blueonbluebot.BlueOnBlueBot = ctx.bot
		botChannelID = bot.serverConfig.getint(str(ctx.guild.id), "channel_check_in", fallback = -1)
		if ctx.channel.id == botChannelID:
			return True
		else:
			raise CommandChannelUnauthorized([botChannelID])

	return commands.check(predicate)


# def has_config(section: str, option: str, type: typing.Literal["str","int","float","bool"] = "str") -> bool:
# 	"""Checks if the bot has the specified config entry.

# 	Intended to prevent the bot from erroring out with missing config values. Does not validate the value in any way other than checking if it exists."""
# 	async def predicate(ctx: commands.Context):
# 		if type == "str":
# 			value = ctx.bot.config.get(section, option, fallback = None)
# 		elif type == "int":
# 			value = ctx.bot.config.getint(section, option, fallback = None)
# 		elif type == "float":
# 			value = ctx.bot.config.getfloat(section, option, fallback = None)
# 		elif type == "bool":
# 			value = ctx.bot.config.getboolean(section, option, fallback = None)
# 		else: value = None

# 		if value is not None:
# 			return True
# 		else:
# 			return False
# 	return commands.check(predicate)


# Error classes
class CommandUserUnauthorized(commands.CheckFailure):
	# User does not have permissions to use that command
	pass


class CommandChannelUnauthorized(commands.CheckFailure):
	# Command was used in a channel that it is not permitted in
	def __init__(self, channels, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.channels = channels
