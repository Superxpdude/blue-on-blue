#!/usr/bin/env python
import sys
import argparse
import subprocess
import os
import asyncio

import logging
import logging.handlers

def install_dependencies():
	subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

# Argument setup
parser = argparse.ArgumentParser()
parser.add_argument('-s','--start',action='store_true',dest="start",help='Run the bot immediately')
parser.add_argument('-d','--debug',action='store_true',dest="debug",help='Enable debug logging')
parser.add_argument('-i','--install',action='store_true',dest='install',help="Install the bot's dependencies")
args = parser.parse_args()

# Check python version
if (sys.version_info < (3,8,0,"final")):
	print("Python 3.8.0 or higher is required to run this bot." \
	f"You are using version {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
	input("Press ENTER to continue...")
	exit()

# If the installation argument is set. Install dependencies and exit.
if args.install:
	install_dependencies()
	exit()

# If the start argument was not passed, run the menu
if not args.start:
	while True:
		print(23 * "-","BLUE ON BLUE", 23 * "-")
		print("1. Start Blue On Blue")
		print("2. Install dependencies")
		print("3. Exit")
		print(60 * "-")
		menu_choice = input("Enter your choice [1-3]: ")

		if menu_choice == "1": # Start bot
			break
		elif menu_choice == "2": # Install dependencies
			install_dependencies()
		elif menu_choice == "3": # Exit
			exit()
		else:
			input("Invalid option. Press ENTER to try again")

# Create required subfolders
for f in ["config", "logs", "data", "temp"]:
	if not os.path.exists(f):
		os.makedirs(f)

# Set up logging
logLevel = logging.DEBUG if args.debug else logging.INFO

rootLog = logging.getLogger()
logFormat = logging.Formatter("%(asctime)s [%(levelname)s]  %(message)s")
logFile = logging.handlers.TimedRotatingFileHandler("logs/blueonblue.log",when="midnight",backupCount=30)
logFile.setFormatter(logFormat)
rootLog.addHandler(logFile)

log = logging.getLogger("blueonblue")
logConsole = logging.StreamHandler(sys.stdout)
logConsole.setFormatter(logFormat)
log.addHandler(logConsole)

log.setLevel(logLevel)

# Discord logging
discordLog = logging.getLogger("discord")
discordLog.setLevel(logging.WARNING)

# Don't import blueonblue until logging is configured
from blueonblue import bot

botToken = bot.config["CORE"].get("bot_token")

if botToken is None:
	logging.error("No Discord API token found in config file.")
	print("The bot needs a Discord API token in order to run.")
	input("Press ENTER to continue...")
	exit()

log.info("Starting Blue on Blue")

#bot.bot.run(botToken, reconnect=True)
asyncio.run(bot.blueonblue_start())
