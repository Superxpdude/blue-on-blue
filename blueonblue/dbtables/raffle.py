from typing import TYPE_CHECKING
if TYPE_CHECKING:
	from ..db import DBConnection

class RaffleWeights:
	def __init__(self, db: "DBConnection"):
		self.db = db


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
				return data["weight"]


	async def setRaffleWeight(self, guildID: int, userID: int, weight: float) -> None:
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
