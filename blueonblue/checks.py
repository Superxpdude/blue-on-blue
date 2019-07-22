import discord
from discord.ext import commands
from settings import config
from blueonblue.bot import bot

# Errors
class UserUnauthorized(commands.CheckFailure):
	# User does not have permissions to use that command
	pass

# Checks if a user is part of the moderator or admin groups
def check_group_mods(ctx):
	# Check if the command was called within a guild
	
	# We can't use ctx.guild here since that breaks this if you call it in a private message
	# Time for an alternative method
	# Other parts of the bot need to be rewritten for this to work
	guild = bot.get_guild(config["SERVER"]["ID"]) # Get the guild object
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

class BotChannelOnly(commands.CheckFailure):
	# This command can only be executed in the bot commands channel
	pass

# Checks if a command was used in a bot commands channel
def check_bot_channel_only(ctx):
	# Check if the command was used in the bot commands channel
	# Make sure that the command can also be used in a private message.
	
	# If no guild specified, allow the command
	if ctx.guild is None:
		return True
	
	botchannel = config["SERVER"]["CHANNELS"]["BOT"]
	if ctx.channel.id == botchannel:
		return True
	else:
		raise BotChannelOnly