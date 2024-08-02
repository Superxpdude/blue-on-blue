import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Literal

import blueonblue
import discord
from blueonblue.defines import (
	GOLD_EMBED_COLOUR,
	SCONF_CHANNEL_MOD_ACTIVITY,
	SCONF_ROLE_GOLD,
)
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
	import sqlite3

import logging

_log = logging.getLogger(__name__)


# All timer-related code in this module is heavily inspired by the reminder system in RoboDanny
# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/reminder.py
class Timer:
	def __init__(self, record: "sqlite3.Row"):
		self.guildID: int = record["server_id"]
		self.userID: int = record["user_id"]
		self.expiry = datetime.fromtimestamp(record["expiry_time"], tz=UTC)

	def __eq__(self, other: object) -> bool:
		try:
			assert isinstance(other, Timer)
			return (self.guildID == other.guildID) and (self.userID == other.userID) and (self.expiry == other.expiry)
		except (AttributeError, AssertionError):
			return False

	def __str__(self) -> str:
		return f"Gold Timer: Guild={self.guildID} User={self.userID} Expiry={self.expiry}"


@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class Gold(commands.GroupCog, group_name="gold"):
	"""Gold user functions"""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		self._current_timer: Timer | None = None
		self._has_timer = asyncio.Event()
		self._task = self.bot.loop.create_task(self.dispatch_timers(), name="Gold Timer")

	# async def cog_load(self):
	# 	await self.refresh_timer()

	async def cog_unload(self):
		self._task.cancel()

	async def wait_for_active_timer(self) -> Timer:
		_log.debug("Wait: Retrieving active timer from database")
		timer = await self.get_active_timer()
		_log.debug(f"Wait: Active Timer [{timer}]")
		if timer is not None:
			self._has_timer.set()
			return timer

		# If we didn't get a timer, clear the event flag and current timer variable
		self._has_timer.clear()
		self._current_timer = None
		await self._has_timer.wait()

		# If we reach this point, we will always have a valid timer
		return await self.get_active_timer()  # type: ignore

	async def refresh_timer(self) -> None:
		"""Refreshes the active timer. Restarts the dispatch task if necessary."""
		log = logging.getLogger(__name__ + ".refresh")
		log.debug("Refreshing gold timers")
		newTimer = await self.get_active_timer()
		log.debug(f"Old timer: {self._current_timer}")
		log.debug(f"New timer: {newTimer}")
		if newTimer != self._current_timer:
			log.debug("Gold timer changed. Updating current timer.")
			self._current_timer = newTimer
			self._task.cancel()
			# Only restart the task if we have a new timer to use
			if self._current_timer is not None:
				log.debug("Restarting gold timer task")
				self._task = self.bot.loop.create_task(self.dispatch_timers(), name="Gold Timer")
			else:
				log.debug("No active gold timers. Leaving task closed.")
		else:
			log.debug("Active timer unchanged")

	async def get_active_timer(self) -> Timer | None:
		# Retrieve the next active timer from the database
		async with self.bot.db.connect() as db:
			async with db.connection.cursor() as cursor:
				await cursor.execute("SELECT * FROM gold ORDER BY expiry_time ASC LIMIT 1")
				data = await cursor.fetchone()

		return Timer(data) if data is not None else None

	async def call_timer(self, timer: Timer) -> None:
		# Delete the record from the database
		_log.info(f"Calling gold timer: {timer}")
		async with self.bot.db.connect() as db:
			async with db.connection.cursor() as cursor:
				await cursor.execute(
					"DELETE FROM gold WHERE server_id = :server_id AND user_id = :user_id",
					{"server_id": timer.guildID, "user_id": timer.userID},
				)
				await db.commit()

		# Fire the timer event
		self.bot.dispatch("gold_timer_complete", timer)

	async def dispatch_timers(self) -> None:
		log = logging.getLogger(__name__ + ".dispatch")
		try:
			# Wait until the bot is ready
			await self.bot.wait_until_ready()
			while not self.bot.is_closed():
				# Asyncio sleep supposedly has issues when called
				# with very long delays. We'll use a shorter sleep
				# instead when dealing with those.
				log.debug("Starting loop")
				self._current_timer = await self.wait_for_active_timer()
				log.debug("Have valid timer")
				now = datetime.now(UTC)
				if self._current_timer.expiry > now:
					log.debug("Timer expiry in the future.")
					# Timer expiry is in the future. Wait for a while.
					to_sleep = min((self._current_timer.expiry - now).total_seconds(), 86400)
					log.debug(f"Sleeping dispatch task for {to_sleep} seconds")
					await asyncio.sleep(to_sleep)
				else:
					log.debug("Firing timer")
					# Fire the timer
					await self.call_timer(self._current_timer)
					# Grab the next timer
					self._current_timer = await self.get_active_timer()
					# If we don't have a new timer, exit the loop
					if self._current_timer is None:
						log.debug("No new timer. Exiting loop.")
						return

		except asyncio.CancelledError:
			# Raise the error on task cancel per asyncio documentation
			log.debug("Dispatch: Task cancelled")
			raise

		except (OSError, discord.ConnectionClosed) as e:
			# On other handled errors, cancel the task
			log.warning(f"Cancelling gold timer due to exception [{e}]")
			self._task.cancel()
			await self.refresh_timer()

	@commands.Cog.listener()
	async def on_gold_timer_complete(self, timer: Timer):
		# Try to get the guild and member objects
		try:
			guild = self.bot.get_guild(timer.guildID) or (await self.bot.fetch_guild(timer.guildID))
		except discord.HTTPException:
			# Unable to get the guild or the member.
			_log.debug(f"Gold timer unable to fetch guild [{timer.guildID}]")
			return
		try:
			member = guild.get_member(timer.userID) or (await guild.fetch_member(timer.userID))
		except discord.HTTPException:
			# Unable to get the guild or the member.
			_log.debug(f"Gold timer unable to fetch member [{timer.userID}] from guild [{timer.guildID}]")
			return

		_log.info(f"Removing TMTM gold for user [{member.name}|{member.id}] in guild [{guild.name}|{guild.id}]")
		# Get the mod channel and gold role
		modChannel = await self.bot.serverConfig.channel_mod_activity.get(guild)
		goldRole = await self.bot.serverConfig.role_gold.get(guild)

		if goldRole is not None:
			try:
				await member.remove_roles(goldRole, reason="TMTM gold expired")
				if modChannel is not None:
					await modChannel.send(
						f"TMTM Gold has expired for user {member.mention}.",
						allowed_mentions=discord.AllowedMentions.none(),
					)

			except discord.Forbidden:
				if modChannel is not None:
					await modChannel.send(
						f"Unable to remove expired TMTM gold from user {member.mention}. Insufficient permissions.",
						allowed_mentions=discord.AllowedMentions.none(),
					)

			except discord.HTTPException:
				if modChannel is not None:
					await modChannel.send(
						f"Unknown error encountered removing expired TMTM gold from user {member.mention}.",
						allowed_mentions=discord.AllowedMentions.none(),
					)
					_log.warning(
						f"Unknown error encountered removing expired TMTM gold from user [{member.name}|{member.id}] in guild [{guild.name}|{guild.id}].",
					)

	@app_commands.command(name="add")
	@app_commands.describe(
		user="User to be given TMTM gold.",
		time="Time duration for TMTM Gold. Default unit is days.",
		time_unit="Unit of measurement for " "time" " parameter.",
	)
	@blueonblue.checks.has_configs(SCONF_CHANNEL_MOD_ACTIVITY, SCONF_ROLE_GOLD)
	async def add(
		self,
		interaction: discord.Interaction,
		user: discord.Member,
		time: float,
		time_unit: Literal["minutes", "hours", "days", "weeks"] = "days",
	):
		"""Gives TMTM Gold to a user"""
		assert interaction.guild is not None

		modChannel = await self.bot.serverConfig.channel_mod_activity.get(interaction.guild)
		assert modChannel is not None
		goldRole = await self.bot.serverConfig.role_gold.get(interaction.guild)
		assert goldRole is not None

		# Start our DB block
		async with self.bot.db.connect() as db:
			async with db.connection.cursor() as cursor:
				# Get our timedelta
				if time_unit == "minutes":
					timeDelta = timedelta(minutes=time)
				elif time_unit == "hours":
					timeDelta = timedelta(hours=time)
				elif time_unit == "weeks":
					timeDelta = timedelta(weeks=time)
				else:  # Days
					timeDelta = timedelta(days=time)

				# Now that we have our timedelta, find the expiry time
				expiryTimeStamp = round((discord.utils.utcnow() + timeDelta).timestamp())

				# Create a "time text"
				timeText = int(time) if time == int(time) else time

				# Build our embed and view
				view = blueonblue.views.ConfirmView(interaction.user)
				goldEmbed = discord.Embed(
					title=f"Gold to be given for `{timeText} {time_unit}` until",
					description=f"<t:{expiryTimeStamp}:F>",
					colour=GOLD_EMBED_COLOUR,
				)
				goldEmbed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
				await interaction.response.send_message(
					f"{interaction.user.mention}, you are about to give TMTM Gold to the following user.",
					view=view,
					embed=goldEmbed,
				)
				view.message = await interaction.original_response()
				# Wait for the view to finish
				await view.wait()

				# Once we have a response, continue
				if view.response:
					# Action confirmed. Give gold to the user
					# Get the mod activity channel

					# We need to check if the user is already present in the gold DB
					await cursor.execute(
						"SELECT * FROM gold WHERE server_id = :serverID AND user_id = :userID",
						{"serverID": interaction.guild.id, "userID": user.id},
					)
					userData = await cursor.fetchone()
					if userData is None:
						# User not in gold DB
						# Add the "gold" role to the user

						goldReason = f"TMTM Gold given by {interaction.user.display_name} for {timeText} {time_unit}."
						try:
							assert goldRole is not None
							await user.add_roles(goldRole, reason=goldReason)
							await cursor.execute(
								"INSERT OR REPLACE INTO gold (server_id, user_id, expiry_time) VALUES \
							(:serverID, :userID, :expiryTime)",
								{
									"serverID": interaction.guild.id,
									"userID": user.id,
									"expiryTime": expiryTimeStamp,
								},
							)
							await interaction.followup.send(
								f"TMTM Gold has been given to {user.mention}.",
								ephemeral=True,
								allowed_mentions=discord.AllowedMentions.none(),
							)
							await modChannel.send(
								f"User {user.mention} has been given TMTM Gold by {interaction.user.mention} for {timeText} {time_unit}.",
								allowed_mentions=discord.AllowedMentions.none(),
							)
						except Exception:
							await interaction.followup.send("Failed to assign roles to gold user.")
					else:
						# User in gold DB. Only update expiry time.
						await cursor.execute(
							"UPDATE gold SET expiry_time = :expiryTime WHERE server_id = :serverID AND user_id = :userID",
							{
								"serverID": interaction.guild.id,
								"userID": user.id,
								"expiryTime": expiryTimeStamp,
							},
						)
						await interaction.followup.send(
							f"Updated expiry time for user {user.mention}.",
							ephemeral=True,
							allowed_mentions=discord.AllowedMentions.none(),
						)
						await modChannel.send(
							f"TMTM Gold for user {user.mention} has been modified by {interaction.user.mention} to {timeText} {time_unit}.",
							allowed_mentions=discord.AllowedMentions.none(),
						)

					# Commit changes to the DB
					await db.commit()

					# With the DB changes committed, we need to refresh the active timer
					await self.refresh_timer()
					# We also need to set the "has data" event
					self._has_timer.set()

				elif view.response is None:
					# Notify the user that the action timed out
					await interaction.followup.send("Pending TMTM Gold action has timed out", ephemeral=True)

				else:
					# Action cancelled
					await interaction.followup.send("TMTM Gold action cancelled")

	@app_commands.command(name="remove")
	@app_commands.describe(user="User to have TMTM Gold removed")
	@blueonblue.checks.has_configs(SCONF_CHANNEL_MOD_ACTIVITY, SCONF_ROLE_GOLD)
	async def remove(self, interaction: discord.Interaction, user: discord.Member):
		"""Removes TMTM Gold from a user"""
		assert interaction.guild is not None

		modChannel = await self.bot.serverConfig.channel_mod_activity.get(interaction.guild)
		assert modChannel is not None
		goldRole = await self.bot.serverConfig.role_gold.get(interaction.guild)
		assert goldRole is not None

		# Start our DB block
		async with self.bot.db.connect() as db:
			async with db.connection.cursor() as cursor:
				# Check if the user is already jailed
				await cursor.execute(
					"SELECT user_id, expiry_time FROM gold WHERE server_id = :serverID AND user_id = :userID",
					{"serverID": interaction.guild.id, "userID": user.id},
				)
				userData = await cursor.fetchone()
				if userData is None:
					# User not jailed
					await interaction.response.send_message(
						f"I could not find {user.mention} in the gold list.",
						ephemeral=True,
						allowed_mentions=discord.AllowedMentions.none(),
					)
					return

				expiryTimeStamp = userData["expiry_time"]

				# User present in gold table. Create our embed and message.
				view = blueonblue.views.ConfirmView(interaction.user)
				goldEmbed = discord.Embed(
					title="User has TMTM Gold until",
					description=f"<t:{expiryTimeStamp}:F>",
					colour=GOLD_EMBED_COLOUR,
				)
				goldEmbed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
				await interaction.response.send_message(
					f"{interaction.user.mention}, you are about to remove TMTM Gold from the following user.",
					view=view,
					embed=goldEmbed,
				)
				view.message = await interaction.original_response()
				# Wait for the view to finish
				await view.wait()

				# Once we have a response, continue
				if view.response:
					# Action confirmed. Remove gold.
					goldReason = f"TMTM Gold removed by {interaction.user.display_name}"
					# Remove the role from the user (if present)
					if goldRole in user.roles:
						await user.remove_roles(goldRole, reason=goldReason)
					await interaction.followup.send(
						f"TMTM gold removed for {user.mention}.",
						ephemeral=True,
						allowed_mentions=discord.AllowedMentions.none(),
					)
					await modChannel.send(
						f"User {user.mention} has had TMTM Gold removed by {interaction.user.mention}.",
						allowed_mentions=discord.AllowedMentions.none(),
					)
					# Remove the entry from the gold DB
					await cursor.execute(
						"DELETE FROM gold WHERE server_id = :serverID AND user_id = :userID",
						{"serverID": interaction.guild.id, "userID": user.id},
					)
					# Make sure that we remove the role reference from the users DB (if present)
					await cursor.execute(
						"DELETE FROM user_roles WHERE server_id = :serverID AND user_id = :userID AND role_id = :roleID",
						{
							"serverID": interaction.guild.id,
							"userID": user.id,
							"roleID": goldRole.id,
						},
					)
					# Write to the DB
					await db.commit()

					# With the DB changes committed, we need to refresh the active timer
					await self.refresh_timer()

				elif view.response is None:
					# Action timed out
					await interaction.followup.send("Pending gold remove action has timed out", ephemeral=True)

				else:
					# Action cancelled
					await interaction.followup.send("TMTM Gold remove action cancelled.")

	@app_commands.command(name="list")
	async def list(self, interaction: discord.Interaction):
		"""Lists users that have TMTM Gold"""
		assert interaction.guild is not None

		# Start our DB block
		async with self.bot.db.connect() as db:
			async with db.connection.cursor() as cursor:
				# Get a list of gold users in this server
				await cursor.execute(
					"SELECT user_id, expiry_time FROM gold WHERE server_id = :serverID",
					{"serverID": interaction.guild.id},
				)
				usersData = await cursor.fetchall()

				# Create our base embed
				goldEmbed = discord.Embed(title="Gold Users", colour=GOLD_EMBED_COLOUR)

				for userData in usersData:
					user = interaction.guild.get_member(userData["user_id"])
					if user is not None:
						userName = user.display_name
					else:
						await cursor.execute(
							"SELECT display_name FROM users WHERE server_id = :serverID AND user_id = :userID",
							{
								"serverID": interaction.guild.id,
								"userID": userData["user_id"],
							},
						)
						data = await cursor.fetchone()
						userName = data["display_name"]

					# Add the user information to the embed
					goldEmbed.add_field(
						name=userName,
						value=f"<t:{userData['expiry_time']}:F>",
						inline=False,
					)

				# Send the embed information
				await interaction.response.send_message(embed=goldEmbed)

	@commands.Cog.listener()
	async def on_member_join(self, member: discord.Member):
		role = await self.bot.serverConfig.role_gold.get(member.guild)
		if role is not None:
			# Check if the user has gold in the database
			async with self.bot.db.connect() as db:
				async with db.connection.cursor() as cursor:
					# Get the user data from the DB
					await cursor.execute(
						"SELECT user_id FROM gold WHERE server_id = :server_id AND user_id = :user_id LIMIT 1",
						{"server_id": member.guild.id, "user_id": member.id},
					)
					if cursor.fetchone() is not None:
						try:
							await member.add_roles(role, reason="Re-adding TMTM gold to joining user")
						except (discord.Forbidden, discord.HTTPException):
							# Ignore reasonable errors when re-adding the role
							pass


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Gold(bot))
