import discord
from discord.ext import tasks
import slash_util

from datetime import datetime, timedelta, timezone
from typing import Literal

import blueonblue
from .users import update_member_roles

import logging
log = logging.getLogger("blueonblue")

JAIL_EMBED_COLOUR = 0xFF0000
JAIL_BLOCK_UPDATES_KEY = "jail"

# Set up views for the jail and release commands
class JailConfirm(blueonblue.views.AuthorResponseViewBase):
	"""Confirmation view for jail."""
	@discord.ui.button(label = "Jail", style = discord.ButtonStyle.danger)
	async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Red button for destructive action"""
		self.response = True
		await self.terminate()

	@discord.ui.button(label = "Cancel", style = discord.ButtonStyle.secondary)
	async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Grey button for cancellation"""
		self.response = False
		await self.terminate()

class ReleaseConfirm(blueonblue.views.AuthorResponseViewBase):
	"""Confirmation view for release."""
	@discord.ui.button(label = "Release", style = discord.ButtonStyle.danger)
	async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Red button for destructive action"""
		self.response = True
		await self.terminate()

	@discord.ui.button(label = "Cancel", style = discord.ButtonStyle.secondary)
	async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Grey button for cancellation"""
		self.response = False
		await self.terminate()

class Jail(slash_util.Cog, name="Jail"):
	"""Temporary "Jail" functions"""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		self.bot.loop.create_task(self.db_init())
		self.jail_loop.start()

	def cog_unload(self):
		self.jail_loop.stop()

	async def slash_command_error(self, ctx, error: Exception) -> None:
		"""Redirect slash command errors to the main bot"""
		return await self.bot.slash_command_error(ctx, error)

	async def db_init(self):
		"""Initializes the database for the cog.
		Creates the tables if they don't exist."""
		async with self.bot.db_connection.cursor() as cursor:
			# Create the tables if they do not exist
			await cursor.execute("CREATE TABLE if NOT EXISTS jail (\
				server_id INTEGER NOT NULL,\
				user_id INTEGER NOT NULL,\
				release_time INTEGER,\
				UNIQUE(server_id,user_id))")

			# Iterate through our serverConfig to set the "block_updates" flag on the jail role
			for guildID in self.bot.serverConfig.sections():
				roleID = self.bot.serverConfig.getint(str(guildID), "role_jail", fallback = -1)
				if roleID >= 0:
					# Role ID is present. Add info to the DB
					# Check if we have an existing entry
					await cursor.execute("SELECT role_id FROM roles WHERE block_updates = :block", {"block": JAIL_BLOCK_UPDATES_KEY})
					roleData = await cursor.fetchone()
					if roleData is not None: # We have an existing entry for the role
						if roleData["role_id"] != roleID:
							# Role IDs do not match. Remove block entry from old role.
							await cursor.execute("UPDATE roles SET block_updates = NULL WHERE server_id = :serverID AND role_id = :roleID",
								{"serverID": guildID, "roleID": roleID})
					else: # No existing entry for this block
						await cursor.execute("INSERT OR REPLACE INTO roles (server_id, role_id, block_updates) VALUES \
							(:serverID, :roleID, :block)", {"serverID": guildID, "roleID": roleID, "block": JAIL_BLOCK_UPDATES_KEY})
			await self.bot.db_connection.commit()

	@slash_util.slash_command(guild_id = blueonblue.debugServerID)
	@slash_util.describe(user = "User to be jailed.")
	@slash_util.describe(time = "Time duration for jail. Default unit is days.")
	@slash_util.describe(time_unit = "Unit of measurement for ""time"" parameter.")
	@blueonblue.checks.is_moderator()
	async def jail(self, ctx: slash_util.Context, user: discord.Member, time: float, time_unit: Literal["minutes", "hours", "days", "weeks"] = "days"):
		"""Jails a user"""

		# Start our DB block
		async with self.bot.db_connection.cursor() as cursor:
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
			releaseTimeStamp = round((datetime.now(timezone.utc) + timeDelta).timestamp())

			# Create a "time text"
			timeText = int(time) if time==int(time) else time

			# Build our embed and view
			view = JailConfirm(ctx)
			jailEmbed = discord.Embed(
				title = f"User to be jailed for `{timeText} {time_unit}` until",
				description=f"<t:{releaseTimeStamp}:F>",
				colour = JAIL_EMBED_COLOUR
			)
			jailEmbed.set_author(
				name = user.display_name,
				icon_url = user.avatar.url
			)
			view.message = await ctx.send(f"{ctx.author.mention}, you are about to jail the following user.", view = view, embed=jailEmbed)
			# Wait for the view to finish
			await view.wait()

			# Once we have a response, continue
			if view.response:
				# Action confirmed. Jail the user
				# Get the mod activity channel
				modChannel: discord.TextChannel = ctx.guild.get_channel(self.bot.serverConfig.getint(str(ctx.guild.id),"channel_mod_activity", fallback = -1))
				# We need to check if the user is already present in the jail DB
				await cursor.execute("SELECT * FROM jail WHERE server_id = :serverID AND user_id = :userID", {"serverID": ctx.guild.id, "userID": user.id})
				userData = await cursor.fetchone()
				if userData is None:
					# User not in jail DB
					await update_member_roles(user, cursor) # Update the user's roles in the DB
					# Add the "jailed" role to the user
					jailRole = ctx.guild.get_role(self.bot.serverConfig.getint(str(ctx.guild.id),"role_jail", fallback = -1))
					jailReason = f"User jailed by {ctx.author.display_name} for {timeText} {time_unit}."
					userRoles = []
					for role in user.roles: # Make a list of roles that the bot can remove
						if (role != ctx.guild.default_role) and (role < ctx.guild.me.top_role) and (not role.managed) and (role != jailRole):
							userRoles.append(role)
					try:
						await user.add_roles(jailRole, reason = jailReason)
						await user.remove_roles(*userRoles, reason = jailReason)
						await cursor.execute("INSERT OR REPLACE INTO jail (server_id, user_id, release_time) VALUES \
						(:serverID, :userID, :releaseTime)", {"serverID": ctx.guild.id, "userID": user.id, "releaseTime": releaseTimeStamp})
						await ctx.send(f"User {user.mention} has been jailed.", ephemeral=True)
						await modChannel.send(f"User {user.mention} has been jailed by {ctx.author.mention} for {timeText} {time_unit}.", allowed_mentions=None)
					except:
						await ctx.send("Failed to assign roles to jail user.")
				else:
					# User in jail DB. Only update release time.
					await cursor.execute("UPDATE jail SET release_time = :releaseTime WHERE server_id = :serverID AND user_id = :userID",
						{"serverID": ctx.guild.id, "userID": user.id, "releaseTime": releaseTimeStamp})
					await ctx.send(f"Updated release time for user {user.mention}.", ephemeral=True)
					await modChannel.send(f"Jail for user {user.mention} has been modified by {ctx.author.mention} to {timeText} {time_unit}.", allowed_mentions=None)
			elif not view.response:
				# Action cancelled
				await ctx.send("Jail action cancelled.")
			else:
				# Notify the user that the action timed out
				await ctx.send("Pending jail action has timed out", ephemeral=True)

	@slash_util.slash_command(guild_id = blueonblue.debugServerID)
	@slash_util.describe(user = "User to be released.")
	@blueonblue.checks.is_moderator()
	async def jail_release(self, ctx: slash_util.Context, user: discord.Member):
		"""Releases a user from jail"""

		# Start our DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Check if the user is already jailed
			await cursor.execute("SELECT user_id, release_time FROM jail WHERE server_id = :serverID AND user_id = :userID",
				{"serverID": ctx.guild.id, "userID": user.id})
			userData = await cursor.fetchone()
			if userData is None:
				# User not jailed
				await ctx.send(f"I could not find {user.mention} in the jail list.", ephemeral=True)
				return

			releaseTimestamp = userData["release_time"]

			# User present in jail list. Create our embed and message
			view = ReleaseConfirm(ctx)
			jailEmbed = discord.Embed(
				title = f"User jailed until",
				description=f"<t:{releaseTimestamp}:F>",
				colour = JAIL_EMBED_COLOUR
			)
			jailEmbed.set_author(
				name = user.display_name,
				icon_url = user.avatar.url
			)

			view.message = await ctx.send(f"{ctx.author.mention}, you are about to release the following user.", view = view, embed=jailEmbed)
			# Wait for the view to finish
			await view.wait()

			# Once we have a response, continue
			if view.response:
				# Action confirmed. Release the user
				# Get the mod activity channel
				modChannel: discord.TextChannel = ctx.guild.get_channel(self.bot.serverConfig.getint(str(ctx.guild.id),"channel_mod_activity", fallback = -1))
				# Get the jail role
				jailRole = ctx.guild.get_role(self.bot.serverConfig.getint(str(ctx.guild.id),"role_jail", fallback = -1))
				# Get the stored roles for the user
				await cursor.execute("SELECT role_id FROM user_roles WHERE server_id = :serverID AND user_id = :userID",
					{"serverID": ctx.guild.id, "userID": user.id})
				roleData = await cursor.fetchall()
				userRoles = []
				# Get the actual role objects
				for r in roleData:
					role = ctx.guild.get_role(r["role_id"])
					if role is not None:
						userRoles.append(role)

				# Remove the user info from the database
				await cursor.execute("DELETE FROM jail WHERE server_id = :serverID AND user_id = :userID", {"serverID": ctx.guild.id, "userID": user.id})
				await self.bot.db_connection.commit() # Commit changes

				jailReason = f"User released by {ctx.author.display_name}"

				# Try assigning the roles to the user
				try:
					await user.add_roles(*userRoles, reason = jailReason)
					await user.remove_roles(jailRole, reason = jailReason)
					await ctx.send(f"User {user.mention} has been released from jail.", ephemeral=True)
					await modChannel.send(f"User {user.mention} has been released from jail by {ctx.author.mention}", allowed_mentions=None)
				except:
					await modChannel.send(f"Error assigning roles when releasing user {user.mention} from jail. Please assign roles manually.", allowed_mentions=None)
					log.warning(f"Failed to assign roles to release user from jail. User: [{user.id}] Roles: [{userRoles}]")

			elif not view.response:
				# Action cancelled
				await ctx.send("Release action cancelled.")
			else:
				# Notify the user that the action timed out
				await ctx.send("Pending release action has timed out", ephemeral=True)

	@slash_util.slash_command(guild_id = blueonblue.debugServerID)
	@blueonblue.checks.is_moderator()
	async def jail_list(self, ctx: slash_util.Context):
		"""Lists users that are currently jailed"""

		# Start our DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Get a list of jailed users in this server
			await cursor.execute("SELECT user_id, release_time FROM jail WHERE server_id = :serverID", {"serverID": ctx.guild.id})
			usersData = await cursor.fetchall()

			# Create our base embed
			jailEmbed = discord.Embed(
				title = "Jailed Users",
				colour = JAIL_EMBED_COLOUR
			)

			for userData in usersData:
				user = ctx.guild.get_member(userData["user_id"])
				if user is not None:
					userName = user.display_name
				else:
					await cursor.execute("SELECT display_name FROM users WHERE server_id = :serverID AND user_id = :userID",
						{"serverID": ctx.guild.id, "userID": userData["user_id"]})
					data = await cursor.fetchone()
					userName = data["display_name"]

				# Add their information to the embed
				jailEmbed.add_field(name=userName, value=f"<t:{userData['release_time']}:F>", inline=False)

			# Send the embed information
			await ctx.send(embed = jailEmbed)

	@tasks.loop(minutes=1, reconnect=True)
	async def jail_loop(self):
		"""Checks if users need to be released from jail"""
		log.debug("Starting jail release check loop")
		# Start our DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Get a list of users that are past their release time
			# Get the current timestamp
			timeStamp = round(datetime.now(timezone.utc).timestamp())
			# Read the DB
			await cursor.execute("SELECT server_id, user_id FROM jail WHERE release_time < :time", {"time": timeStamp})
			releaseData = await cursor.fetchall()
			# Iterate through our release list
			for userData in releaseData:
				log.debug(f"Releasing user {userData['user_id']} from server {userData['server_id']}.")
				guild = self.bot.get_guild(userData["server_id"])
				if guild is not None:
					# Make sure that we can find the guild
					# Find the moderation activity channel
					modChannel: discord.TextChannel = guild.get_channel(self.bot.serverConfig.getint(str(guild.id),"channel_mod_activity", fallback = -1))
					# Get the jail role
					jailRole = guild.get_role(self.bot.serverConfig.getint(str(guild.id),"role_jail", fallback = -1))
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
							await user.remove_roles(jailRole, reason = "Jail timeout expired")
							await modChannel.send(f"User {user.mention} has been released from jail due to timeout expiry.", allowed_mentions=None)
						except:
							await modChannel.send(f"Error assigning roles when releasing user {user.display_name} from jail.", allowed_mentions=None)
							log.warning(f"Failed to assign roles to release user from jail. Guild: [{guild.id}]. User: [{user.id}]. Roles: {userRoles}")
					else:
						# Could not find the user
						if modChannel is not None:
							# Retrieve a name from the users database
							await cursor.execute("SELECT display_name FROM users WHERE server_id = :serverID AND user_id = :userID",
								{"serverID": userData["server_id"], "userID": userData["user_id"]})
							# We should only have one result
							userInfo = await cursor.fetchone()
							# Send our information to the moderation activity channel
							await modChannel.send(f"Failed to release user `{userInfo['display_name']}` from jail, user may no longer be present in the server", allowed_mentions=None)

			# Delete data of released users
			await cursor.execute("DELETE FROM jail WHERE release_time < :time", {"time": timeStamp})
			# Commit our changes
			await self.bot.db_connection.commit()


	@jail_loop.before_loop
	async def before_jail_loop(self):
		await self.bot.wait_until_ready() # Wait until the bot is ready

def setup(bot: blueonblue.BlueOnBlueBot):
	bot.add_cog(Jail(bot))