import logging
from datetime import datetime, timedelta, timezone

import blueonblue
import discord
import parsedatetime
from discord import app_commands
from discord.ext import commands

_log = logging.getLogger(__name__)


class Utils(commands.GroupCog, group_name="utils"):
	"""Utility commands"""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	@app_commands.command(name="timestamp")
	@app_commands.rename(tzoffset="timezone")
	async def timestamp(
		self,
		interaction: discord.Interaction,
		time: str,
		tzoffset: app_commands.Range[int, -12, 12],
	):
		"""Generates Discord timestamp texts from a provided date and time.

		Parameters
		----------
		time : str
			Date/Time in human format
		tzoffset : int
			UTC offset of your timezone. Defaults to zero (UTC time)
		"""

		# Set up parsedatetime
		cal = parsedatetime.Calendar()
		parsedDate = cal.parse(time)[0]

		# Set up our timezone
		tz = timezone(timedelta(hours=tzoffset))

		# Create our datetime object
		dt = datetime(*parsedDate[:6], tzinfo=tz)

		# Send our response
		await interaction.response.send_message(
			f"{discord.utils.format_dt(dt, 't')}: `{discord.utils.format_dt(dt, 't')}`\n"
			f"{discord.utils.format_dt(dt, 'T')}: `{discord.utils.format_dt(dt, 'T')}`\n"
			f"{discord.utils.format_dt(dt, 'd')}: `{discord.utils.format_dt(dt, 'd')}`\n"
			f"{discord.utils.format_dt(dt, 'D')}: `{discord.utils.format_dt(dt, 'D')}`\n"
			f"{discord.utils.format_dt(dt, 'f')}: `{discord.utils.format_dt(dt, 'f')}`\n"
			f"{discord.utils.format_dt(dt, 'F')}: `{discord.utils.format_dt(dt, 'F')}`\n"
			f"{discord.utils.format_dt(dt, 'R')}: `{discord.utils.format_dt(dt, 'R')}`",
			ephemeral=True,
		)


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Utils(bot))
