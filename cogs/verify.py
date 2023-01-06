import discord
from discord import app_commands
from discord.ext import commands

import asqlite
import random
import string

import blueonblue

import logging
log = logging.getLogger("blueonblue")


async def steam_getID64(bot: blueonblue.BlueOnBlueBot, url: str) -> str | int | None:
	"""|coro|

	Converts a Steam profile URL to a Steam64ID

	Parameters
	----------
	url : str
		The full URL of the steam profile to search.

	Returns
	-------
	str | int | None
		The Steam64ID if found, or an HTTP error code if received.
	"""

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
		async with bot.httpSession.get("https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/", params = {
			"key": bot.config.steam_api_token,
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


async def steam_check_group_membership(bot: blueonblue.BlueOnBlueBot, guildID: int, steamID64: int) -> bool | int:
	"""|coro|

	Uses a SteamID64 to check if a user is in a guild's specified Steam group.

	Checks using the short GroupID that can be found on the group edit page.

	Parameters
	----------
	bot : blueonblue.BlueOnBlueBot
		The bot object.
	guildID : int
		The ID of the Discord Guild for which we get the steam group.
	steamID64 : int
		SteamID64 of the user.

	Returns
	-------
	bool | int
		True/False if part of the group or not.
		Integer if an HTTP error was encountered.
	"""
	async with bot.httpSession.get(
		"https://api.steampowered.com/ISteamUser/GetUserGroupList/v1/",
		params = {
			"key": bot.config.steam_api_token,
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
			steamGroupID = bot.serverConfig.getint(str(guildID), "steam_group_id", fallback = 0)
			if steamGroupID in groupList:
				return True
			else:
				return False
		else:
			return response.status


async def steam_check_token(bot: blueonblue.BlueOnBlueBot, userID: int) -> bool | None | int:
	"""|coro|

	Uses a saved SteamID64 to check if a user has placed the verification token in their profile.

	Parameters
	----------
	bot : blueonblue.BlueOnBlueBot
		The bot object.
	userID : int
		Discord ID of the user.

	Returns
	-------
	bool | None | int
		Boolean if the token is in the Steam real name.
		None if we could not retrieve the real name.
		Int if we encountered an HTTP error.
	"""
	# Start by querying in the database to see if we have a token we can use.
	async with bot.db as db:
		async with db.cursor() as cursor:
			await cursor.execute("SELECT steam64_id, token FROM verify WHERE discord_id = :userID", {"userID": userID})
			tokenData = await cursor.fetchone() # We should only ever have one value for a given discord ID

	# Check to see if we retrieved a token
	if tokenData["token"] is None:
		return None # Return none if we don't have a token

	# Make our web request
	async with bot.httpSession.get(
		"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
		params = {
			"key": bot.config.steam_api_token,
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


async def assign_roles(bot: blueonblue.BlueOnBlueBot, guild: discord.Guild, user: discord.Member) -> bool:
	"""|coro|

	Assigns Discord roles to a member upon being verified.

	Parameters
	----------
	bot : blueonblue.BlueOnBlueBot
		The bot object.
	guild : discord.Guild
		Guild to assign roles in.
	user : discord.Member
		Member to assign roles to.

	Returns
	-------
	bool
		True/False if the roles were assigned successfully.
	"""
	# Start by querying the database to see if the user has any roles stored.
	async with bot.db as db:
		async with db.cursor() as cursor:
			await cursor.execute("SELECT server_id, user_id, role_id FROM user_roles WHERE server_id = :server_id AND user_id = :user_id", {"server_id": guild.id, "user_id": user.id})
			roleData = await cursor.fetchall()

	# This needs a check if the user is jailed.
	userRoles: list[discord.Role] = []
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
		# No user roles stored
		memberRole = guild.get_role(bot.serverConfig.getint(str(guild.id), "role_member"))
		try:
			await user.add_roles(memberRole, reason="User verified")
			return True
		except:
			return False


def steam_return_error_text(status_code: int) -> str:
	"""Returns error text from an HTTP error code from Steam API requests.

	Provided errors are also logged to the bot log.

	Parameters
	----------
	status_code : int
		HTTP error status code.

	Returns
	-------
	str
		Error text to be sent to the user.
	"""
	if status_code == 400: # Bad request
		return "That doesn't seem to be a valid steam profile. Please provide a link similar to this: <https://steamcommunity.com/profiles/76561198329777700>"
	elif status_code == 403: # Unauthorized
		return "I ran into an issue getting data from Steam. Please verify that your Steam profile visibility is set to 'Public'. " \
			"If it is, please ping an admin for a role. Error `403`"
	elif status_code == 429: # Rate limited
		log.warning("Received code 429 from Steam.")
		return "I appear to be rate-limited by Steam. Please ping an admin for a role. Error `429`"
	elif status_code == 500: # Server error
		log.warning("Received code 500 from Steam.")
		return "Steam appears to be having some issues. Please ping an admin for a role. Error `500`"
	elif status_code == 503:
		log.warning("Received code 503 from Steam.")
		return "Steam appears to be having some issues. Please ping an admin for a role. Error `503`"
	else:
		log.warning(f"Received code {status_code} from Steam.")
		return f"Something has gone wrong. Please ping an admin for a role. Error `{status_code}`"


@app_commands.guild_only()
class Verify(commands.GroupCog, group_name = "verify"):
	"""Verify that users are part of a steam group."""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	@app_commands.command(name = "steam")
	@app_commands.guild_only()
	@app_commands.checks.bot_has_permissions(manage_roles=True)
	@blueonblue.checks.in_guild()
	async def verify_steam(self, interaction: discord.Interaction, steam_url: str):
		"""Verifies that a Steam account in in the Steam group.

		Parameters
		----------
		interaction : discord.Interaction
			Discord interaction
		steam_url : str
			Your Steam profile URL
		"""
		# Immediately defer the interaction, since we need to make web requests.
		await interaction.response.defer()

		# Get the user's SteamID64
		steamID = await steam_getID64(self.bot, steam_url)
		if steamID is None:
			await interaction.followup.send("Invalid URL sent, please give me a valid URL.")
			return
		elif type(steamID) is int: # If we received a status code, handle the error.
			await interaction.followup.send(steam_return_error_text(steamID))

		# Store an integer version of the SteamID
		steamID64 = int(steamID)

		# Check if the user is in the steam group
		groupMembership = await steam_check_group_membership(self.bot, interaction.guild.id, steamID64)
		if type(groupMembership) is int:
			# HTTP error
			await interaction.followup.send(steam_return_error_text(groupMembership))
			return
		elif groupMembership:
			# User in group
			# Check if the user already exists in our DB
			# Start our DB block.
			async with self.bot.db.connect() as db:
				async with db.cursor() as cursor:
					# Start by checking if the user is already in the DB
					await cursor.execute("SELECT discord_id FROM verify WHERE discord_id = :id AND verified = 1", {"id": interaction.user.id})
					userInDB = await cursor.fetchone()

					if userInDB is not None:
						messageText = "It looks like you're already in our systems, but I'll send you your token and instructions once more.\n"
					else:
						messageText = ""

					# Append our message to the text, then send it.
					messageText += "Check successful. I'll DM what you need to do from here."

					await interaction.followup.send(messageText)

					# Generate a random token
					userToken = "".join(random.sample(string.ascii_letters, 10))
					# Insert the user's data into the database
					await cursor.execute("INSERT OR REPLACE INTO verify (discord_id, steam64_id, token) VALUES\
						(:userID, :steamID, :token)", {"userID": interaction.user.id, "steamID": steamID64, "token": userToken})
					await db.commit() # Commit changes
					# Prepare the instructions
					instructions = "Put this token into the 'real name' section of your steam profile. " \
						f"Come back to the check in section of the discord and type in `/verify checkin`.\n" \
						f"```{userToken}```"

					try: # Try to send the user a DM
						await interaction.user.send(instructions)
					except: # If that fails, send the instructions to the check in channel
						await interaction.followup.send("I was unable to DM you your instructions. I have sent them here instead.\n" + instructions)

		else:
			# User not in group
			applyUrl = self.bot.serverConfig.get(str(interaction.guild.id), "group_apply_url", fallback = None)
			msg = "Sorry, it doesn't look like you're a part of this group."
			if applyUrl is not None:
				msg += f" You're free to apply at {applyUrl}."
			await interaction.followup.send(msg)


	@app_commands.command(name = "checkin")
	@app_commands.guild_only()
	@app_commands.checks.bot_has_permissions(manage_roles=True)
	@blueonblue.checks.in_guild()
	async def check_in(self, interaction: discord.Interaction):
		"""Confirms that a user is a part of the Steam group"""
		# Get the member role
		memberRoleID = self.bot.serverConfig.get(str(interaction.guild.id), "role_member")
		memberRole = interaction.guild.get_role(memberRoleID)

		# Check if the user already has the member role
		if memberRole in interaction.user.roles:
			await interaction.response.send_message(f"{interaction.user.mention}, you already have the member role.")
			return

		# Begin our DB block
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				# Get the user data from the DB
				await cursor.execute("SELECT steam64_id, token, verified FROM verify WHERE discord_id = :id", {"id": interaction.user.id})
				userData = await cursor.fetchone()

				if userData is None:
					# User not found in database
					await interaction.response.send_message("You need to use the `/verify steam` command before you can check in!")

				elif userData["verified"]:
					# User is already verified. We only need to check the steam group.
					# Defer the response since we need to make web requests.
					await interaction.response.defer()
					steamID64: int = userData["steam64_id"]
					# Check group membership
					groupMembership = await steam_check_group_membership(self.bot, interaction.guild.id, steamID64)
					if type(groupMembership) is int:
						# HTTP error
						await interaction.followup.send(steam_return_error_text(groupMembership))
						return

					elif groupMembership:
						# User in group
						if await assign_roles(self.bot, interaction.guild, interaction.user):
							await interaction.followup.send(f"Verification complete, welcome to {interaction.guild.name}.")
						else:
							await interaction.followup.send(f"{interaction.user.mention}, your verification is complete, but I encountered an error "
								"when assigning your roles. Please ping an admin for your roles.")

					else:
						# User not in group
						applyUrl = self.bot.serverConfig.get(str(interaction.guild.id), "group_apply_url", fallback = None)
						if applyUrl is not None:
							msg = "The Steam account that I have on file does not appear to be a part of this group. " \
								f"You're free to apply at {applyUrl} \n" \
								"If you need to use a different Steam account, please use " \
								f"`/verify steam <link-to-your-steam-profile> to get a new user token."
						else:
							msg = "The Steam account that I have on file does not appear to be a part of this group. " \
								"If you need to use a different Steam account, please use " \
								f"`/verify steam <link-to-your-steam-profile> to get a new user token."
						await interaction.followup.send(msg)

				else:
					# User not verified
					# Defer the response since we need to make web requests.
					await interaction.response.defer()

					verified = await steam_check_token(self.bot, interaction.user.id) # Check if the stored token matches the steam profile
					# Handle the verified check
					if type(verified) is int:
						# Status code returned from an HTTP error
						await interaction.followup.send(steam_return_error_text(verified))
					elif verified is None:
						# Did not find any results for that Steam ID
						await interaction.followup.send("I was unable to check for the token on your Steam profile. "
							"Please verify that your Steam profile visibility is set to 'Public'.")
					elif verified:
						# Token confirmed
						# Updated our "verified" flag to be true
						await cursor.execute("UPDATE verify SET verified = 1 WHERE discord_id = :userID", {"userID": interaction.user.id})
						await db.commit()

						# User is already verified. We only need to check the steam group.
						steamID64: int = userData["steam64_id"]
						# Check group membership
						groupMembership = await steam_check_group_membership(self.bot, interaction.guild.id, steamID64)
						if type(groupMembership) is int:
							# HTTP error
							await interaction.followup.send(steam_return_error_text(groupMembership))
							return
						elif groupMembership:
							# User in group
							if await assign_roles(self.bot, interaction.guild, interaction.user):
								await interaction.followup.send(f"Verification complete, welcome to {interaction.guild.name}.")
							else:
								await interaction.followup.send(f"{interaction.user.mention}, your verification is complete, but I encountered an error "
									"when assigning your roles. Please ping an admin for your roles.")

						else:
							# User not in group
							applyUrl = self.bot.serverConfig.get(str(interaction.guild.id), "group_apply_url", fallback = None)
							msg = "Your token matches, but it doesn't seem like you're a part of this group."
							if applyUrl is not None:
								msg += f" You're free to apply at {applyUrl}."
							await interaction.followup.send(msg)
					else:
						# Profile found. Token not present.
						await interaction.followup.send("Sorry, the token does not match what is on your Steam profile. "
							f"You can use `/verify steam` with your Steam profile URL if you need a new token.")


	@commands.Cog.listener()
	async def on_member_join(self, member: discord.Member):
		guildSteamGroupID = self.bot.serverConfig.getint(str(member.guild.id),"steam_group_id", fallback = -1)
		checkInChannelID = self.bot.serverConfig.getint(str(member.guild.id),"channel_check_in", fallback = -1)
		channel = self.bot.get_channel(checkInChannelID)
		if (guildSteamGroupID > 0) and (channel is not None):
			# Only continue if we have a valid steam group ID and check in channel
			# Start our DB block
			async with self.bot.db.connect() as db:
				async with db.cursor() as cursor:
					# Get the user data from the DB
					await cursor.execute("SELECT discord_id FROM verify WHERE discord_id = :id AND verified = 1", {"id": member.id})
					userData = await cursor.fetchone() # This will only return users that are verified
					# Check if we have any data in the DB
					if userData is not None:
						# User is already verified
						await channel.send(f"Welcome to {member.guild.name} {member.mention}. It looks like you have been here before. "
							f"Use `/verify checkin` to gain access to the server, or `/verify steam` if you need to use a "
							"different steam account.")
					else:
						# User not already verified
						await channel.send(f"Welcome to {member.guild.name} {member.mention}. To gain access to this server, "
							f"please type `/verify steam <link-to-your-steam-profile>`. If you are not in {member.guild.name} "
							"at the moment, please go through the regular application process to join.")

async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Verify(bot))
