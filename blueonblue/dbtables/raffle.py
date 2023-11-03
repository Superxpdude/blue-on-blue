from .base import BaseTable
from datetime import datetime, timezone

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


	async def createGroup(self, guildID: int, endTime: datetime) -> int:
		"""Creates a raffle group in the database

		Parameters
		----------
		guildID : int
			Guild ID
		endTime : datetime
			End time for the raffle group

		Returns
		-------
		int
			Database ID of the raffle group
		"""
		async with self.db.connection.cursor() as cursor:
			await cursor.execute(
				"INSERT INTO raffle_groups (server_id, end_time) VALUES (:server_id, :end_time)",
				{
					"server_id": guildID,
					"end_time": round(datetime.now(timezone.utc).timestamp())
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
				{ "group_id": groupID, "message_id": messageID}
			)
