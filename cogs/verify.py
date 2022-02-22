import discord
from discord.ext import commands
import slash_util

import asqlite
import random
import string
from typing import List

import blueonblue

import logging
log = logging.getLogger("blueonblue")

async def steam_getid64(self, url:str = "") -> str | int | None:
	"""Converts a Steam profile URL to a Steam64ID
	Returns the SteamID as a string if it could be found.
	Returns an integer if there was an error with the request.
	Returns None if the steamID could not be found."""
	bot: blueonblue.BlueOnBlueBot = self.bot
	# We need to figure out the "profile" part from the main URL
	# Steam profile URLs can be in two formats: /profiles/*** or /id/***
	# We need to handle both of them
	if "/profiles/" in url:
		# Split the string at the "profiles/" entry, and remove everything but the profile part
		steamID_str = url.split("profiles/", 1)[-1].replace("/","")
		if steamID_str.isnumeric(): # SteamID64s are integers in string form
			return steamID_str # Return the steamID as a string
		else:
			return None
	elif "/id/" in url:
		# With an "ID" url, we're going to have to use the steam API to get the steamID
		# Start by splitting the URL to grab the vanity part
		vanity = url.split("id/", 1)[-1]
		# Vanity URLs will *sometimes* have a forward slash at the end. Trim that if we find it.
		if vanity.endswith("/"):
			vanity = vanity[:-1]

		# Make our request to the steam API
		async with bot.http_session.get("https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/", params = {
			"key": bot.config.get("STEAM","api_token", fallback = ""),
			"vanityurl": vanity
		}) as response:
			if response.status == 200: # Request successful
				responseData = (await response.json())["response"]
				if ("steamid" in responseData) and (responseData["steamid"].isnumeric()):
					return responseData["steamid"]
				else:
					return None # No steamID found in the request, or we didn't get a number
			else:
				return response.status # Return an HTTP error code

async def steam_check_group_membership(self, ctx: commands.Context, steamID64: int) -> bool | int:
	"""Uses a SteamID64 to check if the user is in a Steam group.
	Checks using the short groupID that's found on the group edit page.

	Returns True if the user is in the group.
	Returns False if the user is not in the group.
	Returns an integer if an HTTP error was encountered."""
	bot: blueonblue.BlueOnBlueBot = self.bot
	# Web request block
	async with bot.http_session.get(
		"https://api.steampowered.com/ISteamUser/GetUserGroupList/v1/",
		params = {
			"key": bot.config.get("STEAM","api_token", fallback = ""),
			"steamid": steamID64
		}
	) as response:
		if response.status == 200: # Request successful
			# Get our response data
			responseData = (await response.json())["response"]
			# Get our group list in dict form
			groupList = []
			if "groups" in responseData:
				for g in responseData["groups"]:
					groupList.append(int(g["gid"])) # Append the group ID to the group list
			# Get the steam group from the config
			steamGroupID = bot.serverConfig.getint(str(ctx.guild.id), "steam_group_id", fallback = 0)
			if steamGroupID in groupList:
				return True
			else:
				return False
		else:
			return response.status

async def steam_check_token(self, ctx: commands.Context, cursor: asqlite.Cursor) -> bool | None | int:
	"""Uses a saved SteamID to check if a user has placed the verification token in their profile.
	Returns one of the following:
		True - Token is in steam real name
		False - Token is not in steam real name
		None - Unable to retrieve real name from returned data
		Int - HTTP status code from steam API"""

	# Start by getting the stored Steam64 ID of the user
	bot: blueonblue.BlueOnBlueBot = self.bot
	# Get our user token and steamID from the DB
	await cursor.execute("SELECT steam64_id, token FROM verify WHERE discord_id = :userID", {"userID": ctx.author.id})
	tokenData = await cursor.fetchone() # We should only ever have one value for a given discord ID

	# Check if we have a valid token
	if tokenData["token"] is None:
		return None # Return none if we don't have a token

	# Start our web request block
	async with bot.http_session.get(
		"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
		params = {
			"key": bot.config.get("STEAM","api_token", fallback = ""),
			"steamids": tokenData["steam64_id"]
		}
	) as response:
		if response.status == 200: # Request successful
			# Get our response data
			playerData = (await response.json())["response"]["players"]
			# If we have no entries, return None
			if len(playerData) == 0:
				return None
			# Check if we have a "realname" value in the playerdata
			if "realname" in playerData[0]:
				# Real name is in playerdata
				if tokenData["token"] in playerData[0]["realname"]:
					# Stored token in real name
					return True
				else:
					# Stored token not in real name
					return False
			else:
				# With no realname, we have no match
				return False
		else:
			return response.status

async def assign_roles(self, guild: discord.Guild, user: discord.Member, cursor: asqlite.Cursor) -> bool:
	"""Assigns roles to a member once they verify themselves.
	Uses roles from the users database if present, otherwise assigns the member role."""
	bot: blueonblue.BlueOnBlueBot = self.bot
	# Grab a list of user roles from the DB
	await cursor.execute("SELECT server_id, user_id, role_id FROM user_roles WHERE server_id = :server_id AND user_id = :user_id", {"server_id": guild.id, "user_id": user.id})
	roleData = await cursor.fetchall()

	memberRoleID = bot.serverConfig.getint(str(guild.id), "role_member")
	memberRole = guild.get_role(memberRoleID)

	# This needs a check if the user is jailed or dead. That will come later though...
	userRoles: List[discord.Role] = []
	# Get a list of our user roles
	for r in roleData:
		role = guild.get_role(r["role_id"])
		if role is not None: # Verify that the role actually exists
			userRoles.append(role)

	# Check if we have roles stored
	if len(userRoles) > 0:
		# Roles stored in DB
		try:
			await user.add_roles(*userRoles, reason="User verified")
			return True
		except:
			return False
	else:
		# No user roles store
		try:
			await user.add_roles(memberRole, reason="User verified")
			return True
		except:
			return False

async def steam_throw_error(self, ctx: commands.Context, status_code: int) -> None:
	"""Handles errors from HTTP requests to the Steam API, and sends an error message to the discord channel.
	This function is designed to be called immediately before ending the existing command."""
	if status_code == 400: # Bad request
		await ctx.send(f"{ctx.author.mention} That doesn't seem to be a valid steam porofile. Please provide a link similar to this: <https://steamcommunity.com/profiles/76561198329777700>")
	elif status_code == 403: # Unauthorized
		await ctx.send(f"{ctx.author.mention} I ran into an issue getting data froM Steam. Please verify that your Steam profile visibility is set to 'Public'. "
			"If it is, please ping an admin for a role. Error `403`")
	elif status_code == 429: # Rate limited
		await ctx.send("I appear to be rate-limited by Steam. Please ping an admin for a role. Error `429`")
		log.warning("Received code 429 from Steam.")
	elif status_code == 500: # Server error
		await ctx.send("Steam appears to be having some issues. Please ping an admin for a role. Error `500`")
		log.warning("Received code 500 from Steam.")
	elif status_code == 503:
		await ctx.send("Steam appears to be having some issues. Please ping an admin for a role. Error `503`")
		log.warning("Received code 503 from Steam.")
	else:
		await ctx.send(f"Something has gone wrong. Please ping an admin for a role. Error `{status_code}`")
		log.warning(f"Received code {status_code} from Steam.")


class Verify(slash_util.Cog, name = "Verify"):
	"""Verify that users are part of a steam group."""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		self.bot.loop.create_task(self.db_init())

	async def db_init(self):
		"""Initializes the database for the cog.
		Creates the tables if they don't exist."""
		async with self.bot.db_connection.cursor() as cursor:
			# Create the tables if they do not exist
			# This table doesn't need a server ID, since the discord user to steam ID connection is independent of the discord server
			await cursor.execute("CREATE TABLE if NOT EXISTS verify (\
				discord_id INTEGER PRIMARY KEY,\
				steam64_id INTEGER NOT NULL,\
				token TEXT NOT NULL,\
				verified INTEGER NOT NULL DEFAULT 0)")
			await self.bot.db_connection.commit()

	async def slash_command_error(self, ctx, error: Exception) -> None:
		"""Redirect slash command errors to the main bot"""
		return await self.bot.slash_command_error(ctx, error)

	@commands.command()
	@commands.bot_has_permissions(manage_roles=True)
	@blueonblue.checks.in_channel_checkin()
	# This needs to have a check to make sure that the server config has a steam group
	async def verify(self, ctx: commands.Context, *, steam_url: str=""):
		"""Verifies a user as part of the group.

		Requires a full Steam profile URL for authentication."""
		# Get the user's steamID64
		steamID = await steam_getid64(self, steam_url)
		if steamID is None:
			await ctx.send("Invalid URL sent, please give me a valid URL.")
			return
		elif type(steamID) is int: # If we received a status code, handle the error.
			await steam_throw_error(self, ctx, steamID)
			return

		# Store an integer version of the steamID
		steamID64 = int(steamID)

		# At this point, we know that our steamID64 is an integer in string form
		# Start our DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Start by checking if the user is already in the DB
			await cursor.execute("SELECT discord_id FROM verify WHERE discord_id = :id AND verified = 1", {"id": ctx.author.id})
			userInDB = await cursor.fetchone()
			if userInDB is not None:
				# User already present in database
				await ctx.send("It looks like you're already in our systems, but I'll DM you your token and instructions once more.")

			# Check if the user is in the steam group
			await ctx.send("Checking to see if you're in the steam group...")
			groupMembership = await steam_check_group_membership(self, ctx, steamID64)
			if type(groupMembership) is int:
				# HTTP error
				await steam_throw_error(self, ctx, groupMembership)
				return
			elif groupMembership:
				# User in group
				await ctx.send("Check successful. I'll DM what you need to do from here.")
			else:
				# User not in group
				applyUrl = self.bot.serverConfig.get(str(ctx.guild.id), "group_apply_url", fallback = None)
				msg = "Sorry, it doesn't look like you're a part of this group."
				if applyUrl is not None:
					msg += f" You're free to apply at {applyUrl}."
				await ctx.send(msg)

			# We should only be at this point if the user is in the steam group
			# Generate a random token
			userToken = "".join(random.sample(string.ascii_letters, 10))
			# Insert the user's data into the database
			await cursor.execute("INSERT OR REPLACE INTO verify (discord_id, steam64_id, token) VALUES\
				(:userID, :steamID, :token)", {"userID": ctx.author.id, "steamID": steamID64, "token": userToken})
			await self.bot.db_connection.commit() # Commit changes
			# Prepare the instructions
			instructions = "Put this token into the 'real name' section of your steam profile. " \
				f"Come back to the check in section of the discord and type in `{ctx.prefix}checkin`.\n" \
				f"```{userToken}```"

			try: # Try to send the user a DM
				await ctx.author.send(instructions)
			except: # If that fails, send the instructions to the check in channel
				await ctx.send("I was unable to DM you your instructions. I have sent them here instead.")
				await ctx.send(instructions)

	@commands.command(name="checkin")
	@commands.bot_has_permissions(manage_roles=True)
	@blueonblue.checks.in_channel_checkin()
	# This needs to have a check to make sure that the server config has a steam group
	async def check_in(self, ctx: commands.Context):
		"""Confirms that a user is a part of the Steam group."""
		# Get the member role
		memberRoleID = self.bot.serverConfig.get(str(ctx.guild.id), "role_member")
		memberRole = ctx.guild.get_role(memberRoleID)

		# Check if the user already has the member role
		if memberRole in ctx.author.roles:
			await ctx.send(f"{ctx.author.mention}, you already have the member role.")
			return

		# Begin our DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Get the user data from the DB
			await cursor.execute("SELECT steam64_id, token, verified FROM verify WHERE discord_id = :id", {"id": ctx.author.id})
			userData = await cursor.fetchone()

			if userData is None:
				# User not found in database
				await ctx.send(f"{ctx.author.mention} You need to use the `{ctx.prefix}verify` command before you can check in!")

			elif userData["verified"]:
				# User is already verified. We only need to check the steam group.
				await ctx.send("Checking your profile now.")
				steamID64: int = userData["steam64_id"]
				# Check group membership
				groupMembership = await steam_check_group_membership(self, ctx, steamID64)
				if type(groupMembership) is int:
					# HTTP error
					await steam_throw_error(self, ctx, groupMembership)
					return
				elif groupMembership:
					# User in group
					if await assign_roles(self, ctx.guild, ctx.author, cursor):
						await ctx.send(f"{ctx.author.mention}, verification complete. Welcome to {ctx.guild.name}.")
					else:
						await ctx.send(f"{ctx.author.mention}, your verification is complete, but I encountered an error "
							"when assigning your roles. Please ping an admin for your roles.")
				else:
					# User not in group
					applyUrl = self.bot.serverConfig.get(str(ctx.guild.id), "group_apply_url", fallback = None)
					if applyUrl is not None:
						msg = "The Steam account that I have on file does not appear to be a part of this group. " \
							f"You're free to apply at {applyUrl} \n" \
							"If you need to use a different Steam account, please use " \
							f"`{ctx.prefix}verify <link-to-your-steam-profile> to get a new user token."
					else:
						msg = "The Steam account that I have on file does not appear to be a part of this group. " \
							"If you need to use a different Steam account, please use " \
							f"`{ctx.prefix}verify <link-to-your-steam-profile> to get a new user token."
					await ctx.send(msg)

			else:
				# User not verified
				await ctx.send("Checking your profile now.")
				verified = await steam_check_token(self, ctx, cursor) # Check if the stored token matches the steam profile
				# Handle the verified check
				if type(verified) is int:
					# Status code returned from an HTTP error
					await steam_throw_error(self, ctx, verified)
				elif verified is None:
					# Did not find any results for that Steam ID
					await ctx.send("I was unable to check for the token on your Steam profile. "
						"Please verify that your Steam profile visibility is set to 'Public'.")
				elif verified:
					# Token confirmed
					# Updated our "verified" flag to be true
					await cursor.execute("UPDATE verify SET verified = 1 WHERE discord_id = :userID", {"userID": ctx.author.id})
					await self.bot.db_connection.commit()

					# User is already verified. We only need to check the steam group.
					steamID64: int = userData["steam64_id"]
					# Check group membership
					groupMembership = await steam_check_group_membership(self, ctx, steamID64)
					if type(groupMembership) is int:
						# HTTP error
						await steam_throw_error(self, ctx, groupMembership)
						return
					elif groupMembership:
						# User in group
						if await assign_roles(self, ctx.guild, ctx.author, cursor):
							await ctx.send(f"{ctx.author.mention}, verification complete. Welcome to {ctx.guild.name}.")
						else:
							await ctx.send(f"{ctx.author.mention}, your verification is complete, but I encountered an error "
								"when assigning your roles. Please ping an admin for your roles.")
					else:
						# User not in group
						applyUrl = self.bot.serverConfig.get(str(ctx.guild.id), "group_apply_url", fallback = None)
						msg = "Your token matches, but it doesn't seem like you're a part of this group."
						if applyUrl is not None:
							msg += f" You're free to apply at {applyUrl}."
						await ctx.send(msg)
				else:
					# Profile found. Token not present.
					await ctx.send("Sorry, the token does not match what is on your Steam profile. "
						f"You can use `{ctx.prefix}verify` with your Steam profile URL if you need a new token.")

	@commands.Cog.listener()
	async def on_member_join(self, member: discord.Member):
		guildSteamGroupID = self.bot.serverConfig.getint(str(member.guild.id),"steam_group_id", fallback = -1)
		checkInChannelID = self.bot.serverConfig.getint(str(member.guild.id),"channel_check_in", fallback = -1)
		channel = self.bot.get_channel(checkInChannelID)
		if (guildSteamGroupID > 0) and (channel is not None):
			# Only continue if we have a valid steam group ID and check in channel
			prefix = self.bot.config.get("CORE", "prefix")
			# Start our DB block
			async with self.bot.db_connection.cursor() as cursor:
				# Get the user data from the DB
				await cursor.execute("SELECT discord_id FROM verify WHERE discord_id = :id AND verified = 1", {"id": member.id})
				userData = await cursor.fetchone() # This will only return users that are verified
				# Check if we have any data in the DB
				if userData is not None:
					# User is already verified
					await channel.send(f"Welcome to {member.guild.name} {member.mention}. It looks like you have been here before. "
						f"Use `{prefix}checkin` to gain access to the server, or `{prefix}verify` if you need to use a "
						"different steam account.")
				else:
					# User not already verified
					await channel.send(f"Welcome to {member.guild.name} {member.mention}. To gain access to this server, "
						f"please type `{prefix}verify <link-to-your-steam-profile>`. If you are not in {member.guild.name} "
						"at the moment, please go through the regular application process to join.")



def setup(bot: blueonblue.BlueOnBlueBot):
	bot.add_cog(Verify(bot))
