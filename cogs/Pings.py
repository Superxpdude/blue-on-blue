import discord
from settings import config
from discord.ext import commands
from tinydb import TinyDB, Query

# Function to check if any invalid character patters are in a string.
def sanitize(text):
	if text == "":
		return "You need to specify a valid ping!"
	elif text.count("<@") > 0:
		return "You can't use mentions in a ping!"
	elif len(text) > 20:
		return "Pings must be 20 characters or less!"
	elif text.count(":") > 1:
		return "You can't use emotes in a ping!"
	elif check_ascii(text):
		return "You can't use non-ASCII characters in a ping!"
	else:
		return None

def check_ascii(text):
	try:
		text.encode("ascii")
	except UnicodeEncodeError: # Non-ascii characters present
		True
	else:
		False

class Pings(commands.Cog, name="Pings"):
	"""Ping users by tag."""
	
	def __init__(self, bot):
		self.bot = bot
	
	# Function that checks if a user can use ping control functions
	async def check_ping_control(ctx):
		roles = ctx.author.roles
		authors = [134830326789832704,96018174163570688]
		if (
			ctx.guild.get_role(config["SERVER"]["ROLES"]["ADMIN"]) in roles or
			ctx.guild.get_role(config["SERVER"]["ROLES"]["MODERATOR"]) in roles or
			ctx.author.id in authors
		):
			return True
		else:
			return False
	
	@commands.command(
		name="ping"
	)
	@commands.guild_only()
	async def ping(self, ctx, *, tag: str=""):
		"""Pings all users associated with a specific tag.
		
		Any text on a new line will be ignored. You can use this to send a message along with a ping."""
		tag = tag.split("\n")[0]
		san = sanitize(tag)
		if san is not None:
			await ctx.send(san)
			return
		db = TinyDB('db/pings.json') # Define the database
		tag = tag.lower() # String searching is case-sensitive
		pings = db.tables() # Grab all tables
		pings.remove('_default') # Remove the default table
		if tag in pings: # Pull info from a tag if it exists
			ping = db.table(tag)
			message = "Pinging '%s': " % (tag)
			for u in ping.all(): # Grab all users associated with a tag
				message += u['mention']
				message += " "
			message = message[:-1] # Remove the last character of the message
		else: # If the tag doesn't exist, inform the user
			message = "This tag does not exist. Try %spinglist for a list of active pings." % (ctx.prefix)
		
		# Send the message to the channel
		await ctx.send(message)
	
	@ping.error
	async def ping_error(self,ctx,error):
		if isinstance(error, commands.NoPrivateMessage):
			await ctx.send("This command cannot be used in private messages!")
	
	@commands.command(
		name="pingme"
	)
	async def pingme(self, ctx, *, tag: str=""):
		"""Adds or removes you from a ping list.
		
		If you're not in the list, it will add you to the list.
		If you are in the list, it will remove you from the list."""
		san = sanitize(tag)
		if san is not None:
			await ctx.send(san)
			return
		db = TinyDB('db/pings.json') # Define the database
		tag = tag.lower() # String searching is case-sensitive
		ping = db.table(tag) # Grab the table for the ping
		data = Query() # Define query
		if ping.contains(data.mention == ctx.author.mention): # User in ping list
			ping.remove(data.mention == ctx.author.mention) # Remove the user from the list
			if len(ping) == 0: # If no users are in the list, remove the list
				db.purge_table(tag)
			await ctx.send("You have been removed from ping: %s" % (tag))
		else: # User not in ping list
			ping.insert({'name': ctx.author.name, 'mention': ctx.author.mention})
			await ctx.send("You have been added to ping: %s" % (tag))
	
	@commands.command(
		name="pinglist"
	)
	async def pinglist(self, ctx, *, tag: str=""):
		"""Lists information about pings.
		
		When called with no tag, it will list all active tags.
		When called with a tag, it will list all users subscribed to that tag.
		When called with a mention to yourself, it will list all pings that you are currently subscribed to.
		NOTE: Usernames are stored when added to the list, and may no longer be accurate."""
		db = TinyDB('db/pings.json') # Define the database
		data = Query() # Define query
		tag = tag.lower() # String searching is case-sensitive
		pings = db.tables() # Grab all tables
		pings.remove('_default') # Remove the default table
		if tag in pings: # Pull info from a tag if it exists
			ping = db.table(tag)
			message = "Tag '%s' mentions the following users: \n```" % (tag)
			list = []
			for u in ping.all(): # Grab all users associated with a tag
				list += [u['name']]
			list = sorted(list, key=str.lower) # Sort list alphabetically
			for u in list:
				message += u
				message += ", "
			message = message[:-2] # Remove the last two characters of a message
			message += "```"
		elif "<@" in tag: # If the tag is a mention
			if tag.startswith("<@!"):
				t = tag[3:][:-1]
			else:
				t = tag[2:][:-1]
			if ctx.author.mention.startswith("<@!"):
				m = ctx.author.mention[3:][:-1]
			else:
				m = ctx.author.mention[2:][:-1]
			if t == m:
				list = []
				for p in pings:	# Iterate through all valid pings
					t = db.table(p)
					if t.contains(data.mention == ctx.author.mention):
						list += [p]
				list = sorted(list, key=str.lower) # Sort list alphabetically
				if len(list)>0:
					message = "%s, you are currently subscribed to the following pings: \n```" % (ctx.author.mention)
					for p in list:
						message += p
						message += ", "
					message = message[:-2]
					message += "```"
				else:
					message = "%s, you are not currently subscribed to any pings." % (ctx.author.mention)
			else:
				message = "You can't check a ping list for another user!"
		elif tag == "": # If no tag present, return all tags
			if len(pings)>0: 
				message = "Tag list: \n```"
				list = []
				for p in pings: # Grab all pings
					list += [p]
				list = sorted(list, key=str.lower) # Sort list alphabetically
				for p in list:
					message += p
					message += ", "
				message = message[:-2]
				message += "```"
			else:
				message = "There are currently no pings defined."
		else: # If the tag doesn't exist, inform the user
			message = "This tag does not exist. Try %spinglist for a list of active pings." % (ctx.prefix)
		
		# Send the message to the channel
		await ctx.send(message)
	
	@commands.command(
		name="pingpurge"
	)
	@commands.check(check_ping_control)
	async def pingpurge(self, ctx, *, tag: str=""):
		"""Destroys a ping list.
		
		Removes a ping list, regardless of how many users are in it.
		Can only be used by authorized users.
		This action cannot be undone."""
		# Purge does not get filtered, we need to make sure it always works.
		tag = tag.lower() # String searching is case-sensitive
		db = TinyDB('db/pings.json') # Define the database
		pings = db.tables() # Grab all tables
		pings.remove('_default') # Remove the default table
		if tag in pings:
			db.purge_table(tag)
			await ctx.send("Tag '%s' has been permanently removed by %s." % (tag, ctx.author.name))
		else:
			await ctx.send("This tag does not exist.")

	@pingpurge.error
	async def pingpurge_error(self,ctx,error):
		if isinstance(error, commands.CheckFailure):
			await ctx.send("You are not authorized to use that command.")
			
#	@commands.group()
#	@commands.check(check_ping_control)
#	async def pingmod(self, ctx):
#		"""Ping moderator functions.
#		
#		Subcommands are used to modify the ping module.
#		These commands can only be used by authorized users."""
#		if ctx.invoked_subcommand is None:
#			await ctx.send("Invalid pingmod command passed.")
#	
#	@pingmod.command()
#	async def create(self, ctx, *, tag: str=""):
#		"""Creates a ping list.
#		
#		Creates a ping list and allows users to assign themselves to it.
#		Can only be used by authorized users."""
#		san = sanitize(tag)
#		if san is not None:
#			ctx.send(san)
#			return
#		db = TinyDB('db/pings.json') # Define the database
#		#ping = db.table(tag) # Grab the table for the ping
#		data = Query() # Define query
#		tag = tag.lower() # String searching is case-sensitive

def setup(bot):
	bot.add_cog(Pings(bot))