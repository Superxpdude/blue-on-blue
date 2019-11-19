import discord
from discord.ext import commands, tasks
import blueonblue
import random
import time
import asyncio
from blueonblue.config import config
from datetime import datetime, timedelta
from tinydb import TinyDB, Query
import tinydb.operations as tinyops
import typing
import logging
log = logging.getLogger("blueonblue")

async def kill_user(self,usr,reason: str="User died"):
	"""Function to set the user to dead."""
	tbl = self.db.table('dead')
	role_dead = self.bot._guild.get_role(config["SERVER"]["ROLES"]["DEAD"])
	users = self.bot.get_cog("Users")
	
	time = datetime.utcnow() + timedelta(minutes=15)
	timestr = time.isoformat() # TinyDB can't store the time format. Convert it to string.
	
	await users.user_update(usr)
	await users.write_data(usr, {"dead": True})
	
	tbl.upsert({"name": usr.name, "displayname": usr.display_name, "user_id": usr.id, "revive": timestr}, Query().user_id == usr.id)
	
	usr_roles = []
	for r in usr.roles: # Make a list of roles that the bot can remove
		if (r != self.bot._guild.default_role) and (r < self.bot._guild.me.top_role):
			usr_roles.append(r)
	
	await usr.add_roles(role_dead, reason=reason)
	await usr.remove_roles(*usr_roles, reason=reason)

async def revive_user(self,usr):
	"""Function to set the user to alive."""
	tbl = self.db.table('dead')
	role_dead = self.bot._guild.get_role(config["SERVER"]["ROLES"]["DEAD"])
	users = self.bot.get_cog("Users")
	
	usr_roles = []
	for r in await users.read_data(usr, "roles"):
		usr_roles.append(self.bot._guild.get_role(r["id"]))
	await usr.add_roles(*usr_roles, reason='Dead timeout expired')
	await usr.remove_roles(role_dead, reason='Dead timeout expired')
	tbl.remove(Query().user_id == usr.id)
	await users.remove_data(usr, "dead")

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
		
		Optional: Specify a gun to use. Current available weapons are 'revolver', and 'm1911'."""
		tbl = self.db.table("roulette")
		sleeptime = 2 # Time to sleep between messages
		if not tbl.contains(Query().user_id == ctx.author.id):
			tbl.upsert({"user_id": ctx.author.id, "plays": 0, "deaths": 0, "streak": 0},Query().user_id == ctx.author.id)
		
		# Make sure we have an up to date name for the player
		tbl.upsert({"name": ctx.author.name, "display_name": ctx.author.display_name},Query().user_id == ctx.author.id)
		
		# A regular revolver
		if gun.lower() == "revolver":
			kill = True if (random.randint(1,6) == 1) else False
			txt = "%s is feeling lucky today." % (ctx.author.mention)
			message = await ctx.send(txt)
			await asyncio.sleep(sleeptime)
			txt += "\n%s loads one bullet into a chamber..." % (ctx.author.display_name)
			await message.edit(content=txt)
			await asyncio.sleep(sleeptime)
			txt += "\n%s gives the cylinder a good spin..." % (ctx.author.display_name)
			await message.edit(content=txt)
			await asyncio.sleep(sleeptime)
			txt += "\n%s presses the gun against their head and squeezes the trigger..." % (ctx.author.display_name)
			await message.edit(content=txt)
			await asyncio.sleep(sleeptime*2)
			if kill:
				await ctx.send("*BANG*")
				await kill_user(self,ctx.author,reason="User died playing russian roulette.")
				tbl.update(tinyops.increment("plays"), Query().user_id == ctx.author.id)
				tbl.update(tinyops.increment("deaths"), Query().user_id == ctx.author.id)
				tbl.update(tinyops.set("streak",0), Query().user_id == ctx.author.id)
				await asyncio.sleep(sleeptime)
				await ctx.send("%s died.")
			else:
				await ctx.send("*Click*")
				tbl.update(tinyops.increment("plays"), Query().user_id == ctx.author.id)
				tbl.update(tinyops.increment("streak"), Query().user_id == ctx.author.id)
				await asyncio.sleep(sleeptime)
				await ctx.send("%s survived, stats have been updated." % (ctx.author.display_name))
			
		elif gun.lower() == "m1911":
			txt = "%s is feeling lucky today." % (ctx.author.mention)
			message = await ctx.send(txt)
			await asyncio.sleep(sleeptime)
			txt += "\n%s loads one bullet into the magazine..." % (ctx.author.display_name)
			await message.edit(content=txt)
			await asyncio.sleep(sleeptime)
			txt += "\n%s inserts the magazine and draws the slide..." % (ctx.author.display_name)
			await message.edit(content=txt)
			await asyncio.sleep(sleeptime)
			txt += "\n%s presses the gun against their head and squeezes the trigger..." % (ctx.author.display_name)
			await message.edit(content=txt)
			await asyncio.sleep(sleeptime*2)
			await ctx.send("*BANG*")
			await kill_user(self,ctx.author,reason="User died playing russian roulette.")
			tbl.update(tinyops.increment("plays"), Query().user_id == ctx.author.id)
			tbl.update(tinyops.increment("deaths"), Query().user_id == ctx.author.id)
			tbl.update(tinyops.set("streak",0), Query().user_id == ctx.author.id)
			await asyncio.sleep(sleeptime)
			await ctx.send("%s died. I don't know what they expected." % (ctx.author.display_name))
		
		else:
			await ctx.send("%s, the weapon %s is not a valid weapon for russian roulette." % (ctx.author.mention, gun))
			commands.Command.reset_cooldown(ctx.command,ctx)
	
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
			embed.add_field(name="Plays", value=usrdata["plays"], inline=True)
			embed.add_field(name="Deaths", value=usrdata["deaths"], inline=True)
			embed.add_field(name="Streak", value=usrdata["streak"], inline=True)
			await ctx.send(embed=embed)
	
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