import logging

import blueonblue
import discord
from discord.ext import commands

_log = logging.getLogger(__name__)


class Users(commands.Cog, name="Users"):
	"""Base cog for user management"""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	@commands.Cog.listener()
	async def on_member_join(self, member: discord.Member):
		channel = await self.bot.serverConfig.channel_check_in.get(member.guild)
		if channel is not None:
			# Only continue if we have a valid check in channel
			await channel.send(f"Welcome to {member.guild.name} {member.mention}.")


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Users(bot))
