#!/usr/bin/env python
import argparse
import logging
import os
import pathlib

import discord

from .bot import BlueOnBlueBot
from .config import get_config_value
from .defines import GOOGLE_API_FILE
from .log import setup_logging

import importlib.resources
import json
import sqlite3

_log = logging.getLogger("blueonblue")


def migrate_db():
	# Read the database manifest file
	manifest = json.loads(importlib.resources.files("blueonblue.sql").joinpath("database.json").read_text())
	connection = sqlite3.connect("data/blueonblue.sqlite3")  # Creates the database if it doesn't exist already
	connection.row_factory = sqlite3.Row
	connection.execute("PRAGMA journal_mode = wal")
	connection.execute("PRAGMA foreign_keys = 1")
	cursor = connection.cursor()

	schema_version = cursor.execute("PRAGMA user_version").fetchone()["user_version"]
	_log.debug(f"Database version: {schema_version}")
	if str(schema_version) in manifest:
		while str(schema_version) in manifest:
			# If the schema has an migration defined. Apply it.
			fileName = manifest[str(schema_version)]
			_log.info(f"Applying database migration: {fileName}")
			sql = importlib.resources.files("blueonblue.sql").joinpath(fileName).read_text()
			cursor.executescript(sql)
			schema_version = cursor.execute("PRAGMA user_version").fetchone()["user_version"]
		# Commit the changes to the database
		connection.commit()
		_log.info("Database migrations complete")
		_log.info(f"New database version: {schema_version}")
	else:
		_log.info("No database migrations to apply")

	connection.close()


def main():
	# Argument setup
	parser = argparse.ArgumentParser()
	parser.add_argument("-d", "--debug", action="store_true", dest="debug", help="Enable debug logging")
	args = parser.parse_args()

	# Start the bot
	# Create required subfolders
	for f in ["data", "data/logs"]:
		if not os.path.exists(f):
			os.makedirs(f)

	# Disable PyNaCL warning
	discord.VoiceClient.warn_nacl = False

	# Set up logging
	logLevel = logging.DEBUG if (args.debug or get_config_value("DEBUG_LOGGING") is not None) else logging.INFO
	setup_logging(level=logLevel)
	_log.info("Initializing Blue on Blue")

	# Apply database migrations if necessary
	migrate_db()

	bot = BlueOnBlueBot()

	botToken = get_config_value("DISCORD_TOKEN")

	if botToken is None:
		_log.error("Unable to locate a Discord API token. Exiting.")
		exit()

	if not pathlib.Path(GOOGLE_API_FILE).is_file():
		_log.error("Unable to locate Google API data file. Exiting.")
		exit()

	# Start the bot
	_log.info("Starting Blue on Blue")
	bot.run(botToken, reconnect=True, log_handler=None)


if __name__ == "__main__":
	main()
