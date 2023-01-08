import discord
from discord import app_commands
from discord.ext import commands

import aiohttp
import random
import string

import blueonblue

import logging
_log = logging.getLogger(__name__)

# Exceptions
class MissingSteamID(BaseException):
	"""Exception used when a Steam ID could not be found"""
	def __init__(self, status: int | None = None):
		self.status = status

class InvalidSteamURL(BaseException):
	"""Exception used when an invalid Steam profile URL format was provided"""
	pass

class NoSteamUserFound(BaseException):
	"""Exception raised when no users are returned by a Steam API search"""
	pass

# Discord views
class VerifySteamView(blueonblue.views.AuthorResponseViewBase):
	message: discord.WebhookMessage
	"""View for steam verification"""
	def __init__(self, bot: blueonblue.BlueOnBlueBot, author: discord.User|discord.Member, steamID: str, *args, timeout: float=1800.0, **kwargs):
		self.bot = bot
		self.steamID = steamID
		super().__init__(author, *args, timeout=timeout, **kwargs)
		self.add_item(VerifyButton())


class CheckInView(blueonblue.views.AuthorResponseViewBase):
	message: discord.Message
	"""View for steam verification"""
	def __init__(self, bot: blueonblue.BlueOnBlueBot, author: discord.User|discord.Member, steamID: str, *args, timeout: float=1800.0, **kwargs):
		self.bot = bot
		self.steamID = steamID
		super().__init__(author, *args, timeout=timeout, **kwargs)
		self.add_item(CheckInButton())


# Discord buttons
class VerifyButton(discord.ui.Button):
	"""Button to verify a user"""
	view: VerifySteamView
	def __init__(self, *args, label: str = "Verify", style: discord.ButtonStyle = discord.ButtonStyle.primary, **kwargs):
		super().__init__(*args, label = label, style = style, **kwargs)

	async def callback(self, interaction: discord.Interaction):
		# Immediately defer the interaction response so that we can make web requests
		await interaction.response.defer(ephemeral=True)
		# Check the steam profile to see if it has the token set
		try:
			verified = await steam_check_token(self.view.bot, self.view.steamID, str(interaction.user.id))
		except aiohttp.ClientResponseError as error:
			_log.warning(f"Received response code [{error.status}] from the Steam API when checking steam URL")
			await interaction.followup.send(steam_return_error_text(error.status))
			return
		except:
			_log.exception("Error checking Steam profile")
			await interaction.followup.send("Error encountered checking Steam profile. Please contact an administrator for assistance.")
			return

		if not verified:
			await interaction.followup.send(
				"I was unable to validate the token in your Steam profile. Please ensure that your Steam profile visibility is set to **public**, " \
				"and that you have the following token in your Steam profile's \"real name\" field:\n" \
				f"```{interaction.user.id}```",
				ephemeral=True,
			)
			return

		# User is now confirmed to be verified, set the data in the DB
		async with self.view.bot.db.connect() as db:
			async with db.cursor() as cursor:
				await cursor.execute("INSERT OR REPLACE INTO verify (discord_id, steam64_id) VALUES\
					(:userID, :steamID)", {"userID": interaction.user.id, "steamID": int(self.view.steamID)})
				await db.commit() # Commit changes

		# Disable the buttons in the view, and clean up the view since we won't need it anymore
		await self.view.terminate()

		# If we're in a guild, check if the user is in the associated steam group
		if interaction.guild is not None:
			# If we're in a guild, the user *must* be a member
			assert isinstance(interaction.user, discord.Member)
			try:
				groupMembership = await steam_check_group_membership(self.view.bot, interaction.guild.id, self.view.steamID)
				if not groupMembership:
					# User not in group
					applyUrl = self.view.bot.serverConfig.get(str(interaction.guild.id), "group_apply_url", fallback = None)
					msg = "Your account has been verified, but it doesn't look like you're a part of this group."
					if applyUrl is not None:
						msg += f" You're free to apply at {applyUrl}."
					await interaction.followup.send(msg, ephemeral=True)
					return
			except aiohttp.ClientResponseError as error:
				_log.warning(f"Received response code [{error.status}] from the Steam API when checking steam URL")
				await interaction.followup.send(steam_return_error_text(error.status))
				return
			except:
				_log.exception("Error checking Steam group membership")
				await interaction.followup.send("Error encountered checking Steam group membership. Please contact an administrator for assistance.")
				return

			# User is in the steam group, only proceed if they don't have the member role already
			memberRole = interaction.guild.get_role(self.view.bot.serverConfig.getint(str(interaction.guild.id), "role_member"))
			if (memberRole in interaction.user.roles) or memberRole is None:
				await interaction.followup.send("Verification complete, your Steam ID has been successfully linked", ephemeral=True)
			else:
				if await assign_roles(self.view.bot, interaction.guild, interaction.user):
					await interaction.user.send(f"Verification complete, welcome to {interaction.guild.name}.")

				else:
					await interaction.followup.send(f"{interaction.user.mention} your verification is complete, but I encountered an error "
						"when assigning your roles. Please ping an admin for your roles."
					)
				# Send a verification message to the check in channel
				checkInChannel = self.view.bot.get_channel(self.view.bot.serverConfig.getint(str(interaction.guild.id),"channel_check_in", fallback = -1))
				if isinstance(checkInChannel, discord.TextChannel):
					await checkInChannel.send(f"Member {interaction.user.mention} verified with steam account: http://steamcommunity.com/profiles/{self.view.steamID}")

		else:
			# Not in a guild, don't check group membership
			# Let the user know that they're verified now
			await interaction.followup.send("Verification complete, your Steam ID has been successfully linked")


class CheckInButton(discord.ui.Button):
	"""Button to check in an already verified user"""
	view: CheckInView
	def __init__(self, *args, label: str = "Check In", style: discord.ButtonStyle = discord.ButtonStyle.primary, **kwargs):
		super().__init__(*args, label = label, style = style, **kwargs)

	async def callback(self, interaction: discord.Interaction):
		# This should never be displayed outside of a guild context
		assert interaction.guild is not None
		assert isinstance(interaction.user, discord.Member)

		# Immediately defer the interaction response so that we can make web requests
		await interaction.response.defer()

		try:
			groupMembership = await steam_check_group_membership(self.view.bot, interaction.guild.id, self.view.steamID)
			if not groupMembership:
				# User not in group
				applyUrl = self.view.bot.serverConfig.get(str(interaction.guild.id), "group_apply_url", fallback = None)
				msg = "Your account has been verified, but it doesn't look like you're a part of this group."
				if applyUrl is not None:
					msg += f" You're free to apply at {applyUrl}."
				await interaction.followup.send(msg, ephemeral=True)
				return
		except aiohttp.ClientResponseError as error:
			_log.warning(f"Received response code [{error.status}] from the Steam API when checking steam URL")
			await interaction.followup.send(steam_return_error_text(error.status))
			return
		except:
			_log.exception("Error checking Steam group membership")
			await interaction.followup.send("Error encountered checking Steam group membership. Please contact an administrator for assistance.")
			return

		# User is in the steam group, only proceed if they don't have the member role already
		memberRole = interaction.guild.get_role(self.view.bot.serverConfig.getint(str(interaction.guild.id), "role_member"))
		if (memberRole in interaction.user.roles) or memberRole is None:
			await interaction.followup.send("Verification complete.", ephemeral=True)
		else:
			if await assign_roles(self.view.bot, interaction.guild, interaction.user):
				await interaction.user.send(f"Verification complete, welcome to {interaction.guild.name}.")

			else:
				await interaction.followup.send(f"{interaction.user.mention} your verification is complete, but I encountered an error "
					"when assigning your roles. Please ping an admin for your roles."
				)
			# Send a verification message to the check in channel
			checkInChannel = self.view.bot.get_channel(self.view.bot.serverConfig.getint(str(interaction.guild.id),"channel_check_in", fallback = -1))
			if isinstance(checkInChannel, discord.TextChannel):
				await checkInChannel.send(f"Member {interaction.user.mention} verified with steam account: http://steamcommunity.com/profiles/{self.view.steamID}")


async def steam_getID64(bot: blueonblue.BlueOnBlueBot, url: str) -> str:
	"""|coro|

	Converts a Steam profile URL to a Steam64ID

	Parameters
	----------
	url : str
		The full URL of the steam profile to search.

	Returns
	-------
	str
		The Steam64ID

	Raises
	------
	MissingSteamID
		Raised if the SteamID could not be found without other errors.
	InvalidSteamURL
		Invalid format for Steam Profile URL provided
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
			raise MissingSteamID()
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
			responseData = (await response.json())["response"]
			if ("steamid" in responseData) and (responseData["steamid"].isnumeric()):
				return responseData["steamid"]
			else:
				raise MissingSteamID(response.status)
	else:
		raise InvalidSteamURL()


async def steam_check_group_membership(bot: blueonblue.BlueOnBlueBot, guildID: int, steamID: str) -> bool:
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
	bool
		If the steam account was part of the steam group
	"""
	async with bot.httpSession.get(
		"https://api.steampowered.com/ISteamUser/GetUserGroupList/v1/",
		params = {
			"key": bot.config.steam_api_token,
			"steamid": steamID
		}
	) as response:
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


async def steam_check_token(bot: blueonblue.BlueOnBlueBot, steamID: str, token: str) -> bool:
	"""|coro|

	Uses a saved SteamID64 to check if a user has placed the verification token in their profile.

	Parameters
	----------
	bot : blueonblue.BlueOnBlueBot
		The bot object.
	userID : int
		Discord ID of the user.
	token : str
		Verification token to check

	Returns
	-------
	bool
		If the token is in the Steam Profile real name field
	"""
	# Make our web request
	async with bot.httpSession.get(
		"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
		params = {
			"key": bot.config.steam_api_token,
			"steamids": steamID
		}
	) as response:
		# Get our response data
		playerData = (await response.json())["response"]["players"]
		# If we have no entries, return None
		if len(playerData) == 0:
			raise NoSteamUserFound()
		# Check if we have a "realname" value in the playerdata
		if "realname" in playerData[0]:
			# Real name is in playerdata
			if token in playerData[0]["realname"]:
				# Stored token in real name
				return True
			else:
				# Stored token not in real name
				return False
		else:
			# With no realname, we have no match
			return False


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
	async with bot.db.connect() as db:
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
			assert memberRole is not None
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
		_log.warning("Received code 429 from Steam.")
		return "I appear to be rate-limited by Steam. Please ping an admin for a role. Error `429`"
	elif status_code == 500: # Server error
		_log.warning("Received code 500 from Steam.")
		return "Steam appears to be having some issues. Please ping an admin for a role. Error `500`"
	elif status_code == 503:
		_log.warning("Received code 503 from Steam.")
		return "Steam appears to be having some issues. Please ping an admin for a role. Error `503`"
	else:
		_log.warning(f"Received code {status_code} from Steam.")
		return f"Something has gone wrong. Please ping an admin for a role. Error `{status_code}`"


@app_commands.guild_only()
class Verify(commands.GroupCog, group_name = "verify"):
	"""Verify that users are part of a steam group."""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	@app_commands.command(name = "steam")
	async def verify_steam(self, interaction: discord.Interaction, steam_url: str):
		"""Establishes a link between a Discord account and a Steam account

		Parameters
		----------
		interaction : discord.Interaction
			Discord interaction
		steam_url : str
			Your Steam profile URL
		"""
		# Immediately defer the interaction, since we need to make web requests.
		await interaction.response.defer(ephemeral=True)

		# Get the user's SteamID64
		try:
			steamID = await steam_getID64(self.bot, steam_url)
		except aiohttp.ClientResponseError as error:
			if error.status not in [400, 403]:
				_log.warning(f"Received response code [{error.status}] from the Steam API when checking steam URL")
			await interaction.followup.send(steam_return_error_text(error.status))
			return
		except:
			_log.exception("Error getting Steam64ID")
			await interaction.followup.send("Error encountered checking steam ID. Please contact an administrator for assistance.")
			return

		# If the command is used in a guild, check that the user is in the provided steam group
		if interaction.guild is not None:
			try:
				groupMembership = await steam_check_group_membership(self.bot, interaction.guild.id, steamID)
				if not groupMembership:
					# User not in group
					applyUrl = self.bot.serverConfig.get(str(interaction.guild.id), "group_apply_url", fallback = None)
					msg = "Sorry, it doesn't look like you're a part of this group."
					if applyUrl is not None:
						msg += f" You're free to apply at {applyUrl}."
					await interaction.followup.send(msg)
					return
			except aiohttp.ClientResponseError as error:
				_log.warning(f"Received response code [{error.status}] from the Steam API when checking steam URL")
				await interaction.followup.send(steam_return_error_text(error.status))
				return
			except:
				_log.exception("Error checking Steam group membership")
				await interaction.followup.send("Error encountered checking Steam group membership. Please contact an administrator for assistance.")
				return

		view = VerifySteamView(self.bot, interaction.user, steamID)

		view.message = await interaction.followup.send(
			"To complete your verification, ensure that your steam profile visibility is set to **public**, " \
			"then put the following token into the \"real name\" section of your steam profile.\n" \
			f"```{interaction.user.id}```" \
			"Once you have done so, click the button below to verify your account.",
			view = view,
			wait = True
		)


	@commands.Cog.listener()
	async def on_member_join(self, member: discord.Member):
		guildSteamGroupID = self.bot.serverConfig.getint(str(member.guild.id),"steam_group_id", fallback = -1)
		checkInChannelID = self.bot.serverConfig.getint(str(member.guild.id),"channel_check_in", fallback = -1)
		channel = self.bot.get_channel(checkInChannelID)
		assert isinstance(channel, discord.TextChannel)
		if (guildSteamGroupID > 0) and (channel is not None):
			# Only continue if we have a valid steam group ID and check in channel
			# Start our DB block
			async with self.bot.db.connect() as db:
				async with db.cursor() as cursor:
					# Get the user data from the DB
					await cursor.execute("SELECT steam64_id FROM verify WHERE discord_id = :id AND steam64_id NOT NULL", {"id": member.id})
					userData = await cursor.fetchone() # This will only return users that are verified
					# Check if we have any data in the DB
					if userData is not None:
						# User is already verified
						view = CheckInView(self.bot, member, str(userData["steam64_id"]))
						view.message = await channel.send(f"Welcome to {member.guild.name} {member.mention}. It looks like you have been here before. "
							f"Use the button below to gain access to the server, or `/verify steam` if you need to use a "
							"different steam account.",
							view = view)

					else:
						# User not already verified
						await channel.send(f"Welcome to {member.guild.name} {member.mention}. To gain access to this server, "
							f"please type `/verify steam <link-to-your-steam-profile>`. If you are not in {member.guild.name} "
							"at the moment, please go through the regular application process to join.")


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Verify(bot))
