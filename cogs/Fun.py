import discord
from discord.ext import commands, tasks
import blueonblue
import random
import time
import asyncio
from blueonblue.config import config
from datetime import datetime, timedelta
from pytimeparse.timeparse import timeparse
from tinydb import TinyDB, Query
import tinydb.operations as tinyops
import typing
import logging
log = logging.getLogger("blueonblue")

async def kill_user(self,usr,*,reason: str="User died",duration: int=15):
	"""Function to set the user to dead."""
	tbl = self.db.table('dead')
	role_dead = self.bot._guild.get_role(config["SERVER"]["ROLES"]["DEAD"])
	users = self.bot.get_cog("Users")
	
	time = datetime.utcnow() + timedelta(minutes=duration)
	timestr = time.isoformat() # TinyDB can't store the time format. Convert it to string.
	
	await users.user_update(usr)
	await users.write_data(usr, {"dead": True})
	
	tbl.upsert({"name": usr.name, "displayname": usr.display_name, "user_id": usr.id, "revive": timestr}, Query().user_id == usr.id)
	
	usr_roles = []
	for r in usr.roles: # Make a list of roles that the bot can remove
		if (r != self.bot._guild.default_role) and (r < self.bot._guild.me.top_role) and (r.managed is not True):
			usr_roles.append(r)
	
	try:
		await usr.add_roles(role_dead, reason=reason)
		await usr.remove_roles(*usr_roles, reason=reason)
	except:
		log.warning("Failed to remove roles to kill user. User: %s. Roles: %s" % (usr.name,*usr_roles))
	log.debug("Killed user [%s|%s]" % (usr.name,usr.id))

async def revive_user(self,usr):
	"""Function to set the user to alive."""
	tbl = self.db.table('dead')
	role_dead = self.bot._guild.get_role(config["SERVER"]["ROLES"]["DEAD"])
	users = self.bot.get_cog("Users")
	
	usr_roles = []
	for r in await users.read_data(usr, "roles"):
		usr_roles.append(self.bot._guild.get_role(r["id"]))
	try:
		await usr.add_roles(*usr_roles, reason='Dead timeout expired')
		await usr.remove_roles(role_dead, reason='Dead timeout expired')
	except:
		log.warning("Failed to assign roles to revive user. User: %s. Roles: %s" % (usr.name,*usr_roles))
	tbl.remove(Query().user_id == usr.id)
	await users.remove_data(usr, "dead")
	log.debug("Revived user [%s|%s]" % (usr.name,usr.id))

class Fun(commands.Cog, name="Fun"):
	def __init__(self,bot):
		self.bot = bot
		self.db = TinyDB('db/fun.json', sort_keys=True, indent=4) # Define the database
		self.deadloop.start()
	
	def cog_unload(self):
		self.deadloop.stop()
	
	@commands.group(
		name="rr",
		aliases=["roulette"]
	)
	@blueonblue.checks.in_any_channel(config["SERVER"]["CHANNELS"]["BOT"])
	async def russian_roulette(self,ctx):
		"""How about a nice game of russian roulette?"""
		if ctx.invoked_subcommand is None:
			await ctx.send("Invalid roulette command passed.")
	
	@russian_roulette.command(
		name="play",
		cooldown_after_parsing=True
	)
	@commands.cooldown(rate=1, per=15, type=commands.BucketType.channel)
	async def russian_roulette_play(self, ctx, *, gun: str="revolver"):
		"""I want to play a game.
		
		Optional: Specify a gun to use. Current available weapons are 'revolver', 'bigiron', and 'm1911'."""
		tbl = self.db.table("roulette")
		sleeptime = 2 # Time to sleep between messages
		if not tbl.contains(Query().user_id == ctx.author.id):
			tbl.upsert({"user_id": ctx.author.id, "plays": 0, "deaths": 0, "streak": 0, "max_streak": 0},Query().user_id == ctx.author.id)
		
		# Make sure we have an up to date name for the player
		tbl.upsert({"name": ctx.author.name, "display_name": ctx.author.display_name},Query().user_id == ctx.author.id)
		
		# Set our default values
		kill = False
		text_before = [
			{"text": "Default roulette text."},
			{"text": "You should never see this."}
		]
		text_bang = "*BANG*"
		text_click = "*Click*"
		text_dead = "%s died." % (ctx.author.display_name)
		text_survive = "%s survived, stats have been updated." % (ctx.author.display_name)
			
		if gun.lower() == "revolver":
			kill = True if (random.randint(1,6) == 1) else False
			text_before = [
				{"text": "%s is feeling lucky today." % (ctx.author.mention), "sleep": sleeptime},
				{"text": "%s loads one bullet into a chamber..." % (ctx.author.display_name), "sleep": sleeptime},
				{"text": "%s gives the cylinder a good spin..." % (ctx.author.display_name), "sleep": sleeptime},
				{"text": "%s presses the gun against their head and squeezes the trigger..." % (ctx.author.display_name), "sleep": sleeptime*2}
			]
		
		elif gun.lower() == "bigiron":
			kill = True if (random.randint(1,5) == 1) else False
			text_before = [
				{"text": "%s is feeling lucky today." % (ctx.author.mention), "sleep": sleeptime},
				{"text": "%s takes the big iron from their hip." % (ctx.author.display_name), "sleep": sleeptime},
				{"text": "%s loads one bullet into a chamber, and gives the cylinder a good spin..." % (ctx.author.display_name), "sleep": sleeptime},
				{"text": "%s presses the big iron against their head and squeezes the trigger..." % (ctx.author.display_name), "sleep": sleeptime*2}
			]
			text_bang = "***BANG***"
			text_dead = "%s made one fatal slip, they were no match for the ranger with the big iron on his hip." % (ctx.author.display_name)
			text_survive = "%s returns the big iron to their hip, yee haw. Stats have been updated." % (ctx.author.display_name)
		
		elif gun.lower() == "m1911":
			kill = True
			text_before = [
				{"text": "%s is feeling lucky today." % (ctx.author.mention), "sleep": sleeptime},
				{"text": "%s loads one bullet into the magazine..." % (ctx.author.display_name), "sleep": sleeptime},
				{"text": "%s inserts the magazine and draws the slide..." % (ctx.author.display_name), "sleep": sleeptime},
				{"text": "%s presses the gun against their head and squeezes the trigger..." % (ctx.author.display_name), "sleep": sleeptime*2}
			]
			text_dead = "%s died. I don't know what they expected." % (ctx.author.display_name)
			text_survive = "Literally how. Stats have been updated."
		
		else:
			await ctx.send("%s, the weapon %s is not a valid weapon for russian roulette." % (ctx.author.mention, gun))
			commands.Command.reset_cooldown(ctx.command,ctx)
			return 0
		
		txt = text_before[0]["text"]
		message = await ctx.send(txt)
		await asyncio.sleep(text_before[0].get("sleep", sleeptime))
		for t in text_before[1:]:
			txt += "\n" + t["text"]
			await message.edit(content=txt)
			await asyncio.sleep(t.get("sleep", sleeptime))
		if kill:
			await ctx.send(text_bang)
			await kill_user(self,ctx.author,reason="User died playing russian roulette.")
			usrdata = tbl.search(Query().user_id == ctx.author.id)
			usrdata[0]["plays"] += 1
			usrdata[0]["deaths"] += 1
			usrdata[0]["streak"] = 0
			tbl.write_back(usrdata)
			await asyncio.sleep(sleeptime)
			await ctx.send(text_dead)
		else:
			await ctx.send(text_click)
			usrdata = tbl.search(Query().user_id == ctx.author.id)
			usrdata[0]["plays"] += 1
			usrdata[0]["streak"] += 1
			if usrdata[0]["streak"] > usrdata[0].get("max_streak",0):
				usrdata[0]["max_streak"] = usrdata[0]["streak"]
			tbl.write_back(usrdata)
			await asyncio.sleep(sleeptime)
			await ctx.send(text_survive)
			
	
	@russian_roulette.command(name="stats")
	async def russian_roulette_stats(self,ctx):
		"""Displays your stats for russian roulette."""
		tbl = self.db.table("roulette")
		if not tbl.contains(Query().user_id == ctx.author.id):
			await ctx.send("%s, it doesn't look like you have played russian roulette before." % (ctx.author.mention))
			return 0
		else:
			usrdata = tbl.get(Query().user_id == ctx.author.id)
			embed = discord.Embed(title = "Russian Roulette", color=0x922B21)
			embed.set_author(name=ctx.author.display_name,icon_url=ctx.author.avatar_url)
			embed.add_field(name="Plays", value=usrdata.get("plays","N/A"), inline=True)
			embed.add_field(name="Deaths", value=usrdata.get("deaths","N/A"), inline=True)
			embed.add_field(name="Streak", value=usrdata.get("streak","N/A"), inline=True)
			embed.add_field(name="Max Streak", value=usrdata.get("max_streak","N/A"), inline=True)
			await ctx.send(embed=embed)
	
	@russian_roulette.command(name="leaderboard")
	async def russian_roulette_leaderboard(self,ctx):
		"""Displays the leaderboard."""
		tbl = self.db.table("roulette")
		board = sorted(tbl.all(), key=lambda u: (u.get("max_streak",0),u.get("wins",0)),reverse=True)
		if len(board) > 0:
			embed = discord.Embed(title = "Roulette Leaderboard", color=0x922B21, description="Ranked by highest win streak.")
			embed.add_field(name="First Place", value="%s - %s" % (self.bot._guild.get_member(board[0]["user_id"]).display_name,board[0].get("max_streak",0)), inline=False)
			if len(board) > 1:
				embed.add_field(name="Second Place", value="%s - %s" % (self.bot._guild.get_member(board[1]["user_id"]).display_name,board[1].get("max_streak",0)), inline=False)
			if len(board) > 2:
				embed.add_field(name="Third Place", value="%s - %s" % (self.bot._guild.get_member(board[2]["user_id"]).display_name,board[2].get("max_streak",0)), inline=False)
			if len(board) > 3:
				embed.add_field(name="Fourth Place", value="%s - %s" % (self.bot._guild.get_member(board[3]["user_id"]).display_name,board[3].get("max_streak",0)), inline=False)
			if len(board) > 4:
				embed.add_field(name="Fifth Place", value="%s - %s" % (self.bot._guild.get_member(board[4]["user_id"]).display_name,board[4].get("max_streak",0)), inline=False)
			await ctx.send(embed=embed)
		else:
			await ctx.send("The russian roulette leaderboard is empty!")
	
	@commands.command(name="kill",hidden=True)
	@commands.check(blueonblue.checks.check_group_mods)
	async def kill(self, ctx, usr: typing.Optional[discord.Member]):
		"""Immediately kills a user.
		Users will be assigned the 'dead' role for the next 15 minutes.
		All existing user roles will be automatically reassigned when the user is revived."""
		
		if usr is None:
			await ctx.send("You need to specify a valid user!")
			raise commands.ArgumentParsingError()
		
		await kill_user(self,usr)
		await ctx.send("%s has been executed by %s" % (usr.mention, ctx.author.mention))
		
	
	@commands.command(name="revive",hidden=True)
	@commands.check(blueonblue.checks.check_group_mods)
	async def revive(self, ctx, usr: typing.Optional[discord.Member]):
		"""Immediately revives a dead user."""
		
		if usr is None:
			await ctx.send("You need to specify a valid user!")
			raise commands.ArgumentParsingError()
		
		await revive_user(self,usr)
		await ctx.send("%s has been revived by %s" % (usr.mention, ctx.author.mention))
	
	@commands.command(name="killrandom",hidden=True)
	@commands.guild_only()
	@blueonblue.checks.has_any_role_guild(config["SERVER"]["ROLES"]["ADMIN"])
	async def killrandom(self, ctx, time: str="10m"):
		"""Randomly executes a user that has sent a recent message.
		
		Selects a user that has posted in this channel within the specified period of time.
		Will only look back 100 messages, if the channel is busy it may not search back the specified duration.
		Time is specified using a number, and a unit. Accepts time units up to a week (10m, 30s, 1h, etc.)"""
		
		tmparsed = timeparse(time)
		if tmparsed is None:
			await ctx.send("You have specified an invalid length of time.")
			raise commands.ArgumentParsingError()
		
		# Convert the provided time string to a timedelta
		tmdelta = timedelta(seconds=tmparsed)
		# Convert the timedelta to a human readable format
		tm_readable = str(tmdelta)
		
		users = []
		async for m in ctx.history(limit=250,after=datetime.utcnow() - tmdelta,oldest_first=False):
			if (m.author.top_role < ctx.me.top_role) and (m.author not in users): # Ignore users that have roles above the bot
				users.append(m.author)
		
		message = "%s has ordered the execution of one of the following users:\n" % (ctx.author.mention)
		message += ", ".join(u.mention for u in users)
		message += "\nPlease confirm the execution by selecting the checkmark."
		msg = await ctx.send(message)
		await msg.add_reaction("✅")
		await msg.add_reaction("❌")
		
		def emoji_check(reaction, user):
			return user == ctx.author and (str(reaction.emoji) == '✅' or str(reaction.emoji) == '❌')
		
		try:
			reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=emoji_check)
		except asyncio.TimeoutError: # If the message times out
			await ctx.send("%s, you took too long to respond. The execution was automatically aborted." % \
						  (ctx.author.mention))
		else: # If one of the emotes was pressed
			if str(reaction.emoji) == '❌':
				# Execution
				await ctx.send ("%s, the pending execution has been aborted." % (ctx.author.mention))
				return 0
			else:
				await ctx.send("%s grabs a gun..." % (ctx.author.mention))
				await asyncio.sleep(2)
				await ctx.send("%s loads one bullet into the magazine..." % (ctx.author.display_name))
				await asyncio.sleep(2)
				await ctx.send("%s inserts the magazine and draws the slide..." % (ctx.author.display_name))
				await asyncio.sleep(2)
				await ctx.send("%s takes aim and squeezes the trigger..." % (ctx.author.display_name))
				await asyncio.sleep(5)
				deaduser = random.choice(users)
				await ctx.send("***BANG***")
				await kill_user(self,deaduser,reason="User was executed at random.")
				await asyncio.sleep(2)
				await ctx.send("%s has been executed by %s." % (deaduser.mention,ctx.author.mention))
	
	@tasks.loop(minutes=1, reconnect=True)
	async def deadloop(self):
		
		tbl = self.db.table('dead')
		tm = datetime.utcnow()
		# Begin looping through all users in the dead table
		for u in tbl:
			rls_text = u['revive']
			rls_tm = datetime.fromisoformat(rls_text)
			if tm > rls_tm: # Check if the user should be revived
				usr = self.bot._guild.get_member(u['user_id'])
				await revive_user(self,usr)
	
	@deadloop.before_loop
	async def before_deadloop(self):
		await self.bot.wait_until_ready() # Wait until the bot is ready

def setup(bot):
	if (bot.get_cog("Users")) is None:
		raise RuntimeError("The 'Fun' cog requires the 'Users' cog to be loaded.")
	else:
		bot.add_cog(Fun(bot))