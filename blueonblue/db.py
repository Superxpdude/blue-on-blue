import asqlite
from . import dbtables

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

DBVERSION = 6

class DBConnection():
	"""BlueonBlue database connection class.

	Used to manage a custom asqlite connection context manager so that the database file only needs to be defined once."""
	connection: asqlite.Connection

	def __init__(self, dbFile: str):
		self._dbFile = dbFile

		# Initialize tables
		self.raffleWeight = dbtables.RaffleWeights(self)
		self.raffle = dbtables.Raffles(self)
		self.pings = dbtables.Pings(self)

	async def commit(self) -> None:
		"""Convenience function to commit changes on the connection
		"""
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
			async with db.connection.cursor() as cursor:
				schema_version = 0
				while schema_version != DBVERSION:
					schema_version = (await (await cursor.execute("PRAGMA user_version")).fetchone())["user_version"]
					_log.info(f"Database Schema Version: {schema_version}")

					# Database is newly created
					if schema_version == 0:
						_log.info("Initializing database")
						# Arma stats tables
						await cursor.execute("CREATE TABLE if NOT EXISTS arma_stats_missions (\
							id INTEGER PRIMARY KEY AUTOINCREMENT,\
							server_id INTEGER NOT NULL,\
							api_id INTEGER NOT NULL,\
							file_name TEXT NOT NULL,\
							start_time TEXT NOT NULL,\
							end_time TEXT NOT NULL,\
							main_op INTEGER,\
							UNIQUE(server_id,api_id))")

						await cursor.execute("CREATE TABLE if NOT EXISTS arma_stats_players (\
							mission_id INTEGER NOT NULL, \
							steam_id INTEGER NOT NULL,\
							duration REAL NOT NULL,\
							UNIQUE(mission_id,steam_id),\
							FOREIGN KEY (mission_id) REFERENCES arma_stats_missions (id) ON DELETE CASCADE)")

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

						# Arma stats view
						await cursor.execute("CREATE VIEW mission_attendance_view AS\
							SELECT\
								m.id,\
								m.main_op,\
								m.server_id,\
								m.api_id,\
								m.file_name,\
								u.display_name,\
								u.user_id as discord_id,\
								v.steam64_id,\
								m.start_time,\
								((julianday(m.end_time) - julianday(m.start_time)) * 1440)AS mission_duration,\
								p.duration as player_session,\
								(SELECT COUNT(*) FROM arma_stats_players pp WHERE pp.mission_id = m.id) as user_attendance\
							FROM arma_stats_missions m\
								INNER JOIN arma_stats_players p on p.mission_id = m.id\
								INNER JOIN verify v on v.steam64_id = p.steam_id\
								INNER JOIN users u on v.discord_id = u.user_id AND m.server_id = u.server_id")

						# Serverconfig table
						await cursor.execute("CREATE TABLE if NOT EXISTS serverconfig (\
							server_id INTEGER,\
							setting TEXT,\
							value TEXT,\
							UNIQUE(server_id, setting))")

						# Raffle weights table
						await cursor.execute("CREATE TABLE if NOT EXISTS raffle_weights (\
							server_id INTEGER NOT NULL,\
							user_id INTEGER NOT NULL,\
							weight NUMERIC NOT NULL,\
							UNIQUE(server_id, user_id))")

						# Raffle groups table
						await cursor.execute("CREATE TABLE if NOT EXISTS raffle_groups (\
							id INTEGER PRIMARY KEY AUTOINCREMENT,\
							server_id INTEGER NOT NULL,\
							end_time TEXT NOT NULL,\
							exclusive INTEGER NOT NULL,\
							weighted INTEGER NOT NULL,\
							message_id INT)")

						# Raffle data table
						await cursor.execute("CREATE TABLE if NOT EXISTS raffle_data (\
							id INTEGER PRIMARY KEY AUTOINCREMENT,\
							group_id INTEGER NOT NULL,\
							title TEXT NOT NULL,\
							winners INTEGER NOT NULL,\
							FOREIGN KEY (group_id) REFERENCES raffle_groups (id) ON DELETE CASCADE)")

						# Raffle users table
						await cursor.execute("CREATE TABLE if NOT EXISTS raffle_users (\
							raffle_id INTEGER NOT NULL,\
							discord_id INTEGER NOT NULL,\
							FOREIGN KEY (raffle_id) REFERENCES raffle_data (id) ON DELETE CASCADE)")

						await cursor.execute(f"PRAGMA user_version = {DBVERSION}")
						_log.info(f"Database initialized to version: {DBVERSION}")

						await db.commit()

					if schema_version == 1:
						_log.info("Upgrading database to version 2")
						# Arma stats tables
						await cursor.execute("CREATE TABLE if NOT EXISTS arma_stats_missions (\
							id INTEGER PRIMARY KEY AUTOINCREMENT,\
							server_id INTEGER NOT NULL,\
							api_id INTEGER NOT NULL,\
							file_name TEXT NOT NULL,\
							start_time TEXT NOT NULL,\
							end_time TEXT NOT NULL,\
							main_op INTEGER,\
							UNIQUE(server_id,api_id))")

						await cursor.execute("CREATE TABLE if NOT EXISTS arma_stats_players (\
							mission_id INTEGER NOT NULL, \
							steam_id INTEGER NOT NULL,\
							duration REAL NOT NULL,\
							UNIQUE(mission_id,steam_id),\
							FOREIGN KEY (mission_id) REFERENCES arma_stats_missions (id) ON DELETE CASCADE)")

						# Arma stats view
						await cursor.execute("CREATE VIEW mission_attendance_view AS\
							SELECT\
								m.id,\
								m.main_op,\
								m.server_id,\
								m.api_id,\
								m.file_name,\
								u.display_name,\
								u.user_id as discord_id,\
								v.steam64_id,\
								((julianday(m.end_time) - julianday(m.start_time)) * 1440) as mission_duration,\
								p.duration as player_session,\
								(SELECT COUNT(*) FROM arma_stats_players pp WHERE pp.mission_id = m.id) as user_attendance\
							FROM arma_stats_missions m\
								INNER JOIN arma_stats_players p on p.mission_id = m.id\
								INNER JOIN verify v on v.steam64_id = p.steam_id\
								INNER JOIN users u on v.discord_id = u.user_id AND m.server_id = u.server_id")

						await cursor.execute("PRAGMA user_version = 2")
						_log.info("Database upgraded to version: 2")

						await db.commit()

					if schema_version == 2:
						_log.info("Upgrading database to version 3")

						# Serverconfig table
						await cursor.execute("CREATE TABLE if NOT EXISTS serverconfig (\
							server_id INTEGER,\
							setting TEXT,\
							value TEXT,\
							UNIQUE(server_id, setting))")

						await cursor.execute("PRAGMA user_version = 3")
						_log.info("Database upgraded to version: 3")

						await db.commit()

					if schema_version == 3:
						_log.info("Upgrading database to version 4")

						# Raffle weights table
						await cursor.execute("CREATE TABLE if NOT EXISTS raffle_weights (\
							server_id INTEGER NOT NULL,\
							user_id INTEGER NOT NULL,\
							weight NUMERIC NOT NULL,\
							UNIQUE(server_id, user_id))")

						# Remove chatfilter table
						await cursor.execute("DROP TABLE chatfilter")

						await cursor.execute("PRAGMA user_version = 4")
						_log.info("Database upgraded to version: 4")

						await db.commit()

					if schema_version == 4:
						_log.info("Upgrading database to version 5")

						# Arma stats view
						await cursor.execute("DROP VIEW mission_attendance_view")
						await cursor.execute("CREATE VIEW mission_attendance_view AS\
							SELECT\
								m.id,\
								m.main_op,\
								m.server_id,\
								m.api_id,\
								m.file_name,\
								u.display_name,\
								u.user_id as discord_id,\
								v.steam64_id,\
								m.start_time,\
								((julianday(m.end_time) - julianday(m.start_time)) * 1440)AS mission_duration,\
								p.duration as player_session,\
								(SELECT COUNT(*) FROM arma_stats_players pp WHERE pp.mission_id = m.id) as user_attendance\
							FROM arma_stats_missions m\
								INNER JOIN arma_stats_players p on p.mission_id = m.id\
								INNER JOIN verify v on v.steam64_id = p.steam_id\
								INNER JOIN users u on v.discord_id = u.user_id AND m.server_id = u.server_id")

						await cursor.execute("PRAGMA user_version = 5")
						_log.info("Database upgraded to version: 5")

						await db.commit()

					if schema_version == 5:
						_log.info("Upgrading database to version 6")

						# Raffle groups table
						await cursor.execute("CREATE TABLE if NOT EXISTS raffle_groups (\
							id INTEGER PRIMARY KEY AUTOINCREMENT,\
							server_id INTEGER NOT NULL,\
							end_time TEXT NOT NULL,\
							exclusive INTEGER NOT NULL,\
							weighted INTEGER NOT NULL,\
							message_id INT)")

						# Raffle data table
						await cursor.execute("CREATE TABLE if NOT EXISTS raffle_data (\
							id INTEGER PRIMARY KEY AUTOINCREMENT,\
							group_id INTEGER NOT NULL,\
							title TEXT NOT NULL,\
							winners INTEGER NOT NULL,\
							FOREIGN KEY (group_id) REFERENCES raffle_groups (id) ON DELETE CASCADE)")

						# Raffle users table
						await cursor.execute("CREATE TABLE if NOT EXISTS raffle_users (\
							raffle_id INTEGER NOT NULL,\
							discord_id INTEGER NOT NULL,\
							FOREIGN KEY (raffle_id) REFERENCES raffle_data (id) ON DELETE CASCADE)")

						await cursor.execute("PRAGMA user_version = 6")
						_log.info("Database upgraded to version: 6")

						await db.commit()

		# Database is on the correct version
		_log.info("Database initialization finished")
