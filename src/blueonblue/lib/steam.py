import logging

import blueonblue

_log = logging.getLogger(__name__)


# Exceptions
class MissingSteamID(Exception):
	"""Exception used when a Steam ID could not be found"""

	def __init__(self, status: int | None = None):
		self.status = status


class InvalidSteamURL(Exception):
	"""Exception used when an invalid Steam profile URL format was provided"""

	pass


class NoSteamUserFound(Exception):
	"""Exception raised when no users are returned by a Steam API search"""

	pass


# Functions
async def getID64(bot: blueonblue.BlueOnBlueBot, url: str) -> str:
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
		steamID_str = url.split("profiles/", 1)[-1].replace("/", "")
		if steamID_str.isnumeric():  # SteamID64s are integers in string form
			return steamID_str  # Return the steamID as a string
		else:
			_log.debug(f"Could not find steamID from url: {url}")
			raise MissingSteamID()
	elif "/id/" in url:
		# With an "ID" url, we're going to have to use the steam API to get the steamID
		# Start by splitting the URL to grab the vanity part
		vanity = url.split("id/", 1)[-1]
		# Vanity URLs will *sometimes* have a forward slash at the end. Trim that if we find it.
		if vanity.endswith("/"):
			vanity = vanity[:-1]

		# Make our request to the steam API
		async with bot.httpSession.get(
			"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/",
			params={"key": bot.config.steam_api_token, "vanityurl": vanity},
		) as response:
			responseData = (await response.json())["response"]
			if ("steamid" in responseData) and (responseData["steamid"].isnumeric()):
				return responseData["steamid"]
			else:
				_log.debug(
					f"Error {response.status} retrieving steamID from vanity url: {vanity}"
				)
				raise MissingSteamID(response.status)
	else:
		_log.debug(f"Could not retrieve Steam ID from invalid profile URL: {url}")
		raise InvalidSteamURL()


async def in_guild_group(
	bot: blueonblue.BlueOnBlueBot, guildID: int, steamID: str
) -> bool:
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
		params={"key": bot.config.steam_api_token, "steamid": steamID},
	) as response:
		# Get our response data
		responseData = (await response.json())["response"]
		# Get our group list in dict form
		groupList = []
		if "groups" in responseData:
			for g in responseData["groups"]:
				groupList.append(int(g["gid"]))  # Append the group ID to the group list
		# Get the steam group from the config
		steamGroupID = await bot.serverConfig.steam_group_id.get(guildID)
		if steamGroupID in groupList:
			return True
		else:
			return False


async def check_guild_token(
	bot: blueonblue.BlueOnBlueBot, steamID: str, token: str
) -> bool:
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
		params={"key": bot.config.steam_api_token, "steamids": steamID},
	) as response:
		# Get our response data
		playerData = (await response.json())["response"]["players"]
		# If we have no entries, return None
		if len(playerData) == 0:
			_log.debug(f"Could not find Steam user: {id}")
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


async def get_display_name(bot: blueonblue.BlueOnBlueBot, steamID: str) -> str:
	"""|coro|

	Retrieves the display name of a Steam profile using their SteamID64

	Parameters
	----------
	bot : blueonblue.BlueOnBlueBot
		The bot object
	steamID : str
		Steam64ID of the user

	Returns
	-------
	str
		Display name of the user

	Raises
	------
	NoSteamUserFound
		Could not locate the user by SteamID
	"""
	# Make our web request
	async with bot.httpSession.get(
		"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
		params={"key": bot.config.steam_api_token, "steamids": steamID},
	) as response:
		# Get our response data
		playerData = (await response.json())["response"]["players"]
		# If we have no entries, raise an error
		if len(playerData) == 0:
			_log.debug(f"Could not find Steam user: {steamID}")
			raise NoSteamUserFound()
		# We have a user, return their real name
		return playerData[0]["personaname"]
