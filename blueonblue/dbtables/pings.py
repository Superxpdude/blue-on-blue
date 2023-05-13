from .base import BaseTable
from datetime import datetime, timezone
import discord
from typing import NamedTuple


class PingInfo(NamedTuple):
	id: int
	server_id: int
	name: str
	alias: int | None


class Pings(BaseTable):
	"""Ping table class"""


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
				"SELECT id FROM pings WHERE server_id = :server_id AND ping_name = :ping",
				{"server_id": guildID, "ping": tag.casefold()}
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
				"SELECT alias_for FROM pings WHERE server_id = :server_id AND ping_name = :ping AND alias_for IS NOT NULL",
				{"server_id": guildID, "ping": tag.casefold()}
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
				"SELECT id, alias_for FROM pings WHERE server_id = :server_id AND ping_name = :ping",
				{"server_id": guildID, "ping": tag.casefold()}
			)
			ping = await cursor.fetchone()

			if ping is None: # Tag does not exist
				return None

			# Tag exists
			if ping["alias_for"] is not None:
				return ping["alias_for"]
			else:
				return ping["id"]


	async def get_name(self, id: int) -> str | None:
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
				"SELECT ping_name FROM pings WHERE id = :id",
				{"id": id}
			)
			ping = await cursor.fetchone()

			if ping is None: # Tag does not exist
				return None
			else:
				return ping["ping_name"]


	async def get_alias_names(self, id: int) -> tuple[str]:
		"""Gets the names of all aliases for a given ping.
		Returns a tuple containing all names.
		When no aliases are present, the returned tuple will be empty.

		Parameters
		----------
		id : int
			Tag ID

		Returns
		-------
		tuple[str]
			Tuple of alias names
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT ping_name FROM pings WHERE alias_for = :id",
				{"id": id}
			)
			aliasData = await cursor.fetchall()

			aliasNames = []
			for a in aliasData:
				aliasNames.append(a["ping_name"])
			return tuple(aliasNames)


	async def create(self, tag: str, guildID: int) -> int:
		"""Creates a ping using the given tag.

		Parameters
		----------
		tag : str
			Tag to use
		guildID : int
			Discord guild ID

		Returns
		-------
		int
			Ping ID of created ping
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"INSERT INTO pings (server_id, ping_name, last_used_time) VALUES (:server_id, :ping, :time)",
				{
					"server_id": guildID,
     				"ping": tag.casefold(),
					"time": round(datetime.now(timezone.utc).timestamp())
				}
			)
			await cursor.execute("SELECT last_insert_rowid() as db_id")
			return (await cursor.fetchone())["db_id"]


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
			await cursor.execute("DELETE FROM pings WHERE (server_id = :server_id AND ping_name = :ping)",
				{
					"server_id": guildID,
     				"ping": tag.casefold()
				}
			)


	async def delete_id(self, id: int) -> None:
		"""Deletes the ping with a given ID.

		Parameters
		----------
		id : int
			Ping ID to delete
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute("DELETE FROM pings WHERE (id = :id)",
				{
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
			await cursor.execute("INSERT INTO pings (server_id, ping_name, alias_for) VALUES (:server_id, :alias, :id)",
				{
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
			await cursor.execute("DELETE FROM pings WHERE (server_id = :server_id AND ping_name = :alias AND alias_for IS NOT NULL)",
				{
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
			await cursor.execute("UPDATE pings SET last_used_time = :time WHERE id = :id",
				{
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
				await cursor.execute("INSERT OR REPLACE INTO ping_users (server_id, ping_id, user_id) VALUES (:server_id, :ping, :user_id)",
					{
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
				await cursor.execute("DELETE FROM ping_users WHERE (ping_id = :ping AND user_id = :user_id)",
					{
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
			await cursor.execute("DELETE FROM ping_users WHERE (ping_id = :ping AND user_id = :user_id)",
				{
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
				await cursor.execute("SELECT user_id FROM ping_users WHERE server_id = :server_id AND ping_id = :ping AND user_id = :user_id",
					{
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
				await cursor.execute("SELECT COUNT(*) as count FROM ping_users WHERE ping_id = :ping",
					{
						"ping": pingID
					}
				)
				return (await cursor.fetchone())["count"]


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
				await cursor.execute("SELECT user_id FROM ping_users WHERE ping_id = :ping",
					{
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
			await cursor.execute("SELECT user_id FROM ping_users WHERE ping_id = :ping",
				{
					"ping": pingID
				}
			)
			pingData = await cursor.fetchall()
			for p in pingData:
				if "user_id" in p.keys():
					userIDList.append(p["user_id"])
			return tuple(userIDList)


	async def server_pings(self, guildID: int, *, search: str | None = None, beforeTime: datetime | None = None) -> tuple[str]:
		"""Retrieves a tuple of ping tags for a server

		Parameters
		----------
		guildID : int
			Discord guild ID
		search : str | None, optional
			Only return results matching the search string if present, by default None
		beforeTime: datetime.datetime | None, optional
			Only return results before this timestamp. Does nothing if search is used.

		Returns
		-------
		tuple[str]
			Tuple of ping tags
		"""
		async with self.db.connection.cursor() as cursor:
			if search is not None:
				# Search string present.
				# ("SELECT ping_name FROM pings WHERE server_id = ? AND ping_name LIKE ? AND alias_for IS NULL", (interaction.guild.id,"%"+tag+"%",))
				await cursor.execute("SELECT ping_name FROM pings WHERE server_id = :server_id AND ping_name LIKE :search AND alias_for IS NULL",
			 		{
						"server_id": guildID,
						"search": f"%{search}%"
					}
				)
			elif beforeTime is not None:
				# Before time specified. Only return results last used before this time
				await cursor.execute("SELECT ping_name FROM pings WHERE server_id = :server_id AND last_used_time < :time AND alias_for IS NULL",
					{
						"server_id": guildID,
						"time": round(beforeTime.timestamp())
					}
				)
			else:
				# No search string. Return all pings.
				await cursor.execute("SELECT ping_name FROM pings WHERE server_id = :server_id AND alias_for IS NULL",
					{
						"server_id": guildID
					}
				)
			pingResults: list[str] = []
			for p in (await cursor.fetchall()):
				if "ping_name" in p.keys():
					pingResults.append(p["ping_name"])

			return tuple(pingResults)


	async def ping_info(self, tag: str, guildID: int) -> PingInfo:
		"""Retrieves information about a ping

		Parameters
		----------
		tag : str
			Tag to retrieve
		guildID : int
			Discord guild ID

		Returns
		-------
		PingInfo
			Named tuple of ping information
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT * FROM pings WHERE server_id = :server_id AND ping_name = :ping",
				{"server_id": guildID, "ping": tag.casefold()}
			)
			pingInfo = await cursor.fetchone()

			return PingInfo(
				pingInfo["id"],
				pingInfo["server_id"],
				pingInfo["ping_name"],
				pingInfo["alias_for"]
			)


	async def migrate_ping(self, fromID: int, toID: int) -> None:
		"""Migrates users and aliases from one ping to another

		Parameters
		----------
		fromID : int
			Ping ID to migrate from
		toID : int
			Ping ID to migrate to
		"""
		async with self.db.connection.cursor() as cursor:
			# Migrate users
			await cursor.execute("UPDATE ping_users SET ping_id = :toID WHERE ping_id = :fromID",
				{"toID": toID, "fromID": fromID}
			)
			# Migrate aliases
			await cursor.execute("UPDATE pings SET alias_for = :toID WHERE alias_for = :fromID",
				{"toID": toID, "fromID": fromID}
			)
