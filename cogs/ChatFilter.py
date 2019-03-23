import discord
from discord.ext import commands
from settings import config
from tinydb import TinyDB, Query

# Function to update the blacklist
def update_list():
	db = TinyDB('db/chatfilter.json')
	table = db.table("blacklist")
	data = Query()
	global blacklist
	blacklist = []
	for w in table:
		blacklist += [w["word"]]

def checkphrase(message):
	phrase = message.content.lower()
	if phrase[2:][:9] == "cf remove": # Don't trigger if someone is using the remove command
		return 0
	processed_word = phrase # TODO: Add whitelist functionality
	if any(banned_words in processed_word.replace(" ","") for banned_words in blacklist):
		return 1
	return 0

async def profanity_check(self,message):
	bad_user = str(message.author)
	caught_phrase = str(message.content)
	channel = str(message.channel)
	if message.edited_at is not None:
		timestamp = str(message.edited_at)
	else:
		timestamp = str(message.created_at)
	#bad_message = bad_user, channel, caught_phrase, timestamp
	bad_embed = discord.Embed(title = channel, description = caught_phrase, color=0xff0000)
	bad_embed.set_author(name=bad_user, icon_url=message.author.avatar_url)
	bad_embed.set_footer(text=timestamp)
	await message.delete()
	await self.bot.get_channel(config["SERVER"]["CHANNELS"]["MOD"]).send(embed=bad_embed)
	

class ChatFilter(commands.Cog, name="Chat Filter"):
	"""Chat filter module.

	These commands can only be used by authorized users.
	"""
	
	def __init__(self, bot):
		self.bot = bot
		update_list()
	
	# Function that checks if a user can use chat filter functions
	async def check_cf(ctx):
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
	
	@commands.group()
	@commands.check(check_cf)
	async def cf(self, ctx):
		"""Chat filter control.
		
		Subcommands are used to modify chat filter functions.
		These commands can only be used by authorized users."""
		if ctx.invoked_subcommand is None:
			await ctx.send("Invalid cf command passed.")
	
	@cf.command()
	async def add(self, ctx, *, word: str=None):
		"""Adds a word to the chat filter blacklist."""
		if str is None:
			ctx.send("Invalid word.")
			return 0
		db = TinyDB('db/chatfilter.json') # Define the database
		table = db.table("blacklist") # Grab the blacklist table
		data = Query() # Define query
		word = word.lower() # String searching is case-sensitive
		if table.contains(data.word == word):
			await ctx.send("Word already present in blacklist!")
			return 0
		else:
			table.insert({"word": word})
			await ctx.send("Word '%s' added to blacklist." % (word))
			update_list()
	
	@cf.command()
	async def remove(self, ctx, *, word: str=None):
		"""Removes a word from the chat filter blacklist."""
		if str is None:
			ctx.send("Invalid word.")
			return 0
		db = TinyDB('db/chatfilter.json') # Define the database
		table = db.table("blacklist") # Grab the blacklist table
		data = Query() # Define query
		word = word.lower() # String searching is case-sensitive
		if table.contains(data.word == word):
			table.remove(data.word == word)
			await ctx.send("Word '%s' has been removed from the blacklist." % (word))
			update_list()
		else:
			await ctx.send("Word '%s' is not present in the blacklist." % (word))
			return 0
	
	@cf.command()
	async def list(self, ctx):
		"""Lists all words currently present on the blacklist."""
		db = TinyDB('db/chatfilter.json') # Define the database
		table = db.table("blacklist") # Grab the blacklist table
		data = Query() # Define query
		if len(table)>0:
			message = "Chat filter blacklist: \n```"
			list = []
			for w in table:
				list += [w["word"]]
			list = sorted(list, key=str.lower) # Sort list alphabetically
			for s in list:
				message += s
				message += ", "
			message = message[:-2]
			message += "```"
			await ctx.send(message)
		else:
			await ctx.send("The blacklist is currently empty.")
			return 0
	
	@commands.Cog.listener()
	async def on_message(self,message):
		if message.author != self.bot.user:
			if checkphrase(message):
				await profanity_check(self,message)
	
	@commands.Cog.listener()
	async def on_message_edit(self,before,after):
		if after.author != self.bot.user:
			if checkphrase(after):
				await profanity_check(self,after)
	
def setup(bot):
	bot.add_cog(ChatFilter(bot))