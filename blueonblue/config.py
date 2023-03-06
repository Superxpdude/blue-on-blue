import discord
import tomlkit
from tomlkit import items

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
	def __init__(self, bot: "BlueOnBlueBot", name: str):
		self.bot = bot
		self.name = name


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
					return None


	async def _setValue(self, serverID: int, value: str):
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


class ServerConfigRole(ServerConfigOption):

	def __init__(self, bot: "BlueOnBlueBot", name: str):
		self.data: dict[int, discord.Role] = {}
		super().__init__(bot, name)

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
		roleStr = await self._getValue(serverID)
		if guild is None or roleStr is None or not roleStr.isnumeric():
			return None
		return guild.get_role(int(roleStr))


	async def set(self, server: discord.Guild, role: discord.Role):
		"""Sets the provided role in the server config for this guild

		Parameters
		----------
		server : discord.Guild
			Discord guild
		role : discord.Role
			Role to set in serverconfig
		"""
		await self._setValue(server.id, str(role.id))



class ServerConfig:
	"""Server config abstraction class.

	Handles storing custom data types with data validation in the SQLite database
	Uses helper functions and properties to automatically convert SQLite database types
	to discord.py or other python types when retrieving values.
	"""
	def __init__(self, bot: "BlueOnBlueBot"):
		self.bot = bot
