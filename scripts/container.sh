#!/bin/bash
# Container entry point
echo "Blueonblue container starting..."

# Convert the command to lowercase
command=$(echo $1 | tr '[:upper:]' '[:lower:]')

case $command in
	"start")
		# Start the bot
		echo "Command: Start"
		exec python -m blueonblue
		;;

	*)
		echo "Command: Unknown"
		echo "Exiting"
		;;
esac
