import discord
from settings import config
from discord.ext import commands
from tinydb import TinyDB, Query

class Pings(commands.Cog, name="Pings"):
	"""Ping users by tag."""
	
	def __init__(self, bot):
		self.bot = bot
	
	@commands.command(
		name="ping"
	)
	async def ping(self, ctx, *, tag: str=None):
		"""Pings all users associated with a specific tag."""
		db = TinyDB('db/pings.json') # Define the database
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
			message = "This tag does not exist. Try %spinglist for a list of active pings." % (config["BOT"]["CMD_PREFIXES"][0])
		
		# Send the message to the channel
		await ctx.send(message)
	
	@commands.command(
		name="pingme"
	)
	async def pingme(self, ctx, *, tag: str=None):
		"""Adds or removes you from a ping list.
		
		If you're not in the list, it will add you to the list.
		If you are in the list, it will remove you from the list."""
		db = TinyDB('db/pings.json') # Define the database
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
	async def pinglist(self, ctx, *, tag: str=None):
		"""Lists information about pings.
		
		When called with no tag, it will list all active tags.
		When called with a tag, it will list all users subscribed to that tag.
		NOTE: Usernames are stored when added to the list, and may no longer be accurate."""
		db = TinyDB('db/pings.json') # Define the database
		pings = db.tables() # Grab all tables
		pings.remove('_default') # Remove the default table
		if tag in pings: # Pull info from a tag if it exists
			ping = db.table(tag)
			message = "Tag '%s' mentions the following users: \n```" % (tag)
			for u in ping.all(): # Grab all users associated with a tag
				message += u['name']
				message += ", "
			message = message[:-2] # Remove the last two characters of a message
			message += "```"
		elif tag is None: # If no tag present, return all tags
			if len(pings)>0: 
				message = "Tag list: \n```"
				for p in pings:
					message += p
					message += ", "
				message = message[:-2]
				message += "```"
			else:
				message = "There are currently no pings defined."
		else: # If the tag doesn't exist, inform the user
			message = "This tag does not exist. Try %spinglist for a list of active pings." % (config["BOT"]["CMD_PREFIXES"][0])
		
		# Send the message to the channel
		await ctx.send(message)

def setup(bot):
	bot.add_cog(Pings(bot))