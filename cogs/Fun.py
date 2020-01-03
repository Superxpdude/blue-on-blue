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
	for r in await users.read_data(usr, "roles", []):
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
	#@blueonblue.checks.in_any_channel(config["SERVER"]["CHANNELS"]["BOT"])
	async def russian_roulette(self,ctx):
		"""How about a nice game of russian roulette?"""
		if ctx.invoked_subcommand is None:
			await ctx.send("Invalid roulette command passed.")
	
	@russian_roulette.command(
		name="play",
		cooldown_after_parsing=True
	)
	@blueonblue.checks.in_any_channel(config["SERVER"]["CHANNELS"]["BOT"])
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
	
	@russian_roulette.command(
		name="force"
	)
	@commands.check(blueonblue.checks.check_group_mods)
	async def russian_roulette_force(self, ctx, target: typing.Optional[discord.Member]):
		"""Forces a user to play russian roulette with a revolver."""
		
		if target is None:
			await ctx.send("You need to specify a valid user!")
			raise commands.ArgumentParsingError()
		
		if target is ctx.me:
			await ctx.send("How can a bot hold a gun if it doesn't have any hands!")
			raise commands.ArgumentParsingError()
		
		# The code below is just a modified version of the regular roulette command
		
		tbl = self.db.table("roulette")
		sleeptime = 2 # Time to sleep between messages
		if not tbl.contains(Query().user_id == target.id):
			tbl.upsert({"user_id": target.id, "plays": 0, "deaths": 0, "streak": 0, "max_streak": 0},Query().user_id == target.id)
		
		# Make sure we have an up to date name for the player
		tbl.upsert({"name": target.name, "display_name": target.display_name},Query().user_id == target.id)
		
		# Set our default values
		kill = True if (random.randint(1,6) == 1) else False
		text_before = [
			{"text": "%s thinks that %s is feeling lucky today." % (ctx.author.mention, target.mention), "sleep": sleeptime},
			{"text": "%s loads one bullet into a chamber, and gives the cylinder a good spin..." % (ctx.author.display_name), "sleep": sleeptime},
			{"text": "%s hands the gun to %s..." % (ctx.author.display_name,target.display_name), "sleep": sleeptime},
			{"text": "%s presses the gun against their head and squeezes the trigger..." % (target.display_name), "sleep": sleeptime*2}
		]
		text_bang = "*BANG*"
		text_click = "*Click*"
		text_dead = "%s died." % (target.display_name)
		text_survive = "%s survived, stats have been updated." % (target.display_name)
		
		txt = text_before[0]["text"]
		message = await ctx.send(txt)
		await asyncio.sleep(text_before[0].get("sleep", sleeptime))
		for t in text_before[1:]:
			txt += "\n" + t["text"]
			await message.edit(content=txt)
			await asyncio.sleep(t.get("sleep", sleeptime))
		if kill:
			await ctx.send(text_bang)
			await kill_user(self,target,reason="User died playing forced russian roulette.")
			usrdata = tbl.search(Query().user_id == target.id)
			usrdata[0]["plays"] += 1
			usrdata[0]["deaths"] += 1
			usrdata[0]["streak"] = 0
			tbl.write_back(usrdata)
			await asyncio.sleep(sleeptime)
			await ctx.send(text_dead)
		else:
			await ctx.send(text_click)
			usrdata = tbl.search(Query().user_id == target.id)
			usrdata[0]["plays"] += 1
			usrdata[0]["streak"] += 1
			if usrdata[0]["streak"] > usrdata[0].get("max_streak",0):
				usrdata[0]["max_streak"] = usrdata[0]["streak"]
			tbl.write_back(usrdata)
			await asyncio.sleep(sleeptime)
			await ctx.send(text_survive)
	
	@russian_roulette.command(name="tournament",aliases=["tourney"],cooldown_after_parsing=True)
	@blueonblue.checks.in_any_channel(config["SERVER"]["CHANNELS"]["BOT"])
	@commands.cooldown(rate=1, per=1800, type=commands.BucketType.channel)
	async def russian_roulette_tournament(self,ctx):
		"""Somehow more dangerous than normal russian roulette."""
		tbl = self.db.table("roulette")
		sleeptime = 2
		
		# Post the message to gather contestants
		msg = await ctx.send("%s has started a roulette tournament!" \
							"\nSelect the 🎲 to enter the tournament. The tournament will begin in two minutes." \
							"\nThe tournament host can start the tournament early by selecting the checkmark." % (ctx.author.mention))
		await msg.add_reaction("✅")
		await msg.add_reaction("🎲")
		
		def emoji_check(reaction, user):
			return user == ctx.author and (str(reaction.emoji) == '✅')
		
		try:
			reaction, user = await self.bot.wait_for("reaction_add", timeout=120, check=emoji_check)
		except asyncio.TimeoutError: # Bot has waited two minutes
			await ctx.send("Time's up! Starting the tournament now!")
		else:
			await ctx.send("Starting the tournament now!")
		
		cache_msg = discord.utils.get(self.bot.cached_messages, id=msg.id)
		
		# Grab our user list
		userlist = [ctx.author] # The author has to participate
		for r in cache_msg.reactions:
			if r.emoji == "🎲":
				usrs =  await r.users().flatten()
				for u in usrs:
					if (u not in userlist) and (u.bot is False):
						userlist.append(u)
		
		if len(userlist) <= 1:
			await ctx.send("Tournament aborted due to lack of participants.")
			commands.Command.reset_cooldown(ctx.command,ctx)
			return
		
		txt = "A tournament is beginning!\nThe participants are: "
		txt += ", ".join(u.mention for u in userlist)
		await ctx.send(txt)
		
		for u in userlist:
			if not tbl.contains(Query().user_id == u.id):
				tbl.upsert({"user_id": u.id, "plays": 0, "deaths": 0, "streak": 0, "max_streak": 0},Query().user_id == u.id)
		
		round = 1
		
		cylinderpos = random.SystemRandom().randint(1,6)
		deadpos = random.SystemRandom().randint(1,6)
		# Start our loop
		while len(userlist) > 1:
			await ctx.send("ROUND %s, START" % (round))
			await asyncio.sleep(2)
			random.SystemRandom().shuffle(userlist)
			templist = []
			for u in userlist:
				text_before = [
					{"text": "%s picks up the revolver..." % (u.mention), "sleep": sleeptime},
					{"text": "%s loads one bullet into a chamber..." % (u.display_name), "sleep": sleeptime},
					{"text": "%s gives the cylinder a good spin..." % (u.display_name), "sleep": sleeptime},
					{"text": "%s presses the gun against their head and squeezes the trigger..." % (u.display_name), "sleep": sleeptime*2}
				]
				txt = text_before[0]["text"]
				msg = await ctx.send(txt)
				await asyncio.sleep(text_before[0].get("sleep", sleeptime))
				for t in text_before[1:]:
					txt += "\n" + t["text"]
					await msg.edit(content=txt)
					await asyncio.sleep(t.get("sleep", sleeptime))
				if (random.SystemRandom().randint(1,6) == 1):
					# User was killed
					await ctx.send("*BANG*")
					await kill_user(self,u,reason="User died in russian roulette tournament")
					usrdata = tbl.search(Query().user_id == u.id)
					usrdata[0]["plays"] += 1
					usrdata[0]["deaths"] += 1
					usrdata[0]["streak"] = 0
					tbl.write_back(usrdata)
					await asyncio.sleep(sleeptime)
					await ctx.send("%s has been eliminated from the tournament." % (u.mention))
				else:
					# User survived
					await ctx.send("*Click*")
					usrdata = tbl.search(Query().user_id == u.id)
					usrdata[0]["plays"] += 1
					usrdata[0]["streak"] += 1
					if usrdata[0]["streak"] > usrdata[0].get("max_streak",0):
						usrdata[0]["max_streak"] = usrdata[0]["streak"]
					tbl.write_back(usrdata)
					await asyncio.sleep(sleeptime)
					await ctx.send("%s survived round %s." % (u.mention,round))
					templist.append(u) # Add the user to the survivors list
				await asyncio.sleep(3) # Sleep three seconds between users
			userlist = templist.copy()
			txt = "ROUND %s COMPLETE." % (round)
			if len(userlist) > 1:
				txt += " The following participants remain.\n"
				txt += ", ".join(u.mention for u in templist)
				txt += "\nThe next round will begin in 10 seconds."
			round += 1 # Increment the round counter
			await ctx.send(txt)
			if len(userlist) > 1:
				await asyncio.sleep(10)
		
		# Tournament over
		if len(userlist) > 0:
			# One user survived
			await ctx.send("%s has won the tournament!" % userlist[0].mention)
		else:
			# No users survived
			await ctx.send("This tournament has no winner. All remaining participants died in the same round.")
		
		# Reset the cooldown
		commands.Command.reset_cooldown(ctx.command,ctx)
	
	@russian_roulette.command(name="stats")
	@blueonblue.checks.in_any_channel(config["SERVER"]["CHANNELS"]["BOT"])
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
	@blueonblue.checks.in_any_channel(config["SERVER"]["CHANNELS"]["BOT"])
	async def russian_roulette_leaderboard(self,ctx):
		"""Displays the leaderboard."""
		tbl = self.db.table("roulette")
		board = sorted(tbl.all(), key=lambda u: (u.get("max_streak",0),(u.get("plays",0)-u.get("deaths",0))/max(u.get("deaths",0),1)),reverse=True)
		if len(board) > 0:
			embed = discord.Embed(title = "Roulette Leaderboard", color=0x922B21, description="Ranked by highest win streak.")
			try:
				usr1 = self.bot._guild.get_member(board[0]["user_id"]).display_name
			except:
				usr1 = board[0]["display_name"]
			embed.add_field(name="First Place", value="%s - %s" % (usr1,board[0].get("max_streak",0)), inline=False)
			if len(board) > 1:
				try:
					usr2 = self.bot._guild.get_member(board[1]["user_id"]).display_name
				except:
					usr2 = board[1]["display_name"]
				embed.add_field(name="Second Place", value="%s - %s" % (usr2,board[1].get("max_streak",0)), inline=False)
			if len(board) > 2:
				try:
					usr3 = self.bot._guild.get_member(board[2]["user_id"]).display_name
				except:
					usr3 = board[2]["display_name"]
				embed.add_field(name="Third Place", value="%s - %s" % (usr3,board[2].get("max_streak",0)), inline=False)
			if len(board) > 3:
				try:
					usr4 = self.bot._guild.get_member(board[3]["user_id"]).display_name
				except:
					usr4 = board[3]["display_name"]
				embed.add_field(name="Fourth Place", value="%s - %s" % (usr4,board[3].get("max_streak",0)), inline=False)
			if len(board) > 4:
				try:
					usr5 = self.bot._guild.get_member(board[4]["user_id"]).display_name
				except:
					usr5 = board[4]["display_name"]
				embed.add_field(name="Fifth Place", value="%s - %s" % (usr5,board[4].get("max_streak",0)), inline=False)
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
		
		if usr is ctx.me:
			await ctx.send("I'm sorry %s. I'm afraid I can't do that." % (ctx.author.mention))
			return
		
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