import discord
from discord import app_commands
from discord.ext import commands, tasks

import blueonblue

import logging
_log = logging.getLogger(__name__)

class ArmaStats(commands.GroupCog, group_name="armastats"):
	"""Arma Stats commands."""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	@app_commands.command(name = "me")
	async def me(self, interaction: discord.Interaction):
		return

async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(ArmaStats(bot))
