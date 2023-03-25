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
	channels: tuple[int]

	def __init__(self, *channels, **kwargs):
		super().__init__(**kwargs)
		self.channels = channels


# App command check functions
def in_guild() -> Callable[[T], T]:
	"""Checks if the command was used in a guild"""
	async def predicate(interaction: discord.Interaction):
		if interaction.guild is not None:
			return True
		else:
			raise app_commands.errors.NoPrivateMessage

	return app_commands.check(predicate)


def in_channel_bot() -> Callable[[T], T]:
	"""Checks if the command was used in the specified bot channel"""
	async def predicate(interaction: discord.Interaction):
		assert isinstance(interaction.client, blueonbluebot.BlueOnBlueBot)
		assert isinstance(interaction.user, discord.Member)
		bot: blueonbluebot.BlueOnBlueBot = interaction.client
		# Check if the command was executed in a server or not
		if interaction.guild is not None:
			# Command was used in a server
			assert isinstance(interaction.channel, discord.abc.GuildChannel)
			botChannel = await bot.serverConfig.channel_bot.get(interaction.guild)
			if (botChannel is not None) and (interaction.channel.id == botChannel.id):
				# Used in bot channel
				return True
			else:
				# Not in bot channel
				if botChannel is not None:
					raise ChannelUnauthorized(botChannel.id)
				else:
					raise ChannelUnauthorized()
		else:
			# Not used in guild
			# For this, we don't specifically care if it was used in a DM or not. If it shouldn't be used in DMs, a "in_guild" check should be done as well.
			return True

	return app_commands.check(predicate)
