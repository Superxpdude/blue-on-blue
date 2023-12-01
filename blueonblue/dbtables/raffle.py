from .base import BaseTable
from datetime import datetime

class RaffleWeights(BaseTable):
	"""Raffle Weights table class"""


	async def getWeight(self, guildID: int, userID: int) -> float:
		"""Returns the raffle weight of a user from the database

		Parameters
		----------
		guildID: int
			Guild ID to check
		userID : int
			User ID to check

		Returns
		-------
		float
			Raffle weight. Defaults to 1 if not found
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute("SELECT weight FROM raffle_weights WHERE server_id = :server_id AND user_id = :user_id", {"server_id": guildID, "user_id": userID})
			data = await cursor.fetchone()
			if data is None:
				return 1.0
			else:
				return float(data["weight"])


	async def setWeight(self, guildID: int, userID: int, weight: float) -> None:
		"""Sets the raffle weight for a participant

		Parameters
		----------
		guildID : int
			Guild ID
		userID : int
			User ID
		weight : float
			New weight to set
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute("INSERT INTO raffle_weights (server_id, user_id, weight)\
				VALUES (:server_id, :user_id, :weight)\
				ON CONFLICT (server_id, user_id) DO UPDATE\
				SET weight == :weight",
				{"server_id": guildID, "user_id": userID, "weight": weight}
			)


	async def increaseWeight(self, guildID: int, userID: int, increase: float, maxWeight: float = 3.0) -> None:
		"""Increase the raffle weight for a user.
		Creates the raffle weight entry for the user if it does not exist

		Parameters
		----------
		guildID : int
			Guild ID
		userID : int
			User ID
		increase : float
			Increase amount
		maxWeight : float
			Maximum raffle weight
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"INSERT INTO raffle_weights (user_id, server_id, weight) VALUES (:user_id, :server_id, 1 + :increase)\
				ON CONFLICT (user_id, server_id) DO\
				UPDATE SET weight = MIN(:max, \
					(SELECT weight FROM raffle_weights WHERE user_id = :user_id) + :increase\
				)",
				{"server_id": guildID, "user_id": userID, "increase": increase, "max": maxWeight}
			)


class Raffles(BaseTable):
	"""Raffle tables class"""


	async def createGroup(self, guildID: int, endTime: datetime, exclusive: bool = False, weighted: bool = False) -> int:
		"""Creates a raffle group in the database

		Parameters
		----------
		guildID : int
			Guild ID
		endTime : datetime
			End time for the raffle group
		exclusive : bool, optional
			Exclusive winners for raffles in this group, by default False

		Returns
		-------
		int
			Database ID of the raffle group
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"INSERT INTO raffle_groups (server_id, end_time, exclusive, weighted)\
				VALUES (:server_id, :end_time, :exclusive, :weighted)",
				{
					"server_id": guildID,
					"end_time": endTime.isoformat(),
					"exclusive": exclusive,
					"weighted": weighted,
				}
			)
			await cursor.execute("SELECT last_insert_rowid() as db_id")
			return (await cursor.fetchone())["db_id"]


	async def setGroupMessageID(self, groupID: int, messageID: int) -> None:
		"""Sets the message ID for a raffle group

		Parameters
		----------
		groupID : int
			Group database ID
		messageID : int
			Discord message ID
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"UPDATE raffle_groups SET message_id = :message_id WHERE id = :group_id",
				{"group_id": groupID, "message_id": messageID}
			)


	async def groupExists(self, groupID: int) -> bool:
		"""Checks if a raffle group exists

		Parameters
		----------
		groupID : int
			Raffle group ID to check

		Returns
		-------
		bool
			If the raffle group exists
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT id FROM raffle_groups WHERE id = :group_id",
				{"group_id": groupID}
			)

			return (await cursor.fetchone()) is not None


	async def deleteGroup(self, groupID: int) -> None:
		"""Deletes a raffle group

		Parameters
		----------
		groupID : int
			Group ID of the group to delete
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"DELETE FROM raffle_groups WHERE (id = :group_id)",
				{"group_id": groupID}
			)


	async def createRaffle(self, groupID: int, title: str, winners: int = 1) -> int:
		"""Creates a raffle entry

		Parameters
		----------
		groupID : int
			Raffle group ID to associate the raffle with
		title : str
			Raffle title
		winners : int, optional
			Winner count, by default 1

		Returns
		-------
		int
			Database ID of the raffle
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"INSERT INTO raffle_data (group_id, title, winners) VALUES (:group_id, :title, :winners)",
				{
					"group_id": groupID,
					"title": title,
					"winners": winners,
				}
			)
			await cursor.execute("SELECT last_insert_rowid() as db_id")
			return (await cursor.fetchone())["db_id"]


	async def raffleExists(self, raffleID: int) -> bool:
		"""Checks if a given raffle ID exists

		Parameters
		----------
		raffleID : int
			Raffle ID to check

		Returns
		-------
		bool
			If the raffle exists in the database
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT id FROM raffle_data WHERE id = :raffle_id",
				{"raffle_id": raffleID}
			)
			data = await cursor.fetchone()
			return data is not None


	async def getRaffleName(self, raffleID: int) -> str:
		"""Retrieves the name of a raffle

		Parameters
		----------
		raffleID : int
			Raffle ID to use

		Returns
		-------
		str
			Retrieved name of the raffle
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT title FROM raffle_data WHERE id = :raffle_id",
				{"raffle_id": raffleID}
			)
			raffleData = await cursor.fetchone()

			if raffleData is not None:
				return raffleData["title"]
			else:
				return "Error"


	async def addRaffleUser(self, raffleID: int, discordID: int) -> None:
		"""Adds a user to a raffle

		Parameters
		----------
		raffleID : int
			Raffle ID to add the user to
		discordID : int
			Discord ID of the user
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"INSERT INTO raffle_users (raffle_id, discord_id) VALUES (:raffle_id, :discord_id)",
				{
					"raffle_id": raffleID,
					"discord_id": discordID,
				}
			)


	async def removeRaffleUser(self, raffleID: int, discordID: int) -> None:
		"""Removes a user from a raffle

		Parameters
		----------
		raffleID : int
			Raffle ID to remove the user from
		discordID : int
			Discord ID of the user
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute("\
				DELETE FROM raffle_users WHERE (\
				raffle_id = :raffle_id AND\
				discord_id = :discord_id)",
				{
					"raffle_id": raffleID,
					"discord_id": discordID,
				}
			)


	async def userInRaffle(self, raffleID: int, discordID: int) -> bool:
		"""Checks if a user is already in a raffle.

		Parameters
		----------
		raffleID : int
			Raffle ID to check
		discordID : int
			Discord ID of the user

		Returns
		-------
		bool
			If the user is in the raffle
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT discord_id FROM raffle_users WHERE (raffle_id = :raffle_id AND discord_id = :discord_id)",
				{"raffle_id": raffleID, "discord_id": discordID}
			)
			userData = await cursor.fetchone()

			return userData is not None


	async def getRaffleParticipants(self, raffleID: int) -> tuple[int,...]:
		"""Gets discord IDs for all participants of a raffle

		Parameters
		----------
		raffleID : int
			Raffle ID

		Returns
		-------
		tuple[int,...]
			Tuple of participant discord IDs
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"SELECT discord_id FROM raffle_users WHERE raffle_id = :raffle_id",
				{"raffle_id": raffleID}
			)
			userData = await cursor.fetchall()

			users = []
			for u in userData:
				users.append(u["discord_id"])
			return tuple(users)
