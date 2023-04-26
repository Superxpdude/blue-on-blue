from .base import BaseTable

class Pings(BaseTable):
	"""Ping table class"""
	_tableName = "pings"

	async def ping_exists(self, tag: str, guildID: int) -> bool:
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
				{"table_name": self._tableName, "server_id": guildID, "ping": tag.casefold(),}
			)
			ping = await cursor.fetchone()
			# Return false if ping is none, true otherwise
			return not ping is None


	async def ping_is_alias(self, tag: str, guildID: int) -> bool:
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
				{"table_name": self._tableName, "server_id": guildID, "ping": tag.casefold(),}
			)
			ping = await cursor.fetchone()
			# Return false if ping is none, true otherwise
			return not ping is None


	async def ping_get_id(self, tag: str, guildID: int) -> int | None:
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
				{"table_name": self._tableName, "server_id": guildID, "ping": tag.casefold(),}
			)
			ping = await cursor.fetchone()

			if ping is None: # Tag does not exist
				return None

			# Tag exists
			if ping["alias_for"] is not None:
				return ping["alias_for"]
			else:
				return ping["id"]
