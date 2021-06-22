import discord
from discord.ext import commands, tasks
import blueonblue
import asyncio
from blueonblue.config import config
from datetime import datetime, timedelta
from pytimeparse.timeparse import timeparse
from tinydb import TinyDB, Query
import typing
import logging
log = logging.getLogger("blueonblue")

class Gold(commands.Cog, name="Gold"):
	def __init__(self, bot):
		self.bot = bot
		self.db = TinyDB('db/gold.json', sort_keys=True, indent=4) # Define the database
		self.goldloop.start()
	
	def cog_unload(self):
		self.goldloop.stop()
	
	@commands.command(
		name="gold",
		usage="$$gold user duration"
	)
	@commands.check(blueonblue.checks.check_group_admins)
	async def gold(self, ctx, usr: typing.Optional[discord.Member], tm_str: str=""):
		"""Gives TMTM Gold to a user
	
		Gives a user 'TMTM Gold' for the specified period of time.
		Requires a mention, or the exact name of the user to be provided.
		Accepts times using a number, and a letter to determine the unit.
		Only accepts time units up to a week. Months and years are not supported.
		ex. 'gold userID 60d' would give the user gold for two months.
		ex. 'gold "Username" 52w' would give the user gold for one year (52 weeks)."""
	
		gld = self.bot.get_guild(config["SERVER"]["ID"])
		
		if usr is None:
			await ctx.send("You need to specify a valid user!")
			raise commands.ArgumentParsingError()
			
		tmparsed = timeparse(tm_str)
		if tmparsed is None:
			await ctx.send("You need to specify a valid length of time!")
			raise commands.ArgumentParsingError()
		
		# Convert the provided time string to a timedelta
		tmdelta = timedelta(seconds=tmparsed)
		# Convert the timedelta to a human readable format
		tm_readable = str(tmdelta)
		
		msg = await ctx.send("%s, you are about to give TMTM Gold to %s for %s." \
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
			await ctx.send("%s, you took too long to respond. Pending gold was automatically aborted." % \
						(ctx.author.mention))
		else: # If one of the emotes was pressed
			if str(reaction.emoji) == '❌':
				# TMTM Gold cancelled
				await ctx.send ("%s, the pending gold has been aborted." % (ctx.author.mention))
				return 0
			else:
				tbl = self.db.table('gold')
				users = self.bot.get_cog("Users")
				tm = datetime.utcnow()
				role_gold = gld.get_role(config["SERVER"]["ROLES"]["GOLD"])
				channel_mod = self.bot.get_channel(config["SERVER"]["CHANNELS"]["MOD"])
				
				rls_tm = tm + tmdelta
				rls_text = rls_tm.isoformat() # TinyDB can't store the time format, we need to convert to string
				
				if tbl.contains(Query().id == usr.id): # User is already in gold database
					# Do not remove roles from the user, only update their expiry time
					tbl.upsert({'name': usr.name, 'displayname': usr.display_name, 'user_id': usr.id, 'expiry': rls_text}, Query().user_id == usr.id)
					await channel_mod.send("TMTM Gold for user '%s' has been modified by '%s' to '%s'." % (usr.display_name,ctx.author.display_name,tm_readable))
				else:
					# Ensure that the user database is up to date first
					await users.user_update(usr)
					
					tbl.upsert({'name': usr.name, 'displayname': usr.display_name, 'user_id': usr.id, 'expiry': rls_text}, Query().user_id == usr.id)
					
					gold_reason = "TMTM Gold given to '%s' for '%s'." % (ctx.author.display_name,tm_readable)
					try:
						await usr.add_roles(role_gold, reason=gold_reason) #Add the gold role first to prevent incorrect updating of the users database
					except:
						await channel_mod.send("Error assigning roles when providing TMTM Gold to %s." % (usr.mention))
						log.warning("Failed to assign TMTM Gold to user. User: %s" % (usr.name))
					await channel_mod.send("User '%s' has been given TMTM Gold by '%s' for '%s'." % (usr.display_name,ctx.author.display_name,tm_readable))
	
	@commands.command(
		name = "goldlist"
	)
	@commands.check(blueonblue.checks.check_group_mods)
	async def goldlist(self, ctx):
		"""Displays a list of TMTM Gold users
		
		Displays a full list of all TMTM Gold users currently managed by the bot."""
		
		gld = self.bot.get_guild(config["SERVER"]["ID"])
		tbl = self.db.table('gold')
		embed = discord.Embed(title = "Gold Users", color=0xff3491) # Make our embed
		for i in tbl.all():
			rls_text = i['expiry']
			rls_tm = datetime.fromisoformat(rls_text) # Convert the time string to a time value
			usr_id = i['user_id']
			usr = gld.get_member(i['user_id']) # Get the user by their ID
			try:
				usr_name = usr.display_name # Get the user's display name
			except:
				usr_name = i['displayname'] # If the user is no longer in the server. Grab their stored name
			tmdelta = rls_tm - datetime.utcnow() # Find the time delta from now until user release
			tmdelta = tmdelta - timedelta(microseconds=tmdelta.microseconds) # Remove microseconds
			if tmdelta > timedelta(microseconds=0):
				tmdelta_str = str(tmdelta)
			else:
				tmdelta_str = "Imminent"
			embed.add_field(name=usr_name,value=tmdelta_str,inline=False) # Add the field to the embed
		await ctx.send(embed=embed) # Send the embed
	
	@commands.command(
		name="gold_remove"
	)
	@commands.check(blueonblue.check_group_admins)
	async def gold_remove(self, ctx, usr: typing.Optional[discord.Member]):
		"""Removes TMTM Gold from a user.
		
		Use this command with a userID or user mention to immediately remove TMTM Gold from a user."""
		
		if usr is None:
			await ctx.send("You need to specify a valid user!")
			raise commands.ArgumentParsingError()
		
		tbl = self.db.table('gold')
		gld = self.bot.get_guild(config["SERVER"]["ID"])
		role_gold = gld.get_role(config["SERVER"]["ROLES"]["GOLD"])
		channel_mod = self.bot.get_channel(config["SERVER"]["CHANNELS"]["MOD"])
		if gld is None:
			return 0
		
		usr_id = usr.id
		
		users = self.bot.get_cog("Users")
		
		if tbl.contains(Query().user_id == usr_id):
			try:
				await usr.remove_roles(role_gold, reason="TMTM Gold removed by '%s'." % (ctx.author.display_name))
			except:
				await channel_mod.send("Failed to remove TMTM Gold from user. User: [%s]." % (usr.mention))
				log.warning("Failed to remove TMTM Gold from user. User: [%s]." % (usr.name))
			await channel_mod.send("User '%s' has had TMTM Gold removed by '%s'." % (usr.mention,ctx.author.mention))	
			tbl.remove(Query().user_id == usr_id)

			# Try to remove the TMTM Gold role from the user's stored roles
			old_roles = await users.read_data(usr,"roles",[])
			new_roles = list(filter(lambda i: i["id"] != (config["SERVER"]["ROLES"]["GOLD"]), old_roles))
			await users.write_data(usr,{"roles": new_roles})

		else:
			await ctx.send("Error, could not locate user in TMTM Gold database.")
	
	@tasks.loop(minutes=1, reconnect=True)
	async def goldloop(self):
		tbl = self.db.table('gold')
		tm = datetime.utcnow()
		gld = self.bot.get_guild(config["SERVER"]["ID"])
		role_gold = gld.get_role(config["SERVER"]["ROLES"]["GOLD"])
		channel_mod = self.bot.get_channel(config["SERVER"]["CHANNELS"]["MOD"])
		if gld is None:
			return 0
			
		users = self.bot.get_cog("Users")
		
		# Begin looping through all users in the punish table
		for u in tbl:
			rls_text = u['expiry']
			rls_tm = datetime.fromisoformat(rls_text)
			
			if tm > rls_tm: # Check if the user should be released
				usr = gld.get_member(u['user_id'])
				usr_roles = []
				
				if usr is None:
					await channel_mod.send("Failed to remove TMTM Gold from user '%s', user may no longer be present in the server." % (u['name']))
					# A copy of the same information as below. But using information from the database.
					await channel_mod.send("TMTM Gold has expired for user '%s'." % (u['name']))
					tbl.remove(Query().user_id == u['user_id'])

					# Try to remove the TMTM Gold role from the user's stored roles
					old_roles = await users.read_data(usr,"roles",[])
					new_roles = list(filter(lambda i: i["id"] != (config["SERVER"]["ROLES"]["GOLD"]), old_roles))
					await users.write_data(usr,{"roles": new_roles})
				else:
					try:
						await usr.remove_roles(role_gold, reason="TMTM Gold expired for user '%s'." % (usr.display_name))
					except:
						await channel_mod.send("Failed to remove expired TMTM Gold from user. User: [%s]." % (usr.mention))
						log.warning("Failed to remove expired TMTM Gold from user. User: [%s]." % (usr.name))
					await channel_mod.send("TMTM Gold has expired for user '%s'." % (usr.mention))	
					tbl.remove(Query().user_id == u['user_id'])

					# Try to remove the TMTM Gold role from the user's stored roles
					old_roles = await users.read_data(usr,"roles",[])
					new_roles = list(filter(lambda i: i["id"] != (config["SERVER"]["ROLES"]["GOLD"]), old_roles))
					await users.write_data(usr,{"roles": new_roles})
	
	@goldloop.before_loop
	async def before_goldloop(self):
		await self.bot.wait_until_ready() # Wait until the bot is ready
		
	@goldloop.after_loop
	async def after_goldloop(self):
		if self.goldloop.failed():
			log.warning("TMTM Gold loop has failed. Will attempt to restart in 10 minutes.")
			asyncio.sleep(600)
			log.warning("Attempting to restart TMTM Gold loop.")
			self.goldloop.restart()
	
def setup(bot):
	if (bot.get_cog("Users")) is None:
		raise RuntimeError("The 'Gold' cog requires the 'Users' cog to be loaded.")
	else:
		bot.add_cog(Gold(bot))