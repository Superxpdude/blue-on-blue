from .base import BaseTable
from datetime import datetime, timezone
import discord

class Pings(BaseTable):
	"""Ping table class"""
	_tableName = "pings"
	_userTable  = "ping_users"

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


	async def create_alias(self, alias: str, targetID: int, guildID: int) -> None:
		"""Creates an alias for an existing ping

		Parameters
		----------
		alias : str
			Alias tag to create
		targetID : int
			Ping ID to link the alias to
		guildID : int
			Discord guild ID
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute("INSERT INTO :table_name (server_id, ping_name, alias_for) VALUES (:server_id, :alias, :id)",
				{
					"table_name": self._tableName,
					"server_id": guildID,
					"alias": alias.casefold(),
     				"id": targetID,
				}
			)


	async def delete_alias(self, alias: str, guildID: int) -> None:
		"""Deletes an alias

		Parameters
		----------
		alias : str
			Alias to delete
		guildID : int
			Discord guild ID
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute("DELETE FROM :table_name WHERE (server_id = :server_id AND ping_name = :alias AND alias_for IS NOT NULL)",
				{
					"table_name": self._tableName,
					"server_id": guildID,
					"alias": alias.casefold()
				}
			)


	async def update_ping_time(self, tag: str, guildID: int) -> None:
		"""Updates the last-used-time for a ping

		Parameters
		----------
		tag : str
			Ping tag to update
		guildID : int
			Discord guild ID
		"""
		async with self.db.connection.cursor() as cursor:
			time = round(datetime.now(timezone.utc).timestamp()) # Get the current time in timestamp format
			pingID = await self.get_id(tag, guildID)
			await cursor.execute("UPDATE :table_name SET last_used_time = :time WHERE id = :id",
				{
					"table_name": self._tableName,
					"time": time,
					"id": pingID
				}
			)


	async def add_user(self, tag: str, guildID: int, userID: int) -> bool:
		"""Adds a user to a ping

		Parameters
		----------
		tag : str
			Ping tag
		guildID : int
			Discord guild ID
		userID : int
			User ID to add

		Returns
		-------
		bool
			If the user was added to the ping
		"""
		async with self.db.connection.cursor() as cursor:
			pingID = await self.get_id(tag, guildID)
			if pingID is not None:
				await cursor.execute("INSERT OR REPLACE INTO :table_name (server_id, ping_id, user_id) VALUES (:server_id, :ping, :user_id)",
					{
						"table_name": self._userTable,
						"server_id": guildID,
						"ping": pingID,
						"user_id": userID
					}
				)
				return True
			else: # Ping does not exist. Could not add user.
				return False


	async def remove_user(self, tag: str, guildID: int, userID: int) -> bool:
		"""Removes a user from a ping

		Parameters
		----------
		tag : str
			Ping tag
		guildID : int
			Discord guild ID
		userID : int
			User ID to add

		Returns
		-------
		bool
			If the user was removed from the ping
		"""
		async with self.db.connection.cursor() as cursor:
			pingID = await self.get_id(tag, guildID)
			if pingID is not None:
				# No server reference needed here. Ping IDs must be globally unique.
				await cursor.execute("DELETE FROM :table_name WHERE (ping_id = :ping AND user_id = :user_id)",
					{
						"table_name": self._userTable,
						"ping": pingID,
						"user_id": userID
					}
				)
				return True
			else: # Ping does not exist. Could not remove user.
				return False


	async def remove_user_by_id(self, pingID: int, userID: int) -> bool:
		"""Removes a user from a ping using a ping ID

		Parameters
		----------
		pingID : int
			Ping ID
		userID : int
			User ID

		Returns
		-------
		bool
			If the user was removed from the ping
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute("DELETE FROM :table_name WHERE (ping_id = :ping AND user_id = :user_id)",
				{
					"table_name": self._userTable,
					"ping": pingID,
					"user_id": userID
				}
			)
			return True


	async def has_user(self, tag: str, guildID: int, userID: int) -> bool:
		"""Checks if a ping has a specific user

		Parameters
		----------
		tag : str
			Ping tag to check
		guildID : int
			Discord guild ID
		userID : int
			User ID to check

		Returns
		-------
		bool
			If the user is in the ping
		"""
		async with self.db.connection.cursor() as cursor:
			pingID = await self.get_id(tag, guildID)
			if pingID is not None:
				# No server reference needed here. Ping IDs must be globally unique.
				await cursor.execute("SELECT user_id FROM :table_name WHERE server_id = :server_id AND ping_id = :ping AND user_id = :user_id",
					{
						"table_name": self._userTable,
						"server_id": guildID,
						"ping": pingID,
						"user_id": userID
					}
				)
				userPing = await cursor.fetchone()
				return userPing is not None # Return if the user is in the ping
			else: # Ping does not exist. Return false.
				return False


	async def count_users(self, tag: str, guildID: int) -> int:
		"""Counts the number of users present in a ping.
		Pings that do not exist will return -1.

		Parameters
		----------
		tag : str
			Ping tag to check
		guildID : int
			Discord guild ID

		Returns
		-------
		int
			Number of users in a ping
		"""
		async with self.db.connection.cursor() as cursor:
			pingID = await self.get_id(tag, guildID)
			if pingID is None:
				return -1
			else: # Ping exists
				await cursor.execute("SELECT COUNT(*) FROM :table_name WHERE ping_id = :ping",
					{
						"table_name": self._userTable,
						"ping": pingID
					}
				)
				return (await cursor.fetchone())[0]


	async def count_active_users(self, tag: str, guild: discord.Guild) -> int:
		"""Counts the number of users present in a ping that are currently in the server.
		Slower than count_users() since it has to check user membership.
		Pings that do not exist will return -1.

		Parameters
		----------
		tag : str
			Ping tag to check
		guild : discord.Guild
			Discord guild

		Returns
		-------
		int
			Number of users in a ping
		"""
		async with self.db.connection.cursor() as cursor:
			pingID = await self.get_id(tag, guild.id)
			if pingID is None:
				return -1
			else: # Ping exists
				await cursor.execute("SELECT user_id FROM :table_name WHERE ping_id = :ping",
					{
						"table_name": self._userTable,
						"ping": pingID
					}
				)
				userIDs = await cursor.fetchall()
				userCount = 0 # Start the count
				for u in userIDs:
					if (guild.get_member(u["user_id"])) is not None:
						userCount += 1 # Increment usercount by 1
				return userCount


	async def get_user_ids_by_ping_id(self, pingID: int) -> tuple[int]:
		"""Returns a tuple of user IDs present in a ping by using the ping ID.
		Empty or invalid pings will return an empty list.

		Parameters
		----------
		pingID : int
			Ping ID

		Returns
		-------
		tuple[int]
			Tuple of discord user IDs
		"""
		async with self.db.connection.cursor() as cursor:
			userIDList = []
			await cursor.execute("SELECT user_id FROM :table_name WHERE ping_id = :ping",
				{
					"table_name": self._userTable,
					"ping": pingID
				}
			)
			pingData = await cursor.fetchall()
			for p in pingData:
				if "user_id" in p.keys():
					userIDList.append(p["user_id"])
			return tuple(userIDList)
