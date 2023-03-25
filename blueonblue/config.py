import discord
import tomlkit
from tomlkit import items
import inspect

import logging
_log = logging.getLogger(__name__)

from typing import (
	TYPE_CHECKING
)
if TYPE_CHECKING:
	from blueonblue.bot import BlueOnBlueBot

__all__ = [
	"BotConfig",
	"ServerConfig"
]

class BotConfig:
	"""Config abstraction class

	Abstracts the base config storage away from other modules.
	Handles converting toml-compatible types to the types required for actual execution."""
	def __init__(self, configFile: str):
		# Read our existing config file
		with open(configFile, "r") as file:
			_log.debug(f"Reading config file: {configFile}")
			self.toml = tomlkit.parse(file.read())

		# Set default values for our parameters
		self.toml.setdefault("prefix", "$$")
		self.toml.setdefault("bot_token", "")
		self.toml.setdefault("debug_server", -1)
		self.toml.setdefault("steam_api_token", "")
		self.toml.setdefault("google_api_file", "config/google_api.json")

		# Write any missing values back to the config file
		with open(configFile, "w") as file:
			file.write(tomlkit.dumps(self.toml))

	@property
	def prefix(self) -> str:
		return str(self.toml["prefix"])

	@property
	def bot_token(self) -> str:
		return str(self.toml["bot_token"])

	@property
	def debug_server(self) -> int:
		value = self.toml["debug_server"]
		assert isinstance(value, items.Integer)
		return int(value)

	@property
	def steam_api_token(self) -> str:
		return str(self.toml["steam_api_token"])

	@property
	def google_api_file(self) -> str:
		return str(self.toml["google_api_file"])


class ServerConfigOption:
	def __init__(self, bot: "BlueOnBlueBot", name: str, *, default: str | None = None, protected: bool = False):
		self.bot = bot
		self.name = name
		self.default = default
		self.protected = protected
		self._cache: dict[int, str] = {}


	async def _getValue(self, serverID: int) -> str | None:
		"""Retrieves a raw value from the serverconfig table

		Parameters
		----------
		serverID : int
			Discord server ID to use
		setting : str
			Setting to retrieve

		Returns
		-------
		str | None
			Setting value if found
		"""
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				await cursor.execute(
					"SELECT value FROM serverconfig WHERE server_id = :server_id AND setting = :setting AND value IS NOT NULL",
					{"server_id": serverID, "setting": self.name}
				)
				row = await cursor.fetchone()
				if row is not None:
					return row["value"]
				else:
					# If we could not find a value in the database, return the default
					return self.default


	async def _setValue(self, serverID: int, value: str) -> None:
		"""Sets a raw value on the serverconfig table

		Overwrites existing setting values if present

		Parameters
		----------
		serverID : int
			Discord server ID to use
		setting : str
			Setting to set
		value : str
			Value to set
		"""
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				await cursor.execute(
					"INSERT INTO serverconfig (server_id, setting, value) VALUES (:server_id, :setting, :value) \
					ON CONFLICT(server_id, setting) DO UPDATE SET value = :value",
					{"server_id": serverID, "setting": self.name, "value": value}
				)


	async def _clearValue(self, serverID: int) -> None:
		"""Clears a valie from the serverconfig table

		Parameters
		----------
		serverID : int
			Discord server ID to use
		setting : str
			Setting to clear
		"""
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				await cursor.execute(
					"DELETE FROM pings WHERE (server_id = :server_id AND setting = :setting)",
					{"server_id": serverID, "setting": self.name}
				)


	def _clearCache(self) -> None:
		"""Clears the cache for the config object

		Returns
		-------
		None
		"""
		self._cache = {}


	def _getTransform(self, value: str) -> str:
		"""Applies a transformation on retrieved values for the setting to store them in the cache

		Does nothing by default (input is string, output is string)

		Parameters
		----------
		value : str
			Value to transform

		Returns
		-------
		Transformed value
		"""
		return value


	def _displayTransform(self, value: str) -> str:
		"""Applies a transformation on retrieved values to be displayed in discord text

		Parameters
		----------
		value
			Value to transform

		Returns
		-------
		str
			Transformed value, suitable for placing in discord text
		"""
		return value


	def _getServerID(self, server: discord.Guild | int) -> int | None:
		"""Returns the server ID only if the provided server exists

		Parameters
		----------
		server : discord.Guild | int
			Guild to retrieve ID from

		Returns
		-------
		int | None
			Guild ID if present

		"""
		if isinstance(server, discord.Guild):
			# We already have a guild object
			return server.id
		else:
			guild = self.bot.get_guild(server)
			return guild.id if guild is not None else None


	async def delete(self, server: int | discord.Guild) -> None:
		if isinstance(server, discord.Guild):
			serverID = server.id
			guild = server
		else:
			serverID = server
			guild = self.bot.get_guild(serverID)
			if guild is None:
				return

		# Clear the value from the DB
		await self._clearValue(serverID)
		# Clear the value from the cache if it exists
		if serverID in self._cache.keys():
			del self._cache[serverID]


	async def exists(self, serverID: int) -> bool:
		"""Checks if a value exists in the serverconfig

		Stores the value in the cache if it is not already cached.

		Parameters
		----------
		serverID : int
			Discord server ID

		Returns
		-------
		bool
			Value exists
		"""
		# If the value is in the cache, return
		if serverID in self._cache.keys():
			return True
		# If it isn't, try to get it from the database
		dbValue = await self._getValue(serverID)
		if dbValue is None:
			# No value in DB
			return False
		# Value exists, store it in the cache and return true
		value = self._getTransform(dbValue)
		self._cache[serverID] = value
		return True


	async def get(self, server: int | discord.Guild) -> str | None:
		"""Retrieves the value of the serverconfig option

		Parameters
		----------
		server : int | discord.Guild
			Server to search in the config

		Returns
		-------
		None
			Default config option type will always return none
		"""
		# For the default type, always return none
		return None


	async def getDisplayValue(self, server: int | discord.Guild) -> str:
		"""Retrieves the config value, and formats it for display in discord text

		Parameters
		----------
		server : int | discord.Guild
			Discord server

		Returns
		-------
		str
			Formatted string
		"""
		value = await self.get(server)
		if value is not None:
			return self._displayTransform(value)
		else:
			return "None"


class ServerConfigString(ServerConfigOption):
	def _displayTransform(self, value: str) -> str:
		return value


	async def get(self, server: int | discord.Guild) -> str | None:
		"""Gets a string for the provided server from the serverconfig

		Parameters
		----------
		server : int | discord.Guild
			Discord guild to retrieve value from

		Returns
		-------
		String | None
			String for the provided server, if found
		"""
		if isinstance(server, discord.Guild):
			serverID = server.id
			guild = server
		else:
			serverID = server
			guild = self.bot.get_guild(serverID)
			if guild is None:
				return None

		# Retrieve the config value
		if serverID in self._cache.keys():
			value = self._cache[serverID]
		else:
			value = await self._getValue(serverID)
			if value is not None:
				self._cache[serverID] = self._getTransform(value)
		return value


	async def set(self, server: discord.Guild, value: str) -> None:
		"""Sets the provided string in the server config for this guild

		Parameters
		----------
		server : discord.Guild
			Discord guild
		role : discord.Role
			Role to set in serverconfig
		"""
		self._cache[server.id] = value
		await self._setValue(server.id, value)


class ServerConfigStringDefault(ServerConfigString):
	async def get(self, server: int | discord.Guild) -> str:
		value = await super().get(server)
		assert value is not None
		return value


class ServerConfigInteger(ServerConfigOption):
	# Store values as integers in the cache
	_cache: dict[int, int]

	def _displayTransform(self, value: int) -> str:
		return str(value)


	async def get(self, server: int | discord.Guild) -> int | None:
		"""Gets an integer for the provided server from the serverconfig

		Parameters
		----------
		server : int | discord.Guild
			Discord guild to retrieve value from

		Returns
		-------
		int | None
			Integer for the provided server, if found
		"""
		if isinstance(server, discord.Guild):
			serverID = server.id
			guild = server
		else:
			serverID = server
			guild = self.bot.get_guild(serverID)

			if guild is None:
				return None

		# Retrieve the config value
		if serverID in self._cache.keys():
			valueInt = self._cache[serverID]
		else:
			valueStr = await self._getValue(serverID)
			if valueStr is None or not valueStr.isnumeric():
				return None
			valueInt = self._getTransform(valueStr)
			self._cache[serverID] = valueInt
		return valueInt


	async def set(self, server: discord.Guild, value: int) -> None:
		"""Sets the provided integer in the server config for this guild

		Parameters
		----------
		server : discord.Guild
			Discord guild
		role : discord.Role
			Role to set in serverconfig
		"""
		self._cache[server.id] = value
		await self._setValue(server.id, str(value))


	def _getTransform(self, value: str) -> int:
		return int(value)


class ServerConfigIntegerDefault(ServerConfigInteger):
	async def get(self, server: int | discord.Guild) -> int:
		value = await super().get(server)
		assert value is not None
		return value


class ServerConfigFloat(ServerConfigOption):
	# Store values as integers in the cache
	_cache: dict[int, float]

	def _displayTransform(self, value: float) -> str:
		return str(value)


	async def get(self, server: int | discord.Guild) -> float | None:
		"""Gets a float for the provided server from the serverconfig

		Parameters
		----------
		server : int | discord.Guild
			Discord guild to retrieve value from

		Returns
		-------
		Float | None
			Float for the provided server, if found
		"""
		if isinstance(server, discord.Guild):
			serverID = server.id
			guild = server
		else:
			serverID = server
			guild = self.bot.get_guild(serverID)

			if guild is None:
				return None

		# Retrieve the config value
		if serverID in self._cache.keys():
			valueFloat = self._cache[serverID]
		else:
			valueStr = await self._getValue(serverID)
			if valueStr is None:
				return None
			else:
				# Retrieved value is not none, try to convert it to float
				try:
					valueFloat = self._getTransform(valueStr)
					self._cache[serverID] = valueFloat
				except ValueError:
					# If this fails, return none
					valueFloat = None

		return valueFloat


	async def set(self, server: discord.Guild, value: float) -> None:
		"""Sets the provided integer in the server config for this guild

		Parameters
		----------
		server : discord.Guild
			Discord guild
		role : discord.Role
			Role to set in serverconfig
		"""
		self._cache[server.id] = value
		await self._setValue(server.id, str(value))


	def _getTransform(self, value: str) -> float:
		return float(value)


class ServerConfigFloatDefault(ServerConfigFloat):
	async def get(self, server: int | discord.Guild) -> float:
		value = await super().get(server)
		assert value is not None
		return value


class ServerConfigRole(ServerConfigOption):
	# Store role IDs as integers in the cache
	_cache: dict[int, int]

	def _displayTransform(self, value: discord.Role) -> str:
		return value.mention


	async def get(self, server: int | discord.Guild) -> discord.Role | None:
		"""Gets a role for the provided server from the serverconfig

		Parameters
		----------
		server : int | discord.Guild
			Discord guild to retrieve value from

		Returns
		-------
		discord.Role | None
			Discord role for the provided server, if found
		"""
		if isinstance(server, discord.Guild):
			serverID = server.id
			guild = server
		else:
			serverID = server
			guild = self.bot.get_guild(serverID)

			if guild is None:
				return None

		# Retrieve the role ID
		if serverID in self._cache.keys():
			roleID = self._cache[serverID]
		else:
			roleStr = await self._getValue(serverID)
			if roleStr is None or not roleStr.isnumeric():
				return None
			roleID = self._getTransform(roleStr)
			self._cache[serverID] = roleID
		return guild.get_role(roleID)


	async def set(self, server: discord.Guild, role: discord.Role) -> None:
		"""Sets the provided role in the server config for this guild

		Parameters
		----------
		server : discord.Guild
			Discord guild
		role : discord.Role
			Role to set in serverconfig
		"""
		self._cache[server.id] = role.id
		await self._setValue(server.id, str(role.id))


	def _getTransform(self, value: str) -> int:
		return int(value)


class ServerConfigChannel(ServerConfigOption):
	# Store channel IDs as integers in the cache
	_cache: dict[int, int]

	def _displayTransform(self, value: discord.abc.GuildChannel) -> str:
		return value.mention


	async def get(self, server: int | discord.Guild) -> discord.abc.GuildChannel | None:
		"""Gets a channel for the provided server from the serverconfig

		Parameters
		----------
		server : int | discord.Guild
			Discord guild to retrieve value from

		Returns
		-------
		discord.abc.GuildChannel | None
			Channel in the provided server, if found
		"""
		if isinstance(server, discord.Guild):
			serverID = server.id
			guild = server
		else:
			serverID = server
			guild = self.bot.get_guild(serverID)

			if guild is None:
				return None

		# Retrieve the channel ID
		if serverID in self._cache.keys():
			channelID = self._cache[serverID]
		else:
			channelStr = await self._getValue(serverID)
			if channelStr is None or not channelStr.isnumeric():
				return None
			channelID = self._getTransform(channelStr)
			self._cache[serverID] = channelID
		return guild.get_channel(channelID)


	async def set(self, server: discord.Guild, channel: discord.abc.GuildChannel) -> None:
		"""Sets the provided role in the server config for this guild

		Parameters
		----------
		server : discord.Guild
			Discord guild
		role : discord.Role
			Role to set in serverconfig
		"""
		self._cache[server.id] = channel.id
		await self._setValue(server.id, str(channel.id))


	def _getTransform(self, value: str) -> int:
		return int(value)


class ServerConfig:
	"""Server config abstraction class.

	Handles storing custom data types with data validation in the SQLite database
	Uses helper functions and properties to automatically convert SQLite database types
	to discord.py or other python types when retrieving values.
	"""
	def __init__(self, bot: "BlueOnBlueBot"):
		self.bot = bot

		# Initialize the config options
		# Server channels
		self.channel_bot = ServerConfigChannel(bot, "channel_bot")
		self.channel_check_in = ServerConfigChannel(bot, "channel_check_in")
		self.channel_mission_audit = ServerConfigChannel(bot, "channel_mission_audit")
		self.channel_mod_activity = ServerConfigChannel(bot, "channel_mod_activity")

		# Server roles
		self.role_gold = ServerConfigRole(bot, "role_gold")
		self.role_jail = ServerConfigRole(bot, "role_jail")
		self.role_member = ServerConfigRole(bot, "role_member")

		# Steam Group and verify URL
		self.steam_group_id = ServerConfigInteger(bot, "steam_group_id")
		self.group_apply_url = ServerConfigString(bot, "group_apply_url")

		# Missions config
		self.mission_sheet_key = ServerConfigString(bot, "mission_sheet_key")
		self.mission_worksheet = ServerConfigStringDefault(bot, "mission_worksheet", default = "Schedule")
		self.mission_wiki_url = ServerConfigString(bot, "mission_wiki_url")

		# Arma stats config
		self.arma_stats_key = ServerConfigString(bot, "arma_stats_key", protected = True)
		self.arma_stats_url = ServerConfigString(bot, "arma_stats_url")
		self.arma_stats_min_duration = ServerConfigIntegerDefault(bot, "arma_stats_min_duration", default = "90")
		self.arma_stats_min_players = ServerConfigIntegerDefault(bot, "arma_stats_min_players", default = "10")
		self.arma_stats_participation_threshold = ServerConfigFloatDefault(bot, "arma_stats_participation_threshold", default = "0.5")

		# Initialize our options dict
		self.options: dict[str, ServerConfigOption] = {}
		for m in inspect.getmembers(self):
			if isinstance(m[1], ServerConfigOption):
				self.options[m[0]] = m[1]
