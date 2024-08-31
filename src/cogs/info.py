import logging
import importlib.metadata
import os

import discord
from discord import app_commands
from discord.ext import commands

import blueonblue

_log = logging.getLogger(__name__)


class Info(commands.Cog, name="Info"):
	"""Commands that provide info about the bot."""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	@app_commands.command(name="info")
	async def info(self, interaction: discord.Interaction):
		"""Displays information about the bot."""
		assert interaction.client.user is not None

		embed = discord.Embed(
			title="BlueonBlue", url="https://github.com/Superxpdude/blue-on-blue", description="A Discord bot for TMTM"
		)
		embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
		embed.add_field(name="Authors", value="<@96018174163570688>\n<@134830326789832704>", inline=False)

		# Add the bot version if present
		try:
			packageVersion = importlib.metadata.version("blueonblue")
			version = f"[{packageVersion}](https://github.com/Superxpdude/blue-on-blue/releases/tag/v{packageVersion})"
			embed.add_field(name="Version", value=version, inline=True)
		except importlib.metadata.PackageNotFoundError:
			_log.warning("Unable to locate version for BlueonBlue package in info command.")
			pass

		# Add the revision if present
		if "COMMIT" in os.environ:
			revision = os.environ["COMMIT"]
			embed.add_field(
				name="Revision", value=f"[{revision:7.7}](https://github.com/Superxpdude/blue-on-blue/commit/{revision})"
			)

		await interaction.response.send_message(embed=embed)


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Info(bot))
