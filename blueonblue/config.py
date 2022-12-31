import tomlkit
from tomlkit import items

import logging
log = logging.getLogger(__name__)

__all__ = [
	"BotConfig"
]

class BotConfig:
	"""Config abstraction class

	Abstracts the base config storage away from other modules.
	Handles converting toml-compatible types to the types required for actual execution."""
	def __init__(self, configFile: str):
		# Read our existing config file
		with open(configFile, "r") as file:
			log.debug(f"Reading config file: {configFile}")
			self.toml = tomlkit.parse(file.read())

		# Set default values for our parameters
		self.toml.setdefault("prefix", "$$")
		self.toml.setdefault("bot_token", "")
		self.toml.setdefault("debug_server", -1)
		self.toml.setdefault("steam_api_token", "")
		self.toml.setdefault("google_api_file", "data/google_api.json")

		# Write any missing values back to the config file
		with open(configFile, "w") as file:
			file.write(tomlkit.dumps(self.toml))

	@property
	def prefix(self) -> str:
		return str(self.toml["prefix"])

	@property
	def bot_token(self) -> str:
		return str(self.toml["bot_token"])

	@property
	def debug_server(self) -> int:
		value = self.toml["debug_server"]
		assert isinstance(value, items.Integer)
		return int(value)

	@property
	def steam_api_token(self) -> str:
		return str(self.toml["steam_api_token"])

	@property
	def google_api_file(self) -> str:
		return str(self.toml["google_api_file"])
