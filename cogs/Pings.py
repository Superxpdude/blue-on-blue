import discord
from discord.ext import commands
import blueonblue
from blueonblue.config import config
from tinydb import TinyDB, Query
import typing
import logging
log = logging.getLogger("blueonblue")

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
	
	def __init__(self,bot):
		self.bot = bot
		self.db = TinyDB('db/pings.json', sort_keys=True, indent=4) # Define the database
		
		# The database stores the following info:
		# name: User name when added to the list
		# user_id: Discord user ID
	
	@commands.command(name="ping")
	@commands.guild_only()
	async def ping(self, ctx, *, tag: str=""):
		"""Pings all users associated with a specific tag.
		Any text on a new line will be ignored. You can use this to send a message along with a ping."""
		data = Query() # Define query
		tag = tag.split("\n")[0]
		san = sanitize(tag)
		if san is not None:
			await ctx.send(san)
			return
		tag = tag.lower() # String searching is case-sensitive
		pings = self.db.tables() # Grab all tables
		pings.remove('_default') # Remove the default table
		if tag in pings: # Pull info from a tag if it exists
			ping = self.db.table(tag)
			users = []
			message = "Pinging '%s': " % (tag)
			for u in ping.all(): # Grab all users associated with the tag
				usr = self.bot._guild.get_member(u["user_id"]) # Get the user object
				if usr is not None: # If we can't find the user (i.e. not in the server), remove them
					users.append(usr.mention)
#				else:
#					ping.remove(doc_ids=[u.doc_id])
			message = ("Pinging '%s': " % (tag)) + " ".join(users) # Create the ping message
		else: # If the tag doesn't exist, inform the user
			message = "This tag does not exist. Try %spinglist for a list of active pings." % (ctx.prefix)
		
		# Send the message to the channel
		await ctx.send(message)
		
	@commands.command(name="pingme")
	@blueonblue.checks.in_any_channel(config["SERVER"]["CHANNELS"]["BOT"])
	async def pingme(self, ctx, *, tag: str=""):
		"""Adds or removes you from a ping list.
		If you're not in the list, it will add you to the list.
		If you are in the list, it will remove you from the list."""
		san = sanitize(tag)
		if san is not None:
			await ctx.send(san)
			return
		tag = tag.lower() # String searching is case-sensitive
		if tag not in self.db.tables():
			log.info("New tag '%s' created by '%s' [%s]" % (tag, ctx.author.name, ctx.author.id))
		ping = self.db.table(tag) # Grab the table for the ping
		data = Query() # Define query
		if ping.contains(data.user_id == ctx.author.id): # User in ping list
			ping.remove(data.user_id == ctx.author.id) # Remove the user from the list
			if len(ping) == 0: # If no users are in the list, remove the list
				self.db.purge_table(tag)
				log.info("Tag '%s' removed due to lack of users." % (tag))
			await ctx.send("%s You have been removed from ping: %s" % (ctx.author.mention,tag))
		else: # User not in ping list
			ping.insert({'name': ctx.author.name, 'user_id': ctx.author.id})
			await ctx.send("%s You have been added to ping: %s" % (ctx.author.mention,tag))
	
	@commands.command(name="pinglist")
	@blueonblue.checks.in_any_channel(config["SERVER"]["CHANNELS"]["BOT"])
	async def pinglist(self, ctx, *, tag: str=""):
		"""Lists information about pings.
		
		When called with no tag, it will list all active tags.
		When called with a tag, it will list all users subscribed to that tag.
		When called with a mention to yourself, it will list all pings that you are currently subscribed to.
		Supports searching for tags. Entering a partial tag will return all valid matches."""
		
		gld = self.bot.get_guild(config["SERVER"]["ID"]) # Grab the server object
		data = Query() # Define query
		pings = self.db.tables() # Grab all tables
		pings.remove("_default") # Remove the default table
		
		if "<@" in tag: # Search by user
			if int(tag.replace("<","").replace("@","").replace("!","").replace(">","")) == ctx.author.id:
				ls = []
				for p in pings: # Iterate through all valid pings
					t = self.db.table(p)
					if t.contains(data.user_id == ctx.author.id):
						ls.append(p)
				ls = sorted(ls, key=str.lower) # Sort list alphabetically
				if len(ls)>0:
					message = f"{ctx.author.mention}, you are currently subscribed to the following pings: "\
					"\n```" + ", ".join(ls) + "```"
				else:
					message = "%s, you are not currently subscribed to any pings." % (ctx.author.mention)
			else:
				message = "%s, you cannot check a ping list for another user!" % (ctx.author.mention)
		elif tag in pings: # Direct match for an existing ping
			ping = self.db.table(tag)
			ls = []
			for u in ping.all(): # Grab all users associated with a tag
				usr = gld.get_member(u["user_id"])
				if usr is not None: # If we found the user, grab their current name
					ls.append(usr.display_name)
#				else: # If we could not find the user (i.e. no longer in the server), remove them from the list
#					ping.remove(doc_ids=[u.doc_id])
			ls = sorted(ls, key=str.lower) # Sort list alphabetically
			message = "Tag '%s' mentions the following users: \n```" % (tag) + ", ".join(ls) + "```"
		elif len(tag)>0: # Search for pings
			ls = list(filter(lambda x: x.startswith(tag),pings)) # Filter pings
			if len(ls)>0:
				ls = sorted(ls, key=str.lower) # Sort list alphabetically
				message = "Tag search for '%s': \n```" % (tag) + ", ".join(ls) + "```"
			else:
				message = "%s, there are no tags that match the search term: '%s'" % (ctx.author.mention, tag)
		else: # If no tag is provided, return all tags
			if len(pings)>0:
				ls = sorted(pings, key=str.lower) # Sort list of pings alphabetically
				message = "Tag list: \n```" + ", ".join(ls) + "```"
			else:
				message = "There are currently no pings defined."
		
		# Send the message to the channel
		await ctx.send(message)
	
	@commands.command(name="pingpurge")
	@commands.check(blueonblue.checks.check_group_mods)
	async def pingpurge(self, ctx, *, tag: str=""):
		"""Destroys a ping list.
		
		Removes a ping list, regardless of how many users are in it.
		Can only be used by authorized users.
		This action cannot be undone."""
		# Purge does not get filtered, we need to make sure it always works.
		tag = tag.lower() # String searching is case-sensitive
		pings = self.db.tables() # Grab all tables
		pings.remove('_default') # Remove the default table
		if tag in pings:
			self.db.purge_table(tag)
			await ctx.send("Tag '%s' has been permanently removed by %s." % (tag, ctx.author.name))
			log.info("Tag '%s' has been permanently removed by %s." % (tag, ctx.author.name))
		else:
			await ctx.send("This tag does not exist.")

def setup(bot):
	#usercog = bot.get_cog("Users")
	#if usercog is None:
	#	print("The user cog must be loaded first!")
	#	raise RuntimeError("User cog not found")
	bot.add_cog(Pings(bot))