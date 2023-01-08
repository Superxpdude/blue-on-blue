:: This batch file handles running the bot in a python virtual environment
@echo off
echo Loading virtual environment
if NOT exist venv\pyvenv.cfg (
	echo Virtual environment not found
	echo Please run install.bat to configure the virtual environment
	echo Press enter to continue
	pause
	exit /b
)
echo Loading bot
cmd /c venv\scripts\activate.bat ^
& python -m blueonblue -s
pause
