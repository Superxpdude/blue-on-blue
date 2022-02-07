# Blue on Blue command checks
from discord.ext import commands

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
def has_any_role_guild(*roles: int) -> bool:
	"""Checks if a user has one of the specified roles in a guild.

	Uses the guild specified in the config file, even if the command is sent elsewhere."""
	async def predicate(ctx: commands.Context):
		if await _check_roles(ctx, *roles):
			return True
		else:
			raise UserUnauthorized

	return commands.check(predicate)

def is_moderator() -> bool:
	"""Checks if a user is part of the moderator or admin groups.

	Checks in the server specified in the config file, even if the command is sent elsewhere."""
	async def predicate(ctx: commands.Context):
		if await _check_roles(
			ctx,
			ctx.bot.config.getint("SERVER", "role_admin", fallback = -1),
			ctx.bot.config.getint("SERVER", "role_moderator", fallback = -1)
		):
			return True
		else:
			raise UserUnauthorized

	return commands.check(predicate)

def is_admin() -> bool:
	"""Checks if a user is part of the admin group.

	Checks in the server specified in the config file, even if the command is sent elsewhere."""
	async def predicate(ctx: commands.Context):
		if await _check_roles(
			ctx,
			ctx.bot.config.getint("SERVER", "role_admin", fallback = -1)
		):
			return True
		else:
			raise UserUnauthorized

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

# Error classes
class UserUnauthorized(commands.CheckFailure):
	# User does not have permissions to use that command
	pass

class ChannelUnauthorized(commands.CheckFailure):
	# Command was used in a channel that it is not permitted in
	def __init__(self, channels, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.channels = channels
