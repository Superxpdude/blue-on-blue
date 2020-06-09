import discord
from discord.ext import commands
import blueonblue
from blueonblue.config import config
import json
import requests
import random
from tinydb import TinyDB, Query
import string

import logging
log = logging.getLogger("blueonblue")

async def steam_getid64(url=""):
	"""Converts a Steam profile URL to a Steam64ID"""
	if "/profiles/" in url:
		return url.split("profiles/", 1)[-1].replace("/", "")
	elif "/id/" in url:
		vanity = url.split("id/", 1)[-1]
		if vanity.endswith("/"):
			vanity = vanity[:-1]
		rURL = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
		rPARAMS = {
			"key": config["STEAM"]["API_TOKEN"],
			"vanityurl": vanity
		}
		response = requests.get(rURL, params = rPARAMS)
		if response.status_code == 200:
			try: 
				return response.json()["response"]["steamid"]
			except:
				return None
		else:
			return response.status_code
	else:
		return None

async def steam_check_token(self, usr):
	"""Uses a saved SteamID to check if a user has placed the token in their profile.
	Returns one of the following:
		True - Token is in steam real name
		False - Token is not in steam real name
		None - Unable to retrieve real name from returned data
		Int - HTTP status code from steam API"""
	
	steam_id64 = self.db.get(Query().discord_id == usr.id)["steam_id"]
	token = self.db.get(Query().discord_id == usr.id)["token"]
	
	rURL = "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
	rPARAMS = {
		"key": config["STEAM"]["API_TOKEN"],
		"steamids": steam_id64
	}
	response = requests.get(rURL, params = rPARAMS) # Make the request
	if response.status_code == 200:
		try: 
			realname = response.json()["response"]["players"][0]["realname"]
		except:
			return None
		if token in realname:
			return True
		else:
			return False
	else:
		return response.status_code

async def steam_check_group_membership(steam_id64):
	"""Uses a SteamID to check if the user is in the Steam group.
	Checks using the short groupID that's found on the group edit page."""	
	
	rURL = "https://api.steampowered.com/ISteamUser/GetUserGroupList/v1/"
	rPARAMS = {
		"key": config["STEAM"]["API_TOKEN"],
		"steamid": steam_id64
	}
	response = requests.get(rURL, params = rPARAMS) # Make the request
	if response.status_code == 200: # If the request went through
		steam_group = int(config["STEAM"]["GROUP"])
		groups = response.json()["response"]["groups"]
		for g in groups:
			if int(g["gid"]) == steam_group:
				return True # If the group is found, return true
		return False # If the group was not found, return false
	return response.status_code # If the request failed, return the status code

async def steam_throw_error(self, ctx, status_code):
	"""Throws an error depending on the status code received from the API request."""
	if status_code == 400:
		await ctx.send("That doesn't seem to be a valid steam profile. Please provide a link "
					"similar to this: <https://steamcommunity.com/profiles/76561198329777700>")
	elif status_code == 403:
		await ctx.send("I ran into an issue getting data from Steam. Please verify that your "
					"Steam profile visibility is set to 'Public'. If it is, please ping an admin "
					"for a role. Error 403")
	elif status_code == 429:
		await ctx.send("I appear to be rate-limited by Steam. Please ping an admin for a role. Error 429")
		log.warning("Received code 429 from Steam.")
	elif status_code == 500:
		await ctx.send("Steam appears to be having some issues. Please ping an admin for a role. Error 500")
		log.warning("Received code 500 from Steam.")
	elif status_code == 503:
		await ctx.send("Steam appears to be having some issues. Please ping an admin for a role. Error 503")
		log.warning("Received code 503 from Steam.")
	else:
		await ctx.send("Something has gone wrong. Please ping an admin for a role. Error %s" % (status_code))
		log.warning("Received code %s from Steam." % (status_code))

async def assign_roles(self,ctx,usr):
	"""Assigns roles to a member once they verify themselves.
	Uses roles from the users database if present, otherwise assigns the member role."""
	usercog = self.bot.get_cog("Users")
	member_role = self.bot._guild.get_role(config["SERVER"]["ROLES"]["MEMBER"])
	punish_role = self.bot._guild.get_role(config["SERVER"]["ROLES"]["PUNISH"])
	
	if usercog is not None: # Users cog is loaded
		punished = await usercog.read_data(usr, "punished")
		data_roles = await usercog.read_data(usr, "roles")
		if punished is True:
			try:
				await usr.add_roles(punish_role, reason="User verified")
				return True
			except:
				return False
		elif data_roles is not None:
			roles = []
			for r in await usercog.read_data(usr, "roles"):
				roles.append(self.bot._guild.get_role(r["id"]))
			if len(roles) == 0:
				roles.append(member_role)
			try:
				await usr.add_roles(*roles, reason="User verified")
				return True
			except:
				return False
		else:
			try:
				await usr.add_roles(member_role, reason="User verified")
				return True
			except:
				return False
	else:
		try:
			await usr.add_roles(member_role, reason="User verified")
			return True
		except:
			return False
	

class Verify(commands.Cog, name="Verify"):
	"""Verify that users are part of the steam group."""
	
	def __init__(self, bot):
		self.bot = bot
		self.db = TinyDB("db/verify.json", sort_keys=True, indent=4) # Define the database
	
	@commands.command(name="verify")
	@commands.bot_has_permissions(manage_roles=True)
	@blueonblue.checks.in_any_channel(config["SERVER"]["CHANNELS"]["CHECK_IN"])
	async def verify_user(self, ctx, *, steam_url: str=""):
		"""Verifies a user as part of the group.
		
		Requires a full Steam profile URL for authentication."""
		
		usr = ctx.author
		member_role = self.bot._guild.get_role(config["SERVER"]["ROLES"]["MEMBER"])
		
		# Check if the user already has the member role
		if member_role in ctx.author.roles:
			await ctx.send("%s, you already have the member role." % (ctx.author.mention))
			return 0
		
		# Get the user's steamID64
		steam_id64 = await steam_getid64(steam_url)
		if steam_id64 is None: # If we received None, let the user know that we couldn't find their profile.
			await ctx.send("Invalid URL sent, please give me a valid URL.")
			return 0
		elif type(steam_id64) is int: # If received a status code, throw an error
			return await steam_throw_error(self,ctx,steam_id64)
		
		if self.db.contains(Query().discord_id == usr.id):
			await ctx.send("You're already in our systems, but I'll DM you your token and instructions once more")
		
		# Check if the user is in the group.
		await ctx.send("Checking to see if you're in the TMTM steam group...")
		group_membership = await steam_check_group_membership(steam_id64)
		if type(group_membership) is int:
			return await steam_throw_error(self,ctx,group_membership)
		elif group_membership is True:
			await ctx.send("Check successful. I'll DM what you need to do from here.")
		elif group_membership is False:
			await ctx.send("Sorry, it doesn't look like you're a part of this arma group. "
						"You're free to apply at https://tmtm.gg/contact.php")
			return 0
		
		# Generate a random token
		user_token = "".join(random.sample(string.ascii_letters, 10))
		# Insert the user's data into the database
		self.db.upsert({
			"discord_id": usr.id,
			"discord_name": usr.name,
			"steam_id": steam_id64,
			"token": user_token,
			"verified": False
		}, Query().discord_id == usr.id)
		instructions = "Put this token into the 'real name' section of your steam profile. Come back " \
						"check in section of the discord and type in " + ctx.prefix + "checkin \n" \
						"```" + user_token + "```"
		try:
			await ctx.author.send(instructions)
		except:
			await ctx.send("I was unable to DM you your instructions. I have sent them here instead.")
			await ctx.send(instructions)
	
	@commands.command(name="checkin")
	@commands.bot_has_permissions(manage_roles=True)
	@blueonblue.checks.in_any_channel(config["SERVER"]["CHANNELS"]["CHECK_IN"])
	async def check_in(self, ctx):
		"""Confirms that a user is a part of the steam group."""
		
		usr = ctx.author
		member_role = self.bot._guild.get_role(config["SERVER"]["ROLES"]["MEMBER"])
		
		# Check if the user already has the member role
		if member_role in ctx.author.roles:
			await ctx.send("%s, you already have the member role." % (ctx.author.mention))
			return 0
		
		# If the user is not verified, check their steam profile
		if self.db.contains((Query().discord_id == usr.id) & ~(Query().verified == True)):
			await ctx.send("Checking your profile now.")
			verified = await steam_check_token(self,usr)
			if type(verified) is int:
				return await steam_throw_error(self,ctx,verified)
			elif verified is None:
				await ctx.send("I was unable to check for the token on your Steam profile. "
							"Please verify that your Steam profile visibility is set to 'Public'.")
				return 0
			elif verified is False:
				await ctx.send("Sorry, the token does not match what is on your profile. "
							"You can use %sverify with your Steam profile URL is you need "
							"a new token" % (ctx.prefix))
			elif verified is True:
				#Update the database
				self.db.upsert({"discord_id": usr.id, "verified": True}, Query().discord_id == usr.id)
				steam_id64 = self.db.get(Query().discord_id == usr.id)["steam_id"]
				group_membership = await steam_check_group_membership(steam_id64)
				if type(group_membership) is int:
					return await steam_throw_error(self,ctx,group_membership)
				elif group_membership is False:
					await ctx.send("Your token matches, but it doesn't seem like you're a part of "
								"this Arma group. You're free to apply at https://tmtm.gg/contact.php")
					return 0
				elif group_membership is True:
					if await assign_roles(self,ctx,usr):
						await ctx.send("%s, verification complete. Welcome to TMTM." % (ctx.author.mention))
					else:
						await ctx.send("%s, your verification is complete, but I encountered an error "
									"when assigning your roles. Please ping an admin for a role.")
					return 0				
			
		# If the user is verified, check if they're in the steam group
		elif self.db.contains((Query().discord_id == usr.id) & (Query().verified == True)):
			await ctx.send("Checking your profile now.")
			steam_id64 = self.db.get(Query().discord_id == usr.id)["steam_id"]
			group_membership = await steam_check_group_membership(steam_id64)
			if type(group_membership) is int:
				return await steam_throw_error(self,ctx,group_membership)
			elif group_membership is False:
				await ctx.send("The Steam account that I have on file does not appear to be "
							"a part of this Arma group. You're free to apply at https://tmtm.gg/contact.php \n"
							"If you need to use a different Steam account, please use "
							"%sverify <link-to-your-steam-profile> to get a new user token." % (ctx.prefix))
				return 0
			elif group_membership is True:
				if await assign_roles(self,ctx,usr):
					await ctx.send("%s, verification complete. Welcome to TMTM." % (ctx.author.mention))
				else:
					await ctx.send("%s, your verification is complete, but I encountered an error "
								"when assigning your roles. Please ping an admin for a role.")
				return 0
		
		# If the user is not in the database, prompt them to verify first
		else:
			await ctx.send("It doesn't seem like I have sent you to token yet. Please type in "
						"%sverify for a token." % (ctx.prefix))
			return 0
	
	
	@commands.Cog.listener()
	async def on_member_join(self,member):
		if member.guild.id == config["SERVER"]["ID"]:
			channel = self.bot.get_channel(config["SERVER"]["CHANNELS"]["CHECK_IN"])
			prefix = config["BOT"]["CMD_PREFIXES"][0]
			if self.db.contains((Query().discord_id == member.id) & (Query().verified == True)):
				await channel.send("Welcome to TMTM " + member.mention + ". It looks like you "
						"have been here before. Use %scheckin to gain access to the server, or "
						"%sverify if you need to use a different Steam account." % (prefix,prefix))
			else:	
				await channel.send("Welcome to TMTM " + member.mention + ". To gain access "
						"to the server, please type %sverify <link-to-your-steam-profile>. "
						"If you are not in TMTM at the moment, "
						"please go through the regular application process to join." % (prefix))
	
def setup(bot):
	bot.add_cog(Verify(bot))