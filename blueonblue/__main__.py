#!/usr/bin/env python
import sys
import argparse
import os

from .bot import BlueOnBlueBot
from .log import setup_logging

import logging

def main():
	# Argument setup
	parser = argparse.ArgumentParser()
	parser.add_argument('-d','--debug',action='store_true',dest="debug",help='Enable debug logging')
	args = parser.parse_args()

	# Check python version
	if (sys.version_info < (3,10,0,"final")):
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

	botToken = bot.config.bot_token

	if botToken is None:
		logging.error("No Discord API token found in config file.")
		print("The bot needs a Discord API token in order to run.")
		input("Press ENTER to continue...")
		exit()

	# Start the bot
	log.info("Starting Blue on Blue")
	bot.run(botToken, reconnect=True, log_handler = None)

if __name__ == "__main__":
	main()
