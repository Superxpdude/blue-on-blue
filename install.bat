:: This batch file will handle installing the bot
:: This will create a Virtual Environment, Activate it, and install the bot's prerequisites
@echo off

echo.
echo		You are about to install Blue on Blue
echo		Close this window to abort the install
echo.
echo		Press enter to continue
echo.
echo -----------------------------------------------------
pause
echo Creating virtual environment
if exist pyvenv.cfg (
	echo Virtual Environment Exists. Skipping...
) else (
	python -m venv ./
	echo Virtual Environment Created
)
echo Installing dependencies
cmd /c scripts\activate.bat & python start.py -i
echo Blue on Blue is now installed
echo Press enter to close
pause