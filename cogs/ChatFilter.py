import discord
from discord.ext import commands
from settings import config
from tinydb import TinyDB, Query
import blueonblue

# Function to update the blacklist
def update_list():
	db = TinyDB('db/chatfilter.json', indent=4)
	bl = db.table("blacklist")
	data = Query()
	global blacklist
	blacklist = []
	for b in bl:
		blacklist += [b["word"]]
	
	wl = db.table("whitelist")
	global whitelist
	whitelist = []
	for w in wl:
		whitelist += [w["word"]]
	# To ensure that we remove longer words first, sort the whitelist.
	whitelist.sort(key = len, reverse=True)
	
async def _cf_add(self,ctx,ls,word):
	"""Adds a word to a chat filter list."""
	if word is None:
		await ctx.send("Invalid word.")
		return 0
	db = TinyDB('db/chatfilter.json', indent=4)
	table = db.table(ls)
	data = Query()
	word = word.lower()
	if table.contains(data.word == word):
		await ctx.send("Word already present in %s!" % (ls))
		return 0
	else:
		table.insert({"word": word})
		await ctx.send("Word '%s' added to %s." % (word, ls))
		update_list()

async def _cf_remove(self,ctx,ls,word):
	if str is None:
		await ctx.send("Invalid word.")
		return 0
	db = TinyDB('db/chatfilter.json', indent=4) # Define the database
	table = db.table(ls) # Grab the blacklist table
	data = Query() # Define query
	word = word.lower() # String searching is case-sensitive
	if table.contains(data.word == word):
		table.remove(data.word == word)
		await ctx.send("Word '%s' has been removed from the %s." % (word,ls))
		update_list()
	else:
		await ctx.send("Word '%s' is not present in the %s." % (word,ls))
		return 0

async def _cf_list(self,ctx,ls):
	db = TinyDB('db/chatfilter.json', indent=4) # Define the database
	table = db.table(ls) # Grab the blacklist table
	if len(table)>0:
		message = "Chat filter %s: \n```" % (ls)
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
		await ctx.send("The %s is currently empty." % (ls))
		return 0

def checkphrase(message):
	phrase = message.content.lower()
	if phrase[2:][:9] == "cf remove": # Don't trigger if someone is using the remove command
		return 0
	processed_word = phrase
	if any(safe_words in phrase for safe_words in whitelist):
		for word in whitelist:
			processed_word = processed_word.replace(word, "")
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

	These commands can only be used by authorized users."""
	
	def __init__(self, bot):
		self.bot = bot
		update_list()
	
	@commands.group()
	@commands.check(blueonblue.check_group_mods)
	async def cf(self, ctx):
		"""Chat filter control.
		
		Subcommands are used to modify chat filter functions.
		These commands can only be used by authorized users."""
		if ctx.invoked_subcommand is None:
			await ctx.send("Invalid cf command passed.")
	
	@cf.group()
	async def whitelist(self, ctx):
		"""Chat filter whitelist."""
		if ctx.invoked_subcommand is None:
			await ctx.send("Invalid cf command passed.")
	
	@whitelist.command(name="add")
	async def whitelist_add(self, ctx, *, word: str=None):
		"""Adds a word to the chat filter whitelist."""
		print(self)
		print(ctx)
		print(word)
		await _cf_add(self, ctx, "whitelist", word)
	
	@whitelist.command(name="remove")
	async def whitelist_remove(self, ctx, *, word: str=None):
		"""Removes a word from the chat filter whitelist."""
		await _cf_remove(self, ctx, "whitelist", word)
	
	@whitelist.command(name="list")
	async def whitelist_list(self, ctx):
		"""Lists all words currently present on the whitelist."""
		print(self)
		print(ctx)
		await _cf_list(self, ctx, "whitelist")
	
	@cf.group()
	async def blacklist(self, ctx):
		"""Chat filter blacklist."""
		if ctx.invoked_subcommand is None:
			await ctx.send("Invalid cf command passed.")
	
	@blacklist.command(name="add")
	async def blacklist_add(self, ctx, *, word: str=None):
		"""Adds a word to the chat filter blacklist."""
		await _cf_add(self, ctx, "blacklist", word)
	
	@blacklist.command(name="remove")
	async def blacklist_remove(self, ctx, *, word: str=None):
		"""Removes a word from the chat filter blacklist."""
		await _cf_remove(self, ctx, "blacklist", word)
	
	@blacklist.command(name="list")
	async def blacklist_list(self, ctx, *, word: str=None):
		"""Lists all words currently present on the blacklist."""
		await _cf_list(self, ctx, "blacklist")
	
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