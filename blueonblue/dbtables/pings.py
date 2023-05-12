from .base import BaseTable
from datetime import datetime, timezone

class Pings(BaseTable):
	"""Ping table class"""
	_tableName = "pings"

	async def exists(self, tag: str, guildID: int) -> bool:
		"""Checks if a tag exists in the database for a specific guild.

		Parameters
		----------
		tag : str
			Tag to check
		guildID : int
			Discord guild ID

		Returns
		-------
		bool
			Tag exists in guild
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT id FROM :table_name WHERE server_id = :server_id AND ping_name = :ping",
				{"table_name": self._tableName, "server_id": guildID, "ping": tag.casefold()}
			)
			ping = await cursor.fetchone()
			# Return false if ping is none, true otherwise
			return not ping is None


	async def is_alias(self, tag: str, guildID: int) -> bool:
		"""Checks if a tag is an alias for another tag

		Parameters
		----------
		tag : str
			Tag to check
		guildID : int
			Discord guild ID

		Returns
		-------
		bool
			Tag exists as an alias
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT alias_for FROM :table_name WHERE server_id = :server_id AND ping_name = :ping AND alias_for IS NOT NULL",
				{"table_name": self._tableName, "server_id": guildID, "ping": tag.casefold()}
			)
			ping = await cursor.fetchone()
			# Return false if ping is none, true otherwise
			return not ping is None


	async def get_id(self, tag: str, guildID: int) -> int | None:
		"""Gets the ID reference for a tag.
		If the tag is an alias, get the alias ID. Otherwise, get the tag ID.
		Returns None if the tag was not found.

		Parameters
		----------
		tag : str
			Tag to check
		guildID : int
			Discord guild ID

		Returns
		-------
		int | None
			Tag ID of ping if found
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT id, alias_for FROM :table_name WHERE server_id = :server_id AND ping_name = :ping",
				{"table_name": self._tableName, "server_id": guildID, "ping": tag.casefold()}
			)
			ping = await cursor.fetchone()

			if ping is None: # Tag does not exist
				return None

			# Tag exists
			if ping["alias_for"] is not None:
				return ping["alias_for"]
			else:
				return ping["id"]


	async def get_name(self, id: int, guildID: int) -> str | None:
		"""Gets the name of a tag from its ID.
		Returns None if the tag was not found.

		Parameters
		----------
		id : int
			Tag ID
		guildID : int
			Discord guild ID

		Returns
		-------
		str | None
			Tag name of ping if found
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT ping_name FROM :table_name WHERE server_id = :server_id AND id = :id",
				{"table_name": self._tableName, "server_id": guildID, "id": id}
			)
			ping = await cursor.fetchone()

			if ping is None: # Tag does not exist
				return None
			else:
				return ping["ping_name"]


	async def get_alias_names(self, id: int, guildID: int) -> tuple[str]:
		"""Gets the names of all aliases for a given ping.
		Returns a tuple containing all names.
		When no aliases are present, the returned tuple will be empty.

		Parameters
		----------
		id : int
			Tag ID
		guildID : int
			Discord guild ID

		Returns
		-------
		tuple[str]
			Tuple of alias names
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT ping_name FROM :table_name WHERE server_id = :server_id AND alias_for = :id",
				{"table_name": self._tableName, "server_id": guildID, "id": id}
			)
			aliasData = await cursor.fetchall()

			aliasNames = []
			for a in aliasData:
				aliasNames.append(a["ping_name"])
			return tuple(aliasNames)


	async def create(self, tag: str, guildID: int) -> None:
		"""Creates a ping using the given tag.

		Parameters
		----------
		tag : str
			Tag to use
		guildID : int
			Discord guild ID
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"INSERT INTO :table_name (server_id, ping_name, last_used_time) VALUES (:server_id, :ping, :time)",
				{
					"table_name": self._tableName,
					"server_id": guildID,
     				"ping": tag.casefold(),
					"time": round(datetime.now(timezone.utc).timestamp())
				}
			)


	async def delete_tag(self, tag: str, guildID: int) -> None:
		"""Deletes the ping with a given tag.

		Parameters
		----------
		tag : str
			Ping tag to delete
		guildID : int
			Discord guild ID
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute("DELETE FROM :table_name WHERE (server_id = :server_id AND ping_name = :ping)",
				{
					"table_name": self._tableName,
					"server_id": guildID,
     				"ping": tag.casefold()
				}
			)


	async def delete_id(self, id: int, guildID: int) -> None:
		"""Deletes the ping with a given ID.

		Parameters
		----------
		id : int
			Ping ID to delete
		guildID : int
			Discord guild ID
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute("DELETE FROM :table_name WHERE (server_id = :server_id AND id = :id)",
				{
					"table_name": self._tableName,
					"server_id": guildID,
     				"id": id
				}
			)
