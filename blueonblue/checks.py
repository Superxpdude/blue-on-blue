# Blue on Blue command checks
from discord.ext import commands
import slash_util

import typing
if typing.TYPE_CHECKING:
	import discord

import logging
log = logging.getLogger("blueonblue")

async def _check_roles(ctx: commands.Context, *roles: int) -> bool:
	"""Checks if a user has any of the specified roles (or is an owner of the bot)."""
	guild: discord.Guild = ctx.bot.get_guild(ctx.bot.config.getint("SERVER", "server_id")) # Get the guild object
	guildMember: discord.Member = guild.get_member(ctx.author.id) # Get the member object

	if guildMember is None: # If the member doesn't exist (i.e. not in guild)
		return False

	if await ctx.bot.is_owner(ctx.author): # If author is owner, allow the command
		return True

	for r in guildMember.roles:
		if r.id in roles:
			return True

	# If the user didn't pass the check, raise the error
	return False

# Command conditions
def is_moderator() -> bool:
	"""Checks if a user is part of the moderator or admin groups."""
	async def predicate(ctx: slash_util.Context):
		moderatorRoleID = ctx.bot.serverConfig.getint(str(ctx.guild.id), "role_moderator", fallback = -1)
		moderatorRole = ctx.guild.get_role(moderatorRoleID)
		adminRoleID = ctx.bot.serverConfig.getint(str(ctx.guild.id), "role_admin", fallback = -1)
		adminRole = ctx.guild.get_role(adminRoleID)

		isOwner = await ctx.bot.is_owner(ctx.author)

		if (adminRole in ctx.author.roles) or (moderatorRole in ctx.author.roles) or isOwner:
			return True
		else:
			raise UserUnauthorized

	return commands.check(predicate)

def is_admin() -> bool:
	"""Checks if a user is part of the admin group."""
	async def predicate(ctx: slash_util.Context):
		adminRoleID = ctx.bot.serverConfig.getint(str(ctx.guild.id), "role_admin", fallback = -1)
		adminRole = ctx.guild.get_role(adminRoleID)

		isOwner = await ctx.bot.is_owner(ctx.author)

		if (adminRole in ctx.author.roles) or isOwner:
			return True
		else:
			raise UserUnauthorized

	return commands.check(predicate)

def in_channel_bot() -> bool:
	"""Checks if the command was used in the specified bot channel"""
	async def predicate(ctx: slash_util.Context):
		botChannelID = ctx.bot.serverConfig.getint(str(ctx.guild.id), "channel_bot", fallback = -1)
		if ctx.channel.id == botChannelID:
			return True
		else:
			raise ChannelUnauthorized([botChannelID])

	return commands.check(predicate)

def in_channel_checkin() -> bool:
	"""Checks if the command was used in the specified bot channel"""
	async def predicate(ctx: slash_util.Context):
		botChannelID = ctx.bot.serverConfig.getint(str(ctx.guild.id), "channel_bot", fallback = -1)
		if ctx.channel.id == botChannelID:
			return True
		else:
			raise ChannelUnauthorized([botChannelID])

	return commands.check(predicate)

def has_config(section: str, option: str, type: typing.Literal["str","int","float","bool"] = "str") -> bool:
	"""Checks if the bot has the specified config entry.

	Intended to prevent the bot from erroring out with missing config values. Does not validate the value in any way other than checking if it exists."""
	async def predicate(ctx: commands.Context):
		if type == "str":
			value = ctx.bot.config.get(section, option, fallback = None)
		elif type == "int":
			value = ctx.bot.config.getint(section, option, fallback = None)
		elif type == "float":
			value = ctx.bot.config.getfloat(section, option, fallback = None)
		elif type == "bool":
			value = ctx.bot.config.getboolean(section, option, fallback = None)
		else: value = None

		if value is not None:
			return True
		else:
			return False
	return commands.check(predicate)

def in_any_channel(*items: int) -> bool:
	"""Checks if a command was used in any of the specified channels"""

	def predicate(ctx: commands.Context):
		# Allow commands in private messages
		if ctx.guild is None:
			return True

		if ctx.channel.id in items:
			return True

		# If the channel was invalid, raise the error
		raise ChannelUnauthorized(items)

	return commands.check(predicate)

async def slash_is_moderator(bot: slash_util.Bot, ctx: commands.Context) -> bool:
	"""Slash command check if the user is a moderator or administrator"""
	moderatorRoleID = bot.serverConfig.getint(str(ctx.guild.id), "role_moderator", fallback = -1)
	moderatorRole = ctx.guild.get_role(moderatorRoleID)
	adminRoleID = bot.serverConfig.getint(str(ctx.guild.id), "role_admin", fallback = -1)
	adminRole = ctx.guild.get_role(adminRoleID)

	isOwner = await bot.is_owner(ctx.author)

	if (adminRole in ctx.author.roles) or (moderatorRole in ctx.author.roles) or isOwner:
		return True
	else:
		return False

async def slash_is_admin(bot: slash_util.Bot, ctx: commands.Context) -> bool:
	"""Slash command check if the user is an administrator"""
	adminRoleID = bot.serverConfig.getint(str(ctx.guild.id), "role_admin", fallback = -1)
	adminRole = ctx.guild.get_role(adminRoleID)

	isOwner = await bot.is_owner(ctx.author)

	if (adminRole in ctx.author.roles) or isOwner:
		return True
	else:
		return False

# Error classes
class UserUnauthorized(commands.CheckFailure):
	# User does not have permissions to use that command
	pass

class ChannelUnauthorized(commands.CheckFailure):
	# Command was used in a channel that it is not permitted in
	def __init__(self, channels, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.channels = channels
