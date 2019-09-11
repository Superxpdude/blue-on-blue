# Start file for the blue-on-blue bot.
# Version check
import sys
import argparse
import subprocess

# Handle the argument to skip the launch menu
parser = argparse.ArgumentParser()
parser.add_argument('-s','--start',action='store_true',help='Run the bot immediately')
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

# If the start argument was not passed, run the menu
if not args.start:
	while True:
		print_menu()
		menu_choice = input("Enter your choice [1-3]: ")
		
		if menu_choice == "1": # Start bot
			break
		elif menu_choice == "2": # Install dependencies
			subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
		elif menu_choice == "3": # Exit
			exit()
		else:
			input("Invalid option. Press ENTER to try again")

from blueonblue.bot import bot
from blueonblue.bot import bot_token
from blueonblue.events import init_events

init_events(bot)
bot.run(bot_token, bot=True, reconnect=True)