# Start file for the blue-on-blue bot.
# Version check
import sys
import argparse
import subprocess

# Handle the argument to skip the launch menu
parser = argparse.ArgumentParser()
parser.add_argument('-s','--start',action='store_true',dest="start",help='Run the bot immediately')
parser.add_argument('-d','--debug',action='store_true',dest="debug",help='Enable debug logging')
parser.add_argument('-i','--install',action='store_true',dest='install',help="Install the bot's dependencies")
args = parser.parse_args()

if sys.version_info < (3,7,0,'final'):
	print("Python 3.7.0 or higher is required to run this bot. " \
	"You are using version %s.%s.%s." % (sys.version_info.major, \
	sys.version_info.minor, sys.version_info.micro))
	input("Press ENTER to continue...")
	exit()

# Function to print the launch menu
def print_menu():
	print(23 * "-","BLUE ON BLUE", 23 * "-")
	print("1. Start Blue On Blue")
	print("2. Install dependencies")
	print("3. Exit")
	print(60 * "-")

def install_dependencies():
	subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

if args.install:
	install_dependencies()
	exit()

# If the start argument was not passed, run the menu
if not args.start:
	while True:
		print_menu()
		menu_choice = input("Enter your choice [1-3]: ")
		
		if menu_choice == "1": # Start bot
			break
		elif menu_choice == "2": # Install dependencies
			install_dependencies()
		elif menu_choice == "3": # Exit
			exit()
		else:
			input("Invalid option. Press ENTER to try again")



import os

# Create required subfolders
folders = ["logs", "config", "db", "temp"]
for f in folders:
	if not os.path.exists(f):
		os.makedirs(f)
	
# Set up logging
import logging
from logging import handlers
	
loglevel = logging.DEBUG if args.debug else logging.INFO

# Configure bot logging
rootLogger = logging.getLogger()
logFormat = logging.Formatter("%(asctime)s [%(levelname)s]  %(message)s")

logFile = handlers.TimedRotatingFileHandler("logs/blueonblue.log",when="midnight",backupCount=30)
logFile.setFormatter(logFormat)
rootLogger.addHandler(logFile)

log = logging.getLogger("blueonblue")
logConsole = logging.StreamHandler(sys.stdout)
logConsole.setFormatter(logFormat)
log.addHandler(logConsole)

log.setLevel(logging.DEBUG if args.debug else logging.INFO)

import discord

# Configure discord logging
discordLog = logging.getLogger("discord")
discordLog.setLevel(logging.WARNING)


from blueonblue.config import config_init
config_init()
from blueonblue.config import config

bot_token = config["BOT"]["TOKEN"]
if bot_token is None:
	logging.error("No Discord API token found in config file.")
	print("The bot needs a Discord API token in order to run.")
	input("Press ENTER to continue...")
	exit()

log.info("Starting Blue on Blue")
from blueonblue.bot import bot
from blueonblue.events import init_events

init_events(bot)
bot.run(bot_token, bot=True, reconnect=True)

log.info("Closing Blue on Blue")