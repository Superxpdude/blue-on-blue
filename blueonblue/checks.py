# Blue on blue command checks
import discord
from discord.ext import commands
from blueonblue.config import config
import logging
log = logging.getLogger("blueonblue")

class UserUnauthorized(commands.CheckFailure):
	# User does not have permissions to use that command
	pass

# Checks if a user is part of the moderator or admin groups
def check_group_mods(ctx):
	# Check if the command was called within a guild
	
	# We can't use ctx.guild here since that breaks this if you call it in a private message
	# Time for an alternative method
	# Other parts of the bot need to be rewritten for this to work
	guild = ctx.bot.get_guild(config["SERVER"]["ID"]) # Get the guild object
	userid = ctx.author.id # Get the user ID
	guildMember = guild.get_member(userid) # Get the member object from the guild
	
	if guildMember is None: # If the member doesn't exist, return false
		raise UserUnauthorized
	
	# Now that we have confirmed that the user is in the guild, check their roles
	roles = guildMember.roles
	authors = [134830326789832704,96018174163570688]
	
	if (
		guild.get_role(config["SERVER"]["ROLES"]["ADMIN"]) in roles or
		guild.get_role(config["SERVER"]["ROLES"]["MODERATOR"]) in roles or
		ctx.author.id in authors
	):
		return True
	else:
		raise UserUnauthorized
		
# Checks if a user is part of the moderator or admin groups
def check_group_admins(ctx):
	# Check if the command was called within a guild
	
	# We can't use ctx.guild here since that breaks this if you call it in a private message
	# Time for an alternative method
	# Other parts of the bot need to be rewritten for this to work
	guild = ctx.bot.get_guild(config["SERVER"]["ID"]) # Get the guild object
	userid = ctx.author.id # Get the user ID
	guildMember = guild.get_member(userid) # Get the member object from the guild
	
	if guildMember is None: # If the member doesn't exist, return false
		raise UserUnauthorized
	
	# Now that we have confirmed that the user is in the guild, check their roles
	roles = guildMember.roles
	authors = [134830326789832704,96018174163570688]
	
	if (
		guild.get_role(config["SERVER"]["ROLES"]["ADMIN"]) in roles or
		ctx.author.id in authors
	):
		return True
	else:
		raise UserUnauthorized

def has_any_role_guild(*items):
	# Check that the user is in any group within the bot's server
	def predicate(ctx):
		guild = ctx.bot.get_guild(config["SERVER"]["ID"]) # Get the guild object
		userid = ctx.author.id # Get the user ID
		guildMember = guild.get_member(userid) # Get the member object from the guild
		
		if guildMember is None: # If the member doesn't exist (i.e. not in guild)
			raise UserUnauthorized
		
		# Now that we have confirmed that the user is in the guild, check their roles
		roles = guildMember.roles
		authors = [134830326789832704,96018174163570688]
		
		for role in roles:
			if role.id in items:
				return True
		
		if userid in authors:
			return True
		
		# If the user didn't pass the check, raise the error
		raise UserUnauthorized
	
	return commands.check(predicate)

class ChannelUnauthorized(commands.CheckFailure):
	# Command was used in a channel that it is not permitted in
	def __init__(self, channels, *args, **kwargs):
		super().__init__(*args,**kwargs)
		self.channels = channels

# Checks if a command was used in an authorized channel
def in_any_channel(*items):
	# Check that the command was run within a specified channel
	def predicate(ctx):
		# Allow commands in private messages
		if ctx.guild is None:
			return True
		
		ch = ctx.channel
		chid = ch.id
		
		if chid in items:
			return True
		
		# If the channel was invalid, raise the error
		raise ChannelUnauthorized(items)
		
	return commands.check(predicate)