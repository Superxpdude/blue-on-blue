import asqlite

from typing import (
	Optional,
	Type,
)

from types import TracebackType

import logging
log = logging.getLogger(__name__)

__all__ = [
	"DB"
]

class DB():
	"""Database class to initialize a connection to the bot's database

	Only to be used in an async context manager"""
	connection: asqlite.Connection

	def __init__(self, dbFile: str):
		self._dbFile = dbFile
		self._dbVersion = 1

	async def __aenter__(self) -> asqlite.Connection:
		self.connection = await asqlite.connect(self._dbFile)
		return self.connection

	async def __aexit__(
		self,
		exc_type: Optional[Type[BaseException]],
		exc_value: Optional[BaseException],
		traceback: Optional[TracebackType],
	) -> None:
		await self.connection.close()

	# WIP. Will Write migration code in here for future versions
	async def migrate_version(self) -> None:
		"""Migrates the database to the latest schema version.

		Does nothing if the database is already up to date.
		"""
		async with self as db:
			async with db.cursor() as cursor:
				version = (await (await cursor.execute("PRAGMA user_version")).fetchone())["user_version"]
				logging.info(f"Database Schema Version: {version}")


