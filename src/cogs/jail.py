import logging
from datetime import timedelta
from typing import Literal

import blueonblue
import discord
from blueonblue.defines import (
	SCONF_CHANNEL_MOD_ACTIVITY,
	SCONF_ROLE_TIMEOUT,
	TIMEOUT_EMBED_COLOUR,
)
from discord import app_commands
from discord.ext import commands, tasks

_log = logging.getLogger(__name__)


@app_commands.guild_only()
@app_commands.default_permissions(manage_messages=True)
class Jail(commands.Cog, name="Jail"):
	"""Jail commands"""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	async def cog_load(self):
		self.timeout_role_loop.start()

	async def cog_unload(self):
		self.timeout_role_loop.stop()

	@app_commands.command(name="jail")
	@app_commands.describe(
		user="User to be jailed",
		time="Time duration for jail. Default unit is days",
		time_unit="Unit of measurement for the " "time" " parameter",
	)
	@blueonblue.checks.has_configs(SCONF_CHANNEL_MOD_ACTIVITY, SCONF_ROLE_TIMEOUT)
	async def jail(
		self,
		interaction: discord.Interaction,
		user: discord.Member,
		time: float,
		time_unit: Literal["minutes", "hours", "days", "weeks"] = "days",
	):
		"""Jails a user"""
		assert interaction.guild is not None

		modChannel = await self.bot.serverConfig.channel_mod_activity.get(interaction.guild)
		assert modChannel is not None
		# Timeout role doesn't do anything until I can figure out a good way to remove the
		# role on timeout expiry
		# timeoutRole = await self.bot.serverConfig.role_timeout.get(interaction.guild)
		# assert timeoutRole is not None

		# Get our timedelta
		if time_unit == "minutes":
			timeDelta = timedelta(minutes=time)
		elif time_unit == "hours":
			timeDelta = timedelta(hours=time)
		elif time_unit == "weeks":
			timeDelta = timedelta(weeks=time)
		else:  # Days
			timeDelta = timedelta(days=time)

		if timeDelta > timedelta(weeks=4):
			await interaction.response.send_message(
				"Timeouts greater than 28 days are not supported by Discord.", ephemeral=True, delete_after=30
			)
			return

		# Now that we have our timedelta, find the release time
		releaseTimeStamp = round((discord.utils.utcnow() + timeDelta).timestamp())

		# Create a "time text"
		timeText = int(time) if time == int(time) else time

		# Build our embed and view
		view = blueonblue.views.ConfirmViewDanger(interaction.user, confirm="Jail")
		jailEmbed = discord.Embed(
			title=f"User to be jailed for `{timeText} {time_unit}` until",
			description=f"<t:{releaseTimeStamp}:F>",
			colour=TIMEOUT_EMBED_COLOUR,
		)
		jailEmbed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
		await interaction.response.send_message(
			f"{interaction.user.mention}, you are about to jail the following user.",
			view=view,
			embed=jailEmbed,
		)
		view.message = await interaction.original_response()
		# Wait for the view to finish
		await view.wait()

		# Once we have a response, continue
		if view.response:
			# Action confirmed. Jail the user
			try:
				await user.timeout(timeDelta, reason=f"User timed out by {interaction.user.display_name}")
				timeoutRole = await self.bot.serverConfig.role_timeout.get(interaction.guild)
				if timeoutRole is not None:
					await user.add_roles(timeoutRole, reason=f"User timed out by {interaction.user.display_name}")
				await modChannel.send(
					f"User {user.mention} has been jailed by {interaction.user.mention} for {timeText} {time_unit}.",
					allowed_mentions=discord.AllowedMentions.none(),
				)
			except discord.Forbidden:
				await interaction.followup.send("Error applying timeout. Insufficient permissions.")
		elif not view.response:
			# Action cancelled
			await interaction.followup.send("Jail action cancelled.")
		else:
			# Notify the user that the action timed out
			await interaction.followup.send("Pending jail action has timed out", ephemeral=True)

	@tasks.loop(minutes=1)
	async def timeout_role_loop(self):
		"""Loop to periodically clear the timeout role from users who are no longer timed out."""
		# Iterate through all guilds
		for guild in self.bot.guilds:
			timeoutRole = await self.bot.serverConfig.role_timeout.get(guild)
			# If the timeout role is defined. Check for all members with the role.
			if timeoutRole is not None:
				modChannel = await self.bot.serverConfig.channel_mod_activity.get(guild)
				for member in timeoutRole.members:
					# If the member is not timed out. Remove the role from them.
					if not member.is_timed_out():
						try:
							await member.remove_roles(timeoutRole, reason="Timeout expired")
							if modChannel is not None:
								await modChannel.send(
									f"Timeout expired for user {member.mention}.",
									allowed_mentions=discord.AllowedMentions.none(),
								)
						except discord.Forbidden:
							if modChannel is not None:
								await modChannel.send(
									f"Error removing role {timeoutRole.mention} from user {member.mention} on timeout expiry.",
									allowed_mentions=discord.AllowedMentions.none(),
								)


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Jail(bot))
