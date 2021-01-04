:: This batch file handles running the bot in a python virtual environment
@echo off
echo Loading virtual environment
if NOT exist pyvenv.cfg (
	echo Virtual environment not found
	echo Please run install.bat to configure the virtual environment
	echo Press enter to continue
	pause
	exit /b
)
echo Loading bot
cmd /c scripts\activate.bat & python start.py -s
pause