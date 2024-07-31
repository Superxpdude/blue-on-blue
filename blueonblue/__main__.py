#!/usr/bin/env python
import sys
import argparse
import pathlib
import os

from .bot import BlueOnBlueBot
from .log import setup_logging

import logging

REQUIRED_VERSION = (3,10,0,"final")

def get_token() -> str | None:
	"""Retrieves the discord bot token from a secret file or environment variable.

	Returns
	-------
	str | None
		Bot token if found, otherwise None
	"""
	token: str | None = None
	filepath = pathlib.Path("./discord_token")
	if filepath.is_file():
		# File exists. Read the file to get the token.
		with open(filepath) as file:
			token = file.read()
	else:
		# File does not exist. Read the environment variable.
		# Only try to read the environment variable if it actually exists
		if "DISCORD_TOKEN" in os.environ:
			token = os.environ["DISCORD_TOKEN"]

	return token


def main():
	# Argument setup
	parser = argparse.ArgumentParser()
	parser.add_argument('-d','--debug',action='store_true',dest="debug",help='Enable debug logging')
	args = parser.parse_args()

	# Check python version
	if (sys.version_info < REQUIRED_VERSION):
		print("Python 3.10.0 or higher is required to run this bot." \
		f"You are using version {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
		input("Press ENTER to continue...")
		exit()

	# Start the bot
	# Create required subfolders
	for f in ["config", "logs", "data"]:
		if not os.path.exists(f):
			os.makedirs(f)

	# Set up logging
	logLevel = logging.DEBUG if args.debug else logging.INFO
	setup_logging(level = logLevel)
	log = logging.getLogger("blueonblue")

	bot = BlueOnBlueBot()

	botToken = get_token()

	if botToken is None:
		logging.error("Unable to locate a Discord API token. Exiting.")
		exit()

	# Start the bot
	log.info("Starting Blue on Blue")
	bot.run(botToken, reconnect=True, log_handler = None)

if __name__ == "__main__":
	main()
