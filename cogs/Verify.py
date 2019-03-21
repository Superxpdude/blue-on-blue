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
async def check_credentials(user):
	#steam_id64 = shortlist.loc[[user], 'steamProfile'].tolist()

	#token = shortlist.loc[[user], 'token'].tolist()[0]
	
	db = TinyDB('db/verify.json') # Define the database
	data = Query()
	steam_id64 = db.get(data.discord_id == user)["steam_id"]
	token = db.get(data.discord_id == user)["token"]
	res = requests.get('http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=' + config["STEAM"]["API_TOKEN"] + '&steamids=' + str(steam_id64))
	user_data = res.json()
	print('checking steam profile...', user_data)
	realname = user_data['response']['players'][0]['realname']

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
	print(root)
	print("Checking for steam id", steam_id)
	print(list(root[6]))
	for child in root[6]:
		if child.text == steam_id:
			return True
	return False

# Convert a Steam profile URL to a Steam64ID
async def get_id64(url=""):
	print(url)
	if '/profiles/' in url:
		return url.split('profiles/', 1)[-1].replace("/", "")
	elif '/id/' in url:
		rURL = 'https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?key=' + config["STEAM"]["API_TOKEN"] + '&vanityurl=' + url.split('id/', 1)[-1]
		if rURL.endswith('/'):
			rURL = rURL[:-1]
		req = requests.get(rURL)
		print('converting URL to to 64 bit steam id...')
		return req.json()['response']['steamid']
	else:
		return None

# Enters an unverified user into a .csv.
async def enter_user(user, token, url):
	#entry = pd.DataFrame([[user, url, token]], columns=['userName', 'steamProfile', 'token'])
	#entry.to_csv('Administration/unverifiedusers.csv', mode='a', header=False, index=False)
	db = TinyDB('db/verify.json') # Define the database
	data = Query()
	db.upsert({"discord_id": user, "steam_id": url, "token": token, "verified": False}, data.discord_id == user) 


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
	# TODO: maybe look into implementing an actual database, but idc.
	@commands.command(
		name="verify"
	)
	@commands.bot_has_permissions(
		manage_roles=True
	)
	#async def verify_user(steam_url, message, client):
	async def verify_user(self, ctx, *, steam_url: str=""):
		"""Verifies a user as part of the group."""
		#shortlist = pd.read_csv('Administration/unverifiedusers.csv', index_col='userName')
		db = TinyDB('db/verify.json') # Define the database
		data = Query()
		user = str(ctx.author)
		role = discord.utils.get(ctx.guild.roles, id=config["SERVER"]["ROLES"]["MEMBER"])
		steam_id64 = await get_id64(steam_url)
		if steam_id64 is None:
			await ctx.send("Invalid URL sent, please give me a proper URL.")
			return 0

		if role in ctx.author.roles:
			await ctx.send("You already have the Member role! >:(")
			return 0

		await ctx.send("Checking to see if you're in the TMTM steam group...")
		if await check_group(steam_id64):
			await ctx.send("Check successful")
		else:
			await ctx.send("Sorry, you're not a part of this arma group. You're free to apply "
							"by sending Anvil an email. musicalanvil@gmail.com.")
			return
		
		# User already present in database
		if db.contains(data.discord_id == user):
			userdata = db.get(data.discord_id == user)
			#if userdata["verified"]: # Check if the steam account is still in the steam group
				#await bot.add_roles(ctx.author, role, reason="User verified by bot")
			#elif await check_credentials(self, ctx, user):
			if await check_credentials(user):
				#await bot.add_roles(ctx.author, role, reason="User verified by bot")
				await assign_role(self, ctx, role)
				db.upsert({"discord_id": user, "verified": True}, data.discord_id == user) 
			else:
				await ctx.send("Sorry the token does not match what is on your profile.")
			return 0


		url = 'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key=' + config["STEAM"]["API_TOKEN"] + '&steamids=' + str(steam_id64)
		res = requests.get(url)
		print(res.json())

		if res.status_code == 200:
			user_token = "".join(random.sample(string.ascii_letters, 10))
			good_response = "Link checks out, I'll DM what you need to do from here."
			instructions = "Put this token into the 'real name' section of your steam profile, come back to the " \
						   "check in section of the discord and type in " + ctx.prefix + "verify once more. \n" \
						   "```" + \
						   user_token + \
						   "```"
			await enter_user(user, user_token, steam_id64)

			await ctx.send(good_response)
			try:
				await ctx.author.send(instructions)
			except message.HTTPException:
				error_instructions = "Sorry " + ctx.author.mention + " , I couldn't DM you so here are your instructions here instead."
				await ctx.send(error_instructions)
		elif res.status_code == 400:
			error_message = "Sorry " + user + ", that wasn't a valid steam profile provided, please provide a link" \
													 "similar to this: http://steamcommunity.com/profiles/76561197960287930"
			await ctx.send(error_message)
		elif res.status_code == 401:
			await ctx.send("Something's wrong, please ping an admin for a role")
			#await self.bot.send_message('362288299978784768', "Error 403, I access denied to steam")
		elif res.status_code == 402:
			await ctx.send("Something's wrong, please ping an admin for a role")
			#await self.bot.send_message('362288299978784768', "Error 403, I access denied to steam")
		elif res.status_code == 429:
			await ctx.send("I've pissed off gabe newell, please ping an admin for a role")
			#await bot.send_message('362288299978784768', "error 429, too many requests")
		elif res.status_code == 500:
			await ctx.send("Steam's having some issues, please ping an admin for a role.")
			#await bot.send_message('362288299978784768', "Error 500, Steam's having some problems.")
		elif res.status_code == 500:
			await ctx.send("Steam's having some issues, please ping an admin for a role.")
			#await bot.send_message('362288299978784768', "Error 503, Steam's having some problems.")

def setup(bot):
	bot.add_cog(Verify(bot))