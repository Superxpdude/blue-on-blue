import logging
from types import TracebackType
from typing import (
	Optional,
	Type,
)

import asqlite

from . import dbtables

_log = logging.getLogger(__name__)

__all__ = ["DB", "DBConnection"]


class DBConnection:
	"""BlueonBlue database connection class.

	Used to manage a custom asqlite connection context manager so that the database file only needs to be defined once."""

	connection: asqlite.Connection

	def __init__(self, dbFile: str):
		self._dbFile = dbFile

		# Initialize tables
		self.raffleWeight = dbtables.RaffleWeights(self)
		self.pings = dbtables.Pings(self)

	async def commit(self) -> None:
		"""Convenience function to commit changes on the connection"""
		await self.connection.commit()

	async def __aenter__(self) -> "DBConnection":
		self.connection = await asqlite.connect(self._dbFile)
		return self

	async def __aexit__(
		self,
		exc_type: Optional[Type[BaseException]],
		exc_value: Optional[BaseException],
		traceback: Optional[TracebackType],
	) -> None:
		await self.connection.close()


class DB:
	"""Database class to initialize a connection to the bot's database

	Only to be used in an async context manager"""

	connection: asqlite.Connection

	def __init__(self, dbFile: str):
		self._dbFile = dbFile

	def connect(self) -> DBConnection:
		return DBConnection(self._dbFile)
