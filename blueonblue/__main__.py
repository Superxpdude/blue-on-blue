#!/usr/bin/env python
import sys
import argparse
import os

from .bot import BlueOnBlueBot
from .config import get_config_value
from .log import setup_logging

import logging

REQUIRED_VERSION = (3,10,0,"final")

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

	botToken = get_config_value("DISCORD_TOKEN")

	if botToken is None:
		logging.error("Unable to locate a Discord API token. Exiting.")
		exit()

	# Start the bot
	log.info("Starting Blue on Blue")
	bot.run(botToken, reconnect=True, log_handler = None)

if __name__ == "__main__":
	main()
