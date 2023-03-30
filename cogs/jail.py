import discord
from discord import app_commands
from discord.ext import tasks, commands

from datetime import datetime, timedelta, timezone
from typing import Literal

import blueonblue
from .users import update_member_roles
from blueonblue.defines import (
	SCONF_CHANNEL_MOD_ACTIVITY,
	SCONF_ROLE_JAIL
)

import logging
_log = logging.getLogger(__name__)

JAIL_EMBED_COLOUR = 0xFF0000
JAIL_BLOCK_UPDATES_KEY = "jail"

@app_commands.guild_only()
@app_commands.default_permissions(manage_messages=True)
class Jail(commands.GroupCog, group_name="jail"):
	"""Jail commands"""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot


	async def cog_load(self):
		"""Initializes the database for the cog.
		Creates the tables if they don't exist."""
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				# Iterate through our servers to set the "block_updates" flag on the jail role
				for guild in self.bot.guilds:
					role = await self.bot.serverConfig.role_jail.get(guild)
					if role is not None:
						# Role ID is present. Add info to the DB
						# Check if we have an existing entry
						await cursor.execute("SELECT role_id FROM roles WHERE block_updates = :block", {"block": JAIL_BLOCK_UPDATES_KEY})
						roleData = await cursor.fetchone()
						if roleData is not None: # We have an existing entry for the role
							if roleData["role_id"] != role.id:
								# Role IDs do not match. Remove block entry from old role.
								await cursor.execute("UPDATE roles SET block_updates = NULL WHERE server_id = :serverID AND role_id = :roleID",
									{"serverID": guild.id, "roleID": role.id})
						else: # No existing entry for this block
							await cursor.execute("INSERT OR REPLACE INTO roles (server_id, role_id, block_updates) VALUES \
								(:serverID, :roleID, :block)", {"serverID": guild.id, "roleID": role.id, "block": JAIL_BLOCK_UPDATES_KEY})
				await db.commit()

		self.jail_loop.start()

	async def cog_unload(self):
		self.jail_loop.stop()

	@app_commands.command(name = "jail")
	@app_commands.describe(
		user = "User to be jailed",
		time = "Time duration for jail. Default unit is days",
		time_unit = "Unit of measurement for the ""time"" parameter"
	)
	@blueonblue.checks.has_configs(SCONF_CHANNEL_MOD_ACTIVITY, SCONF_ROLE_JAIL)
	async def jail(self, interaction: discord.Interaction, user: discord.Member, time: float, time_unit: Literal["minutes", "hours", "days", "weeks"] = "days"):
		"""Jails a user"""
		assert interaction.guild is not None

		modChannel = await self.bot.serverConfig.channel_mod_activity.get(interaction.guild)
		assert modChannel is not None
		jailRole = await self.bot.serverConfig.role_jail.get(interaction.guild)
		assert jailRole is not None

		# Start our DB block
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				# Get our timedelta
				if time_unit == "minutes":
					timeDelta = timedelta(minutes=time)
				elif time_unit == "hours":
					timeDelta = timedelta(hours=time)
				elif time_unit == "weeks":
					timeDelta = timedelta(weeks=time)
				else: # Days
					timeDelta = timedelta(days=time)

				# Now that we have our timedelta, find the release time
				releaseTimeStamp = round((discord.utils.utcnow() + timeDelta).timestamp())

				# Create a "time text"
				timeText = int(time) if time==int(time) else time

				# Build our embed and view
				view = blueonblue.views.ConfirmViewDanger(interaction.user, confirm="Jail")
				jailEmbed = discord.Embed(
					title = f"User to be jailed for `{timeText} {time_unit}` until",
					description=f"<t:{releaseTimeStamp}:F>",
					colour = JAIL_EMBED_COLOUR
				)
				jailEmbed.set_author(
					name = user.display_name,
					icon_url = user.display_avatar.url
				)
				await interaction.response.send_message(f"{interaction.user.mention}, you are about to jail the following user.", view = view, embed=jailEmbed)
				view.message = await interaction.original_response()
				# Wait for the view to finish
				await view.wait()

				# Once we have a response, continue
				if view.response:
					# Action confirmed. Jail the user
					# We need to check if the user is already present in the jail DB
					await cursor.execute("SELECT * FROM jail WHERE server_id = :serverID AND user_id = :userID", {"serverID": interaction.guild.id, "userID": user.id})
					userData = await cursor.fetchone()
					if userData is None:
						# User not in jail DB
						await update_member_roles(user, cursor) # Update the user's roles in the DB
						# Add the "jailed" role to the user
						jailReason = f"User jailed by {interaction.user.display_name} for {timeText} {time_unit}."
						userRoles = []
						for role in user.roles: # Make a list of roles that the bot can remove
							if (role != interaction.guild.default_role) and (role < interaction.guild.me.top_role) and (not role.managed) and (role != jailRole):
								userRoles.append(role)
						try:
							assert jailRole is not None
							await user.add_roles(jailRole, reason = jailReason)
							await user.remove_roles(*userRoles, reason = jailReason)
							await cursor.execute("INSERT OR REPLACE INTO jail (server_id, user_id, release_time) VALUES \
							(:serverID, :userID, :releaseTime)", {"serverID": interaction.guild.id, "userID": user.id, "releaseTime": releaseTimeStamp})
							await interaction.followup.send(f"User {user.mention} has been jailed.", ephemeral=True)
							await modChannel.send(f"User {user.mention} has been jailed by {interaction.user.mention} for {timeText} {time_unit}.", allowed_mentions=discord.AllowedMentions.none())
						except:
							await interaction.followup.send("Failed to assign roles to jail user.")
					else:
						# User in jail DB. Only update release time.
						await cursor.execute("UPDATE jail SET release_time = :releaseTime WHERE server_id = :serverID AND user_id = :userID",
							{"serverID": interaction.guild.id, "userID": user.id, "releaseTime": releaseTimeStamp})
						await interaction.followup.send(f"Updated release time for user {user.mention}.", ephemeral=True)
						await modChannel.send(f"Jail for user {user.mention} has been modified by {interaction.user.mention} to {timeText} {time_unit}.", allowed_mentions=discord.AllowedMentions.none())
				elif not view.response:
					# Action cancelled
					await interaction.followup.send("Jail action cancelled.")
				else:
					# Notify the user that the action timed out
					await interaction.followup.send("Pending jail action has timed out", ephemeral=True)

	@app_commands.command(name = "release")
	@app_commands.describe(user = "User to be released")
	@blueonblue.checks.has_configs(SCONF_CHANNEL_MOD_ACTIVITY, SCONF_ROLE_JAIL)
	async def release(self, interaction: discord.Interaction, user: discord.Member):
		"""Releases a user from jail"""
		assert interaction.guild is not None

		modChannel = await self.bot.serverConfig.channel_mod_activity.get(interaction.guild)
		assert modChannel is not None
		jailRole = await self.bot.serverConfig.role_jail.get(interaction.guild)
		assert jailRole is not None

		# Start our DB block
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				# Check if the user is already jailed
				await cursor.execute("SELECT user_id, release_time FROM jail WHERE server_id = :serverID AND user_id = :userID",
					{"serverID": interaction.guild.id, "userID": user.id})
				userData = await cursor.fetchone()
				if userData is None:
					# User not jailed
					await interaction.response.send_message(f"I could not find {user.mention} in the jail list.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
					return

				releaseTimestamp = userData["release_time"]

				# User present in jail list. Create our embed and message
				view = blueonblue.views.ConfirmViewDanger(interaction.user, confirm="Release")
				jailEmbed = discord.Embed(
					title = f"User jailed until",
					description=f"<t:{releaseTimestamp}:F>",
					colour = JAIL_EMBED_COLOUR
				)
				jailEmbed.set_author(
					name = user.display_name,
					icon_url = user.display_avatar.url
				)

				await interaction.response.send_message(f"{interaction.user.mention}, you are about to release the following user.", view = view, embed=jailEmbed)
				view.message = await interaction.original_response()
				# Wait for the view to finish
				await view.wait()

				# Once we have a response, continue
				if view.response:
					# Action confirmed. Release the user
					# Get the stored roles for the user
					await cursor.execute("SELECT role_id FROM user_roles WHERE server_id = :serverID AND user_id = :userID",
						{"serverID": interaction.guild.id, "userID": user.id})
					roleData = await cursor.fetchall()
					userRoles = []
					# Get the actual role objects
					for r in roleData:
						role = interaction.guild.get_role(r["role_id"])
						if role is not None:
							userRoles.append(role)

					# Remove the user info from the database
					await cursor.execute("DELETE FROM jail WHERE server_id = :serverID AND user_id = :userID", {"serverID": interaction.guild.id, "userID": user.id})
					await db.commit() # Commit changes

					jailReason = f"User released by {interaction.user.display_name}"

					# Try assigning the roles to the user
					try:
						await user.add_roles(*userRoles, reason = jailReason)
						assert jailRole is not None
						await user.remove_roles(jailRole, reason = jailReason)
						await interaction.followup.send(f"User {user.mention} has been released from jail.", ephemeral=True)
						await modChannel.send(f"User {user.mention} has been released from jail by {interaction.user.mention}", allowed_mentions=discord.AllowedMentions.none())
					except:
						await modChannel.send(f"Error assigning roles when releasing user {user.mention} from jail. Please assign roles manually.", allowed_mentions=discord.AllowedMentions.none())
						_log.warning(f"Failed to assign roles to release user from jail. User: [{user.id}] Roles: [{userRoles}]")

				elif not view.response:
					# Action cancelled
					await interaction.followup.send("Release action cancelled.")
				else:
					# Notify the user that the action timed out
					await interaction.followup.send("Pending release action has timed out", ephemeral=True)

	@app_commands.command(name = "list")
	async def list(self, interaction: discord.Interaction):
		"""Lists users that are currently jailed"""
		assert interaction.guild is not None

		# Start our DB block
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				# Get a list of jailed users in this server
				await cursor.execute("SELECT user_id, release_time FROM jail WHERE server_id = :serverID", {"serverID": interaction.guild.id})
				usersData = await cursor.fetchall()

				# Create our base embed
				jailEmbed = discord.Embed(
					title = "Jailed Users",
					colour = JAIL_EMBED_COLOUR
				)

				for userData in usersData:
					user = interaction.guild.get_member(userData["user_id"])
					if user is not None:
						userName = user.display_name
					else:
						await cursor.execute("SELECT display_name FROM users WHERE server_id = :serverID AND user_id = :userID",
							{"serverID": interaction.guild.id, "userID": userData["user_id"]})
						data = await cursor.fetchone()
						userName = data["display_name"]

					# Add their information to the embed
					jailEmbed.add_field(name=userName, value=f"<t:{userData['release_time']}:F>", inline=False)

				# Send the embed information
				await interaction.response.send_message(embed = jailEmbed)

	@tasks.loop(minutes=1, reconnect=True)
	async def jail_loop(self):
		"""Checks if users need to be released from jail"""
		_log.debug("Starting jail release check loop")
		# Start our DB block
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				# Get a list of users that are past their release time
				# Get the current timestamp
				timeStamp = round(datetime.now(timezone.utc).timestamp())
				# Read the DB
				await cursor.execute("SELECT server_id, user_id FROM jail WHERE release_time < :time", {"time": timeStamp})
				releaseData = await cursor.fetchall()
				# Iterate through our release list
				for userData in releaseData:
					_log.debug(f"Releasing user {userData['user_id']} from server {userData['server_id']}.")
					guild = self.bot.get_guild(userData["server_id"])
					if guild is not None:
						# Make sure that we can find the guild
						# Find the moderation activity channel
						modChannel = await self.bot.serverConfig.channel_mod_activity.get(guild)
						# Get the jail role
						jailRole = await self.bot.serverConfig.role_jail.get(guild)
						user = guild.get_member(userData["user_id"])
						if user is not None:
							# We have found the user
							# Get the user's roles
							await cursor.execute("SELECT role_id FROM user_roles WHERE server_id = :serverID AND user_id = :userID",
								{"serverID": guild.id, "userID": user.id})
							userRoleData = await cursor.fetchall()
							userRoles = []
							for r in userRoleData:
								role = guild.get_role(r["role_id"])
								if role is not None:
									userRoles.append(role)
							# Remove the jail role, and return the user's original roles
							try:
								await user.add_roles(*userRoles, reason = "Jail timeout expired")
								assert jailRole is not None
								await user.remove_roles(jailRole, reason = "Jail timeout expired")
								if modChannel is not None:
									await modChannel.send(f"User {user.mention} has been released from jail due to timeout expiry.", allowed_mentions=discord.AllowedMentions.none())
							except:
								if modChannel is not None:
									await modChannel.send(f"Error assigning roles when releasing user {user.display_name} from jail.", allowed_mentions=discord.AllowedMentions.none())
								_log.warning(f"Failed to assign roles to release user from jail. Guild: [{guild.id}]. User: [{user.id}]. Roles: {userRoles}")
						else:
							# Could not find the user
							if modChannel is not None:
								# Retrieve a name from the users database
								await cursor.execute("SELECT display_name FROM users WHERE server_id = :serverID AND user_id = :userID",
									{"serverID": userData["server_id"], "userID": userData["user_id"]})
								# We should only have one result
								userInfo = await cursor.fetchone()
								# Send our information to the moderation activity channel
								await modChannel.send(f"Failed to release user `{userInfo['display_name']}` from jail, user may no longer be present in the server", allowed_mentions=discord.AllowedMentions.none())

				# Delete data of released users
				await cursor.execute("DELETE FROM jail WHERE release_time < :time", {"time": timeStamp})
				# Commit our changes
				await db.commit()


	@jail_loop.before_loop
	async def before_jail_loop(self):
		await self.bot.wait_until_ready() # Wait until the bot is ready

async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Jail(bot))
