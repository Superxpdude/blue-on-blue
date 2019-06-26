import discord
from settings import config
from discord.ext import commands, tasks
from tinydb import TinyDB, Query
from datetime import datetime, timedelta
from pytimeparse.timeparse import timeparse
import blueonblue
import asyncio

def punish_split_input(self,ctx,args):
	"""Finds a discord user using either a mention string, or by searching in the current server."""
	
	gld = self.bot.get_guild(config["SERVER"]["ID"])
	if args.startswith('"'): #Search for the user
		args = args[1:].split('" ',1) #Split the input to get the variables
		if len(args) < 2: # If we have less than two inputs, mark the time as empty
			args = [args[0],""]
		usr = gld.get_member_named(args[0]) # Search for the user using their name
		tm_str = args[1]
	elif args.startswith("<@"): # Grab the user from a mention string
		args = args.split(' ',1) # Split the input
		if len(args) < 2: # If we have less than two inputs, mark the time as empty
			args = [args[0],""]
		# This is a bit hacky, but we need to make sure we're only working with a userID
		args[0] = args[0].replace("<","")
		args[0] = args[0].replace("@","")
		args[0] = args[0].replace("!","")
		args[0] = args[0].replace(">","")
		usr = gld.get_member(int(args[0])) # Grab the user from the ID
		tm_str = args[1]
	else:
		usr = None
		tm_str = None
	ret = [usr,tm_str]
	return ret

class Punish(commands.Cog, name="Punish"):
	def __init__(self, bot):
		self.bot = bot
		self.punishloop.start()
	
	def cog_unload(self):
		self.punishloop.cancel()
	
	@commands.command(
		name="punish",
		aliases=['jail', 'gitmo'],
		usage='$$punish user duration'
	)
	@commands.check(blueonblue.check_group_mods)
	async def punish(self, ctx, *, args):
		"""Punishes a user
		
		Sends a user to the shadow realm for a specified period of time.
		Requires a mention, or the exact name of the user being punished wrapped in double-quotes.
		Accepts times using a number, and a letter to determine the unit.
		ex. 'punish userID 1d 12h' would punish the user for 1.5 days.
		ex. 'punish "Memer" 1w' would punish a user named 'Memer' for 1 week."""
		
		input = punish_split_input(self,ctx,args)
		
		usr = input[0]
		tm_str = input[1]
		
		if usr is None:
			await ctx.send("You need to specify a user!")
			return 0
		
		tmparsed = timeparse(tm_str)
		if tmparsed is None:
			await ctx.send("You need to specify a time!")
			return 0
		
		# Convert the provided time string to a timedelta
		tmdelta = timedelta(seconds=tmparsed)
		# Convert the timedelta to a human readable format
		tm_readable = str(tmdelta)
		
		msg = await ctx.send("%s, you are about to punish the user %s for %s." \
							 "\nPlease select the checkmark emoji to confirm, " \
							 "or the cross emoji to abort." % \
							 (ctx.author.mention,usr.mention,tm_readable))
		await msg.add_reaction("✅")
		await msg.add_reaction("❌")
		
		def emoji_check(reaction, user):
			return user == ctx.author and (str(reaction.emoji) == '✅' or str(reaction.emoji) == '❌')
		
		try:
			reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=emoji_check)
		except asyncio.TimeoutError: # If the message times out
			await ctx.send("%s, you took too long to respond. Pending punish was automatically aborted." % \
						  (ctx.author.mention))
		else: # If one of the emotes was pressed
			if str(reaction.emoji) == '❌':
				# Punish cancelled
				await ctx.send ("%s, the pending punishment has been aborted." % (ctx.author.mention))
				return 0
			else:
				db = TinyDB('db/punish.json', sort_keys=True, indent=4) # Define the database
				tbl = db.table('punish')
				data = Query() # Define query
				tm = datetime.utcnow()
				gld = self.bot.get_guild(config["SERVER"]["ID"])
				role_member = gld.get_role(config["SERVER"]["ROLES"]["MEMBER"])
				role_punish = gld.get_role(config["SERVER"]["ROLES"]["PUNISH"])
				channel_mod = self.bot.get_channel(config["SERVER"]["CHANNELS"]["MOD"])
				if gld is None:
					return 0
				
				rls_tm = tm + tmdelta
				rls_text = rls_tm.isoformat() # TinyDB can't store the time format, we need to convert so string
				
				tbl.insert({'name': usr.name, 'displayname': usr.display_name, 'user_id': usr.id, 'release': rls_text})
				
				punish_reason = "User punished by '%s' for '%s'." % (ctx.author.display_name,tm_readable)
				await usr.remove_roles(role_member, reason=punish_reason)
				await usr.add_roles(role_punish, reason=punish_reason)
				await channel_mod.send("User '%s' has been punished by '%s' for '%s'." % (usr.display_name,ctx.author.display_name,tm_readable))
		
	@commands.command(
		name="release",
	)
	@commands.check(blueonblue.check_group_mods)
	async def release(self, ctx, usr_str):
		"""Releases a user from punishment
		
		Use this command with a userID or user mention to immediately release a user from the shadow realm."""
		
		if usr_str is None:
			await ctx.send("You need to specify a user!")
		
		db = TinyDB('db/punish.json', sort_keys=True, indent=4) # Define the database
		tbl = db.table('punish')
		data = Query() # Define query
		gld = self.bot.get_guild(config["SERVER"]["ID"])
		role_member = gld.get_role(config["SERVER"]["ROLES"]["MEMBER"])
		role_punish = gld.get_role(config["SERVER"]["ROLES"]["PUNISH"])
		channel_mod = self.bot.get_channel(config["SERVER"]["CHANNELS"]["MOD"])
		if gld is None:
			return 0
			
		# This is a bit hacky, but we need to make sure we're only working with a userID
		usr_str = usr_str.replace("<","")
		usr_str = usr_str.replace("@","")
		usr_str = usr_str.replace("!","")
		usr_str = usr_str.replace(">","")
		usr_id = int(usr_str)
		usr = gld.get_member(usr_id)
		
		if tbl.contains(data.user_id == usr_id):
			await usr.remove_roles(role_punish, reason="Punishment removed by '%s'." % (ctx.author.display_name))
			await usr.add_roles(role_member, reason="Punishment removed by '%s'." % (ctx.author.display_name))
			await channel_mod.send("User '%s' has been released from punishment by '%s'." % (usr.mention,ctx.author.mention))
			tbl.remove(data.user_id == usr_id)
		else:
			await ctx.send("Error, could not locate user in punishment database.")
	
	@tasks.loop(minutes=1, reconnect=True)
	async def punishloop(self):
		db = TinyDB('db/punish.json', sort_keys=True, indent=4) # Define the database
		tbl = db.table('punish')
		data = Query() # Define query
		tm = datetime.utcnow()
		gld = self.bot.get_guild(config["SERVER"]["ID"])
		role_member = gld.get_role(config["SERVER"]["ROLES"]["MEMBER"])
		role_punish = gld.get_role(config["SERVER"]["ROLES"]["PUNISH"])
		channel_mod = self.bot.get_channel(config["SERVER"]["CHANNELS"]["MOD"])
		if gld is None:
			return 0
		
		# Begin looping through all users in the punish table
		for u in tbl:
			rls_text = u['release']
			rls_tm = datetime.fromisoformat(rls_text)
			
			if tm > rls_tm: # Check if the user should be released
				usr = gld.get_member(u['user_id'])
				if usr is None:
					await channel_mod.send("Failed to remove punishment from user '%s', user may no longer be present in the server." % (u['name']))
				await usr.remove_roles(role_punish, reason='Punishment timeout expired')
				await usr.add_roles(role_member, reason='Punishment timeout expired')
				await channel_mod.send("User '%s' has been released from punishment due to timeout expiry." % (usr.display_name))
				tbl.remove(data.user_id == usr.id)
				
	
	@punishloop.before_loop
	async def before_punishloop(self):
		await self.bot.wait_until_ready() # Wait until the bot is ready

def setup(bot):
	bot.add_cog(Punish(bot))