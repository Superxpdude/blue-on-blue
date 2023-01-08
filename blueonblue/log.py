import discord
import logging
import logging.handlers

class _ColourFormatter(logging.Formatter):
	"""Logging formatter that injects ANSI colour codes into the logging stream.

	Taken almost entirely from discord.py's "utils" file.
	"""

	LEVEL_COLOURS = [
		(logging.DEBUG, '\x1b[40;1m'),
		(logging.INFO, '\x1b[34;1m'),
		(logging.WARNING, '\x1b[33;1m'),
		(logging.ERROR, '\x1b[31m'),
		(logging.CRITICAL, '\x1b[41m'),
	]

	FORMATS = {
		level: logging.Formatter(
			f"\x1b[30;1m%(asctime)s\x1b[0m {colour}[%(levelname)-8s]\x1b[0m \x1b[35m%(name)s\x1b[0m %(message)s",
			"%Y-%m-%d %H:%M:%S",
		)
		for level, colour in LEVEL_COLOURS
	}

	def format(self, record):
		formatter = self.FORMATS.get(record.levelno)
		if formatter is None:
			formatter = self.FORMATS[logging.DEBUG]

		# Override the traceback to always print in red
		if record.exc_info:
			text = formatter.formatException(record.exc_info)
			record.exc_text = f'\x1b[31m{text}\x1b[0m'

		output = formatter.format(record)

		# Remove the cache layer
		record.exc_text = None
		return output

def setup_logging(
	*,
	level: int = logging.INFO,
) -> None:
	"""Handles setting up logging for BlueonBlue

	Inspired heavily by the built-in logging capabilities for discord.py

	Parameters
	----------
	level : int, optional
		Logging level to use, by default logging.INFO
	"""

	logHandler = logging.handlers.TimedRotatingFileHandler("logs/blueonblue.log",when="midnight",backupCount=30)
	consoleHandler = logging.StreamHandler()

	logFormatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
	consoleFormatter = _ColourFormatter() if discord.utils.stream_supports_colour(consoleHandler) \
		else logging.Formatter("%(asctime)s [%(levelname)-8s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")

	logHandler.setFormatter(logFormatter)
	consoleHandler.setFormatter(consoleFormatter)

	log = logging.getLogger()

	log.addHandler(logHandler)
	log.addHandler(consoleHandler)

	log.setLevel(level)
