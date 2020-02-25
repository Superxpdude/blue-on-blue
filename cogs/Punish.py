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

class Punish(commands.Cog, name="Punish"):
	def __init__(self, bot):
		self.bot = bot
		self.db = TinyDB('db/punish.json', sort_keys=True, indent=4) # Define the database
		self.punishloop.start()
	
	def cog_unload(self):
		self.punishloop.stop()
	
	@commands.command(
		name="punish",
		aliases=["jail", "gitmo"],
		usage="$$punish user duration"
	)
	@commands.check(blueonblue.checks.check_group_mods)
	async def punish(self, ctx, usr: typing.Optional[discord.Member], tm_str: str=""):
		"""Punishes a user
		
		Sends a user to the shadow realm for a specified period of time.
		Requires a mention, or the exact name of the user being punished wrapped in double-quotes.
		Accepts times using a number, and a letter to determine the unit.
		Only accepts time units up to a week. Months and years do not work.
		ex. 'punish userID 1d 12h' would punish the user for 1.5 days.
		ex. 'punish "Memer" 1w' would punish a user named 'Memer' for 1 week."""
		
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
				tbl = self.db.table('punish')
				users = self.bot.get_cog("Users")
				tm = datetime.utcnow()
				role_member = self.bot._guild.get_role(config["SERVER"]["ROLES"]["MEMBER"])
				role_punish = self.bot._guild.get_role(config["SERVER"]["ROLES"]["PUNISH"])
				channel_mod = self.bot.get_channel(config["SERVER"]["CHANNELS"]["MOD"])
				
				rls_tm = tm + tmdelta
				rls_text = rls_tm.isoformat() # TinyDB can't store the time format, we need to convert to string
				
				if tbl.contains(Query().id == usr.id): # User is already in punish database
					# Do not remove roles from the user, only update their release time
					tbl.upsert({'name': usr.name, 'displayname': usr.display_name, 'user_id': usr.id, 'release': rls_text}, Query().user_id == usr.id)
					await channel_mod.send("Punishment for user '%s' has been modified by '%s' to '%s'." % (usr.display_name,ctx.author.display_name,tm_readable))
				else:
					# Ensure that the user database is up to date first
					await users.user_update(usr)
					await users.write_data(usr, {"punished": True})
					
					tbl.upsert({'name': usr.name, 'displayname': usr.display_name, 'user_id': usr.id, 'release': rls_text}, Query().user_id == usr.id)
					
					usr_roles = []
					for r in usr.roles: # Make a list of roles that the bot can remove
						if (r != self.bot._guild.default_role) and (r < self.bot._guild.me.top_role) and (r.managed is not True):
							usr_roles.append(r)
					
					punish_reason = "User punished by '%s' for '%s'." % (ctx.author.display_name,tm_readable)
					try:
						await usr.add_roles(role_punish, reason=punish_reason) #Add the punish role first to prevent incorrect updating of the users database
						await usr.remove_roles(*usr_roles, reason=punish_reason)
					except:
						await channel_mod.send("Error assigning roles when punishing user %s." % (usr.mention))
						log.warning("Failed to assign roles to punish user. User: %s. Roles: %s" % (usr.name,*usr_roles))
					await channel_mod.send("User '%s' has been punished by '%s' for '%s'." % (usr.display_name,ctx.author.display_name,tm_readable))
	
	@commands.command(
		name = "punishlist"
	)
	@commands.check(blueonblue.checks.check_group_mods)
	async def punishlist(self, ctx):
		"""Displays a list of punished users
		
		Displays a full list of all users currently punished by the bot."""
		
		tbl = self.db.table('punish')
		embed = discord.Embed(title = "Punished Users", color=0xff0000) # Make our embed
		for i in tbl.all():
			rls_text = i['release']
			rls_tm = datetime.fromisoformat(rls_text) # Convert the time string to a time value
			usr_id = i['user_id']
			usr = self.bot._guild.get_member(i['user_id']) # Get the user by their ID
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
		name="release"
	)
	@commands.check(blueonblue.check_group_mods)
	async def release(self, ctx, usr: typing.Optional[discord.Member]):
		"""Releases a user from punishment
		
		Use this command with a userID or user mention to immediately release a user from the shadow realm."""
		
		if usr is None:
			await ctx.send("You need to specify a valid user!")
			raise commands.ArgumentParsingError()
		
		tbl = self.db.table('punish')
		gld = self.bot._guild
		role_punish = gld.get_role(config["SERVER"]["ROLES"]["PUNISH"])
		channel_mod = self.bot.get_channel(config["SERVER"]["CHANNELS"]["MOD"])
		if gld is None:
			return 0
		
		usr_id = usr.id
		
		users = self.bot.get_cog("Users")
		usr_roles = []
		for r in await users.read_data(usr, "roles"):
			usr_roles.append(self.bot._guild.get_role(r["id"]))
		
		if tbl.contains(Query().user_id == usr_id):
			try:
				await usr.remove_roles(role_punish, reason="Punishment removed by '%s'." % (ctx.author.display_name))
				await usr.add_roles(*usr_roles, reason="Punishment removed by '%s'." % (ctx.author.display_name))
			except:
				await channel_mod.send("Error assigning roles when releasing user %s from punishment. Please assign roles manually." % (usr.mention))
				log.warning("Failed to assign roles to release user from punishment. User: [%s]. Roles: [%s]" % (usr.name,*usr_roles))
			await channel_mod.send("User '%s' has been released from punishment by '%s'." % (usr.mention,ctx.author.mention))	
			tbl.remove(Query().user_id == usr_id)
			await users.remove_data(usr, "punished")
		else:
			await ctx.send("Error, could not locate user in punishment database.")
	
	@tasks.loop(minutes=1, reconnect=True)
	async def punishloop(self):
		tbl = self.db.table('punish')
		tm = datetime.utcnow()
		gld = self.bot._guild
		role_punish = gld.get_role(config["SERVER"]["ROLES"]["PUNISH"])
		channel_mod = self.bot.get_channel(config["SERVER"]["CHANNELS"]["MOD"])
		if gld is None:
			return 0
			
		users = self.bot.get_cog("Users")
		
		# Begin looping through all users in the punish table
		for u in tbl:
			rls_text = u['release']
			rls_tm = datetime.fromisoformat(rls_text)
			
			if tm > rls_tm: # Check if the user should be released
				usr = gld.get_member(u['user_id'])
				usr_roles = []
				
				if usr is None:
					await channel_mod.send("Failed to remove punishment from user '%s', user may no longer be present in the server." % (u['name']))
					# A copy of the same information as below. But using information from the database.
					await channel_mod.send("User '%s' has been released from punishment due to timeout expiry." % (u['name']))
					tbl.remove(Query().user_id == u['user_id'])
					await users.remove_data(u['user_id'], "punished")
				else:
					for r in await users.read_data(usr, "roles", []):
						usr_roles.append(self.bot._guild.get_role(r["id"]))
					try:
						await usr.remove_roles(role_punish, reason='Punishment timeout expired')
						await usr.add_roles(*usr_roles, reason='Punishment timeout expired')
					except:
						await channel_mod.send("Error assigning roles when releasing user %s from punishment." % (usr.mention))
						log.warning("Failed to assign roles to release user from punishment. User: [%s]. Roles: [%s]" % (usr.name,*usr_roles))
					await channel_mod.send("User '%s' has been released from punishment due to timeout expiry." % (usr.display_name))
					tbl.remove(Query().user_id == usr.id)
					await users.remove_data(usr, "punished")
				
	
	@punishloop.before_loop
	async def before_punishloop(self):
		await self.bot.wait_until_ready() # Wait until the bot is ready
		
	@punishloop.after_loop
	async def after_punishloop(self):
		if self.punishloop.failed():
			log.warning("Punish loop has failed. Attempting to restart.")
			self.punishloop.restart()

def setup(bot):
	if (bot.get_cog("Users")) is None:
		raise RuntimeError("The 'Punish' cog requires the 'Users' cog to be loaded.")
	else:
		bot.add_cog(Punish(bot))