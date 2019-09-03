import discord
from discord.ext import commands
from settings import config
import json
import requests
import random
from tinydb import TinyDB, Query
from lxml import etree
from lxml.etree import fromstring
import string


# Checks the user's steam account to check if they placed the token in their steam profile.
# returns true or false
async def check_credentials(user, userid):
	# steam_id64 = shortlist.loc[[user], 'steamProfile'].tolist()

	# token = shortlist.loc[[user], 'token'].tolist()[0]
	
	db = TinyDB('db/verify.json', sort_keys=True, indent=4) # Define the database
	data = Query()
	steam_id64 = db.get(data.discord_id == userid)["steam_id"]
	token = db.get(data.discord_id == userid)["token"]
	res = requests.get('http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=' + config["STEAM"]["API_TOKEN"] + '&steamids=' + str(steam_id64))
	user_data = res.json()
	# print('checking steam profile...', user_data)
	try:
		realname = user_data['response']['players'][0]['realname']
	except KeyError:
		realname = ""
	if token in realname:
		return True
	else:
		return False


# Checks if a user is in a steam group
async def check_group(steam_id):
	req = requests.request('GET', 'https://steamcommunity.com/gid/%s/memberslistxml/?xml=1' % (config["STEAM"]["GROUP"]))
	a = req.content
	type(a)
	root = etree.fromstring(a)
	# print(root)
	# print("Checking for steam id", steam_id)
	# print(list(root[6]))
	for child in root[6]:
		if child.text == steam_id:
			return True
	return False


# Convert a Steam profile URL to a Steam64ID
async def get_id64(url=""):
	# print(url)
	if '/profiles/' in url:
		return url.split('profiles/', 1)[-1].replace("/", "")
	elif '/id/' in url:

		# TODO: Get rid of final '/' character when sending in vanity URL's
		rURL = 'https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key=' + config["STEAM"]["API_TOKEN"] + '&vanityurl=' + url.split('id/', 1)[-1]
		if rURL.endswith('/'):
			rURL = rURL[:-1]
		req = requests.get(rURL)

		return req.json()['response']['steamid']
	else:
		return None


# Enters an unverified user into a .csv.
async def enter_user(user, userid, token, url):
	# entry = pd.DataFrame([[user, url, token]], columns=['userName', 'steamProfile', 'token'])
	# entry.to_csv('Administration/unverifiedusers.csv', mode='a', header=False, index=False)
	db = TinyDB('db/verify.json', sort_keys=True, indent=4) # Define the database
	data = Query()
	db.upsert({"discord_id": userid, "discord_name": user, "steam_id": url, "token": token, "verified": False}, data.discord_id == userid) 


# Assigns roles to a user.
async def assign_role(self, ctx, role):
	try:
		await ctx.author.add_roles(role)
		await ctx.send("Welcome " + ctx.author.mention + ", your role has been assigned.")
	except discord.Forbidden:
		await ctx.send("I lack permissions to assign that role, go bother an admin please")
	return 0


class Verify(commands.Cog, name="Verify"):
	"""Verify that users are part of the steam group."""

	def __init__(self, bot):
		self.bot = bot
	
	# These functions were written by Arlios
	# Originally pulled from his discord bot
	# Modified by Superxpdude
	
	# Define some variables
	STEAM_API_KEY = config["STEAM"]["API_TOKEN"]
	STEAM_GROUP_ID = config["STEAM"]["GROUP"]
	MEMBER_ROLE = config["SERVER"]["ROLES"]["MEMBER"]
	
	# This whole process will ask users to enter a command for their steam profiles, upon successful request, the user
	# is stored into a .csv with a token which the bot will check if the user entered their token on their steam accounts
	@commands.command(
		name="verify"
	)
	@commands.bot_has_permissions(
		manage_roles=True
	)
	# async def verify_user(steam_url, message, client):
	async def verify_user(self, ctx, *, steam_url: str=""):
		"""Verifies a user as part of the group.

		Requires a full steam profile URL for authentication."""
		# shortlist = pd.read_csv('Administration/unverifiedusers.csv', index_col='userName')
		# print(ctx.author.id)
		db = TinyDB('db/verify.json', sort_keys=True, indent=4) # Define the database
		data = Query()
		user = str(ctx.author)
		userid = ctx.author.id
		role = discord.utils.get(ctx.guild.roles, id=config["SERVER"]["ROLES"]["MEMBER"])

		# Check for the member role
		if role in ctx.author.roles:
			await ctx.send("You already have the Member role! >:(")
			return 0

		if db.contains(data.discord_id == userid):
			await ctx.send("You're already in our systems but I'll DM you your token and instructions once more")



		# User already present in database
		# if db.contains(data.discord_id == userid):
		# 	userdata = db.get(data.discord_id == userid)
		# if userdata["verified"]: # Check if the steam account is still in the steam group
		# 	await bot.add_roles(ctx.author, role, reason="User verified by bot")
		# elif await check_credentials(self, ctx, user):
		# 	if await check_credentials(user, userid):
		# 	await bot.add_roles(ctx.author, role, reason="User verified by bot")
		# 	await assign_role(self, ctx, role)
		# 	db.upsert({"discord_id": userid, "verified": True}, data.discord_id == userid)
		# else:
		# 	await ctx.send("Sorry the token does not match what is on your profile.")
		# return 0
		steam_id64 = await get_id64(steam_url)

		if steam_id64 is None:
			await ctx.send("Invalid URL sent, please give me a proper URL.")
			return 0

		await ctx.send("Checking to see if you're in the TMTM steam group...")
		if await check_group(steam_id64):
			await ctx.send("Check successful")
		else:
			await ctx.send("Sorry, you're not a part of this arma group. You're free to apply "
							"by sending Anvil an email. musicalanvil@gmail.com.")
			return

		url = 'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key=' + config["STEAM"]["API_TOKEN"] + '&steamids=' + str(steam_id64)
		res = requests.get(url)

		if res.status_code == 200:
			user_token = "".join(random.sample(string.ascii_letters, 10))
			good_response = "Link checks out, I'll DM what you need to do from here."
			instructions = "Put this token into the 'real name' section of your steam profile, come back to the " \
						   "check in section of the discord and type in " + ctx.prefix + "checkin \n" \
						   "```" + \
						   user_token + \
						   "```"
			await enter_user(user, userid, user_token, steam_id64)

			await ctx.send(good_response)

			# TODO: Fix this try/catch block later to properly catch an HTTP Exception
			# try:
			await ctx.author.send(instructions)

			# except message.HTTPException:
			# 	error_instructions = "Sorry " + ctx.author.mention + " ,
		# 			I couldn't DM you so here are your instructions here instead."
			# 	await ctx.send(error_instructions)
		else:
			await throw_error(res, ctx)

	@commands.command(
		name="checkin"
	)
	@commands.bot_has_permissions(
		manage_roles=True
	)
	async def check_in(self, ctx, *, steam_url: str=""):
		"""Verifies a user as part of the group.

		Requires a full steam profile URL for authentication."""
		# shortlist = pd.read_csv('Administration/unverifiedusers.csv', index_col='userName')
		# print(ctx.author.id)
		db = TinyDB('db/verify.json', sort_keys=True, indent=4)  # Define the database
		data = Query()
		user = str(ctx.author)
		userid = ctx.author.id
		role = discord.utils.get(ctx.guild.roles, id=config["SERVER"]["ROLES"]["MEMBER"])

		if db.contains(data.discord_id == userid):
			await ctx.send("Checking your profile now.")

			if db.get(data.discord_id == userid)['verified'] or await check_credentials(user, userid):
				db.upsert({"discord_id": userid, "verified": True}, data.discord_id == userid)
				await assign_role(self, ctx, role)
				return 0
			else:
				await ctx.send("Sorry the token does not match what is on your profile.\n"
				"Use " + ctx.prefix + "verify with your steam URL if you need a new token.")
				return 0
		else:
			await ctx.send("I haven't even sent you a token yet!, please type in " + ctx.prefix + "verify for a token.")

	@commands.Cog.listener()
	async def on_member_join(self,member):
		if member.guild.id == config["SERVER"]["ID"]:
			channel = self.bot.get_channel(config["SERVER"]["CHANNELS"]["CHECK_IN"])
			prefix = config["BOT"]["CMD_PREFIXES"][0]
			await channel.send("Welcome to TMTM " + member.mention + ", To gain access "
						"to the server, please type %sverify <link-to-your-steam-profile>. "
						"If you are not in TMTM at the moment, "
						"please go through the regular application process to join." % (prefix))

def setup(bot):
	bot.add_cog(Verify(bot))

async def throw_error(res, ctx):
	if res.status_code == 400:
		error_message = "Sorry, that wasn't a valid steam profile provided, please provide a link" \
									  "similar to this: http://steamcommunity.com/profiles/76561197960287930"
		await ctx.send(error_message)

	elif res.status_code == 401:
		await ctx.send("Something's wrong, please ping an admin for a role. Error 401")
	# await self.bot.send_message('362288299978784768', "Error 403, I access denied to steam")
	elif res.status_code == 402:
		await ctx.send("Something's wrong, please ping an admin for a role. Error 402")
	# await self.bot.send_message('362288299978784768', "Error 403, I access denied to steam")
	elif res.status_code == 429:
		await ctx.send("I've pissed off gabe newell, please ping an admin for a role. Error 429")
	# await bot.send_message('362288299978784768', "error 429, too many requests")
	elif res.status_code == 500:
		await ctx.send("Steam's having some issues, please ping an admin for a role. Error 500")
	# await bot.send_message('362288299978784768', "Error 500, Steam's having some problems.")
	elif res.status_code == 500:
		await ctx.send("Steam's having some issues, please ping an admin for a role. Error 500")
	# await bot.send_message('362288299978784768', "Error 503, Steam's having some problems.")
