import asqlite

from typing import (
	Optional,
	Type,
)

from types import TracebackType

import logging
_log = logging.getLogger(__name__)

__all__ = [
	"DB",
	"DBConnection"
]

DBVERSION = 2

class DBConnection():
	"""BlueonBlue database connection class.

	Used to manage a custom asqlite connection context manager so that the database file only needs to be defined once."""
	connection: asqlite.Connection

	def __init__(self, dbFile: str):
		self._dbFile = dbFile

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


class DB():
	"""Database class to initialize a connection to the bot's database

	Only to be used in an async context manager"""
	connection: asqlite.Connection

	def __init__(self, dbFile: str):
		self._dbFile = dbFile

	def connect(self) -> DBConnection:
		return DBConnection(self._dbFile)

	# WIP. Will Write migration code in here for future versions
	async def migrate_version(self) -> None:
		"""Migrates the database to the latest schema version.

		Does nothing if the database is already up to date.
		"""
		async with self.connect() as db:
			async with db.cursor() as cursor:
				schema_version = 0
				while schema_version != DBVERSION:
					schema_version = (await (await cursor.execute("PRAGMA user_version")).fetchone())["user_version"]
					_log.info(f"Database Schema Version: {schema_version}")

					# Database is newly created
					if schema_version == 0:
						_log.info("Initializing database")
						# Arma stats tables
						await cursor.execute("CREATE TABLE if NOT EXISTS arma_stats_missions (\
							id INTEGER PRIMARY KEY \
							file_name TEXT NOT NULL,\
							start_time TEXT NOT NULL,\
							duration INTEGER NOT NULL)")

						await cursor.execute("CREATE TABLE if NOT EXISTS arma_stats_players (\
							mission_id INTEGER NOT NULL \
							steam_id INTEGER NOT NULL,\
							duration INTEGER NOT NULL,\
							UNIQUE(mission_id,steam_id),\
							FOREIGN KEY (mission_id) REFERENCES arma_stats_missions (id) ON DELETE CASCADE)")

						# Chat Filter table
						# "filterlist" value determines if the string is on the block list (0) or the allow list (1)
						await cursor.execute("CREATE TABLE if NOT EXISTS chatfilter (\
							server_id INTEGER NOT NULL,\
							filter_list INTEGER NOT NULL,\
							string TEXT NOT NULL,\
							UNIQUE(server_id,filter_list,string))")

						# Gold module table
						await cursor.execute("CREATE TABLE if NOT EXISTS gold (\
							server_id INTEGER NOT NULL,\
							user_id INTEGER NOT NULL,\
							expiry_time INTEGER,\
							UNIQUE(server_id,user_id))")

						# Jail module table
						await cursor.execute("CREATE TABLE if NOT EXISTS jail (\
							server_id INTEGER NOT NULL,\
							user_id INTEGER NOT NULL,\
							release_time INTEGER,\
							UNIQUE(server_id,user_id))")

						# Ping module tables
						await cursor.execute("CREATE TABLE if NOT EXISTS pings (\
							id INTEGER PRIMARY KEY AUTOINCREMENT,\
							server_id INTEGER NOT NULL,\
							ping_name TEXT NOT NULL,\
							last_used_time INTEGER,\
							alias_for INTEGER,\
							UNIQUE(server_id,ping_name),\
							FOREIGN KEY (alias_for) REFERENCES pings (id) ON DELETE CASCADE)")
						await cursor.execute("CREATE TABLE if NOT EXISTS ping_users (\
							server_id INTEGER NOT NULL,\
							ping_id INTEGER,\
							user_id INTEGER NOT NULL,\
							UNIQUE(server_id,ping_id,user_id),\
							FOREIGN KEY (ping_id) REFERENCES pings (id) ON DELETE CASCADE)")

						# Users module tables
						await cursor.execute("CREATE TABLE if NOT EXISTS users (\
							server_id INTEGER,\
							user_id INTEGER,\
							display_name TEXT,\
							name TEXT,\
							UNIQUE(server_id,user_id))")
						await cursor.execute("CREATE TABLE if NOT EXISTS user_roles (\
							server_id INTEGER,\
							user_id INTEGER,\
							role_id INTEGER,\
							UNIQUE(server_id,user_id,role_id),\
							FOREIGN KEY (role_id) REFERENCES roles (role_id) ON DELETE CASCADE)")
						await cursor.execute("CREATE TABLE if NOT EXISTS roles(\
							server_id INTEGER,\
							role_id INTEGER PRIMARY KEY,\
							name TEXT,\
							block_updates TEXT,\
							UNIQUE(server_id,role_id),\
							UNIQUE(server_id,block_updates))")

						# Verify module tables
						await cursor.execute("CREATE TABLE if NOT EXISTS verify (\
							discord_id INTEGER PRIMARY KEY,\
							steam64_id INTEGER UNIQUE)")

						await cursor.execute(f"PRAGMA user_version = {DBVERSION}")
						_log.info(f"Database initialized to version: {DBVERSION}")

						await db.commit()

					if schema_version == 1:
						_log.info("Upgrading database to version 2")
						# Chat Filter table
						# "filterlist" value determines if the string is on the block list (0) or the allow list (1)
						await cursor.execute("CREATE TABLE if NOT EXISTS arma_stats_missions (\
							id INTEGER PRIMARY KEY, \
							file_name TEXT NOT NULL,\
							start_time TEXT NOT NULL,\
							duration INTEGER NOT NULL)")

						await cursor.execute("CREATE TABLE if NOT EXISTS arma_stats_players (\
							mission_id INTEGER NOT NULL, \
							steam_id INTEGER NOT NULL,\
							duration INTEGER NOT NULL,\
							UNIQUE(mission_id,steam_id),\
							FOREIGN KEY (mission_id) REFERENCES arma_stats_missions (id) ON DELETE CASCADE)")

						await cursor.execute(f"PRAGMA user_version = 2")
						_log.info(f"Database upgraded to version: 2")

						await db.commit()

		# Database is on the correct version
		_log.info("Database initialization finished")
