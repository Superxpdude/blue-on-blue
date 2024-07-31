# Blue on Blue command checks
import discord
from discord import app_commands

from typing import (
	Callable,
	TypeVar,
)

from blueonblue import bot as blueonbluebot

import logging
_log = logging.getLogger(__name__)

T = TypeVar("T")

# App command error classes
class UserUnauthorized(app_commands.AppCommandError):
	"""Command can only be used by specified users"""
	pass


class ChannelUnauthorized(app_commands.AppCommandError):
	"""Command can only be used in specified channels"""
	channels: tuple[int, ...]

	def __init__(self, *channels, **kwargs):
		super().__init__(**kwargs)
		self.channels = channels


class MissingServerConfigs(app_commands.AppCommandError):
	"""Command is missing server config options"""
	configs: tuple[str, ...]

	def __init__(self, *configs: str, **kwargs):
		super().__init__(**kwargs)
		self.configs = configs


def has_configs(*configs: str) -> Callable[[T], T]:
	"""Checks if a serverconfig exists for the given config value

	Also implicitly checks if the command was used in a guild or not."""
	async def predicate(interaction: discord.Interaction):
		assert isinstance(interaction.client, blueonbluebot.BlueOnBlueBot)
		bot = interaction.client
		if interaction.guild is None:
			raise app_commands.errors.NoPrivateMessage
		# Guild exists
		missing: list[str] = []
		for c in configs:
			if await bot.serverConfig.options[c].get(interaction.guild) is None:
				missing.append(c)

		if len(missing) > 0:
			raise MissingServerConfigs(*missing)
		# No errors
		return True

	return app_commands.check(predicate)
