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


def main():
	# Argument setup
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"-d", "--debug", action="store_true", dest="debug", help="Enable debug logging"
	)
	args = parser.parse_args()

	# Start the bot
	# Create required subfolders
	for f in ["data", "data/logs"]:
		if not os.path.exists(f):
			os.makedirs(f)

	# Disable PyNaCL warning
	discord.VoiceClient.warn_nacl = False

	# Set up logging
	logLevel = logging.DEBUG if args.debug else logging.INFO
	setup_logging(level=logLevel)
	log = logging.getLogger("blueonblue")

	bot = BlueOnBlueBot()

	botToken = get_config_value("DISCORD_TOKEN")

	if botToken is None:
		log.error("Unable to locate a Discord API token. Exiting.")
		exit()

	if not pathlib.Path(GOOGLE_API_FILE).is_file():
		log.error("Unable to locate Google API data file. Exiting.")
		exit()

	# Start the bot
	log.info("Starting Blue on Blue")
	bot.run(botToken, reconnect=True, log_handler=None)


if __name__ == "__main__":
	main()
