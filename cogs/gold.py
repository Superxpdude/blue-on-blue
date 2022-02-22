import discord
from discord.ext import tasks
import slash_util

from datetime import datetime, timedelta, timezone
from typing import Literal

import blueonblue

import logging
log = logging.getLogger("blueonblue")

GOLD_EMBED_COLOUR = 0xFF3491

# Set up views for the gold commands
class GoldConfirm(blueonblue.views.AuthorResponseViewBase):
	"""Confirmation view for gold."""
	@discord.ui.button(label = "Confirm", style = discord.ButtonStyle.green)
	async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Green button for confirmation"""
		self.response = True
		await self.terminate()

	@discord.ui.button(label = "Cancel", style = discord.ButtonStyle.secondary)
	async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
		"""Grey button for cancellation"""
		self.response = False
		await self.terminate()

class Gold(slash_util.Cog, name="Gold"):
	"""Gold user functions"""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		self.bot.loop.create_task(self.db_init())
		self.gold_loop.start()

	def cog_unload(self):
		self.gold_loop.stop()

	async def db_init(self):
		"""Initializes the database for the cog.
		Creates the tables if they don't exist."""
		async with self.bot.db_connection.cursor() as cursor:
			# Create the tables if they do not exist
			await cursor.execute("CREATE TABLE if NOT EXISTS gold (\
				server_id INTEGER NOT NULL,\
				user_id INTEGER NOT NULL,\
				expiry_time INTEGER,\
				UNIQUE(server_id,user_id))")
			# Commit changes to the DB
			await self.bot.db_connection.commit()

	@slash_util.slash_command(guild_id = blueonblue.debugServerID)
	@slash_util.describe(user = "User to be given TMTM gold.")
	@slash_util.describe(time = "Time duration for TMTM Gold. Default unit is days.")
	@slash_util.describe(time_unit = "Unit of measurement for ""time"" parameter.")
	async def gold(self, ctx: slash_util.Context, user: discord.Member, time: float, time_unit: Literal["minutes", "hours", "days", "weeks"] = "days"):
		"""Gives TMTM Gold to a user"""
		if not (await blueonblue.checks.slash_is_admin(self.bot, ctx)):
			await ctx.send("You are not authorized to use this command", ephemeral=True)
			return

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

			# Now that we have our timedelta, find the expiry time
			expiryTimeStamp = round((datetime.now(timezone.utc) + timeDelta).timestamp())

			# Create a "time text"
			timeText = int(time) if time==int(time) else time

			# Build our embed and view
			view = GoldConfirm(ctx)
			jailEmbed = discord.Embed(
				title = f"Gold to be given for `{timeText} {time_unit}` until",
				description=f"<t:{expiryTimeStamp}:F>",
				colour = GOLD_EMBED_COLOUR
			)
			jailEmbed.set_author(
				name = user.display_name,
				icon_url = user.avatar.url
			)
			view.message = await ctx.send(f"{ctx.author.mention}, you are about to give TMTM Gold to the following user.", view = view, embed=jailEmbed)
			# Wait for the view to finish
			await view.wait()

			# Once we have a response, continue
			if view.response:
				# Action confirmed. Give gold to the user
				# Get the mod activity channel
				modChannel: discord.TextChannel = ctx.guild.get_channel(self.bot.serverConfig.getint(str(ctx.guild.id),"channel_mod_activity", fallback = -1))
				# We need to check if the user is already present in the gold DB
				await cursor.execute("SELECT * FROM gold WHERE server_id = :serverID AND user_id = :userID", {"serverID": ctx.guild.id, "userID": user.id})
				userData = await cursor.fetchone()
				if userData is None:
					# User not in gold DB
					# Add the "gold" role to the user
					goldRole = ctx.guild.get_role(self.bot.serverConfig.getint(str(ctx.guild.id),"role_gold", fallback = -1))
					goldReason = f"TMTM Gold given by {ctx.author.display_name} for {timeText} {time_unit}."
					try:
						await user.add_roles(goldRole, reason = goldReason)
						await cursor.execute("INSERT OR REPLACE INTO gold (server_id, user_id, expiry_time) VALUES \
						(:serverID, :userID, :expiryTime)", {"serverID": ctx.guild.id, "userID": user.id, "expiryTime": expiryTimeStamp})
						await ctx.send(f"TMTM Gold has been given to {user.mention}.", ephemeral=True)
						await modChannel.send(f"User {user.mention} has been given TMTM Gold by {ctx.author.mention} for {timeText} {time_unit}.", allowed_mentions=None)
					except:
						await ctx.send("Failed to assign roles to gold user.")
				else:
					# User in gold DB. Only update expiry time.
					await cursor.execute("UPDATE gold SET expiry_time = :expiryTime WHERE server_id = :serverID AND user_id = :userID",
						{"serverID": ctx.guild.id, "userID": user.id, "expiryTime": expiryTimeStamp})
					await ctx.send(f"Updated expiry time for user {user.mention}.", ephemeral=True)
					await modChannel.send(f"TMTM Gold for user {user.mention} has been modified by {ctx.author.mention} to {timeText} {time_unit}.", allowed_mentions=None)

				# Commit changes to the DB
				await self.bot.db_connection.commit()

			elif view.response is None:
				# Notify the user that the action timed out
				await ctx.send("Pending TMTM Gold action has timed out", ephemeral=True)

			else:
				# Action cancelled
				await ctx.send("TMTM Gold action cancelled")

	@slash_util.slash_command(guild_id = blueonblue.debugServerID)
	@slash_util.describe(user = "User to have TMTM Gold removed")
	async def gold_remove(self, ctx: slash_util.Context, user: discord.Member):
		"""Removes TMTM Gold from a user"""
		if not (await blueonblue.checks.slash_is_admin(self.bot, ctx)):
			await ctx.send("You are not authorized to use this command", ephemeral=True)
			return

		# Start our DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Check if the user is already jailed
			await cursor.execute("SELECT user_id, expiry_time FROM gold WHERE server_id = :serverID AND user_id = :userID",
				{"serverID": ctx.guild.id, "userID": user.id})
			userData = await cursor.fetchone()
			if userData is None:
				# User not jailed
				await ctx.send(f"I could not find {user.mention} in the gold list.", ephemeral=True)
				return

			expiryTimeStamp = userData["expiry_time"]

			# User present in gold table. Create our embed and message.
			view = GoldConfirm(ctx)
			jailEmbed = discord.Embed(
				title = f"User has TMTM Gold until",
				description=f"<t:{expiryTimeStamp}:F>",
				colour = GOLD_EMBED_COLOUR
			)
			jailEmbed.set_author(
				name = user.display_name,
				icon_url = user.avatar.url
			)
			view.message = await ctx.send(f"{ctx.author.mention}, you are about to remove TMTM Gold from the following user.", view = view, embed=jailEmbed)
			# Wait for the view to finish
			await view.wait()

			# Once we have a response, continue
			if view.response:
				# Action confirmed. Remove gold.
				# Get the mod activity channel
				modChannel: discord.TextChannel = ctx.guild.get_channel(self.bot.serverConfig.getint(str(ctx.guild.id),"channel_mod_activity", fallback = -1))
				# Get the gold role
				goldRoleID = self.bot.serverConfig.getint(str(ctx.guild.id),"role_gold", fallback = -1)
				goldRole = ctx.guild.get_role(goldRoleID)
				goldReason = f"TMTM Gold removed by {ctx.author.display_name}"
				# Remove the role from the user (if present)
				if goldRole in user.roles:
					await user.remove_roles(goldRole, reason = goldReason)
				await ctx.send(f"TMTM gold removed for {user.display_name}.", ephemeral=True)
				await modChannel.send(f"User {user.mention} has had TMTM Gold removed by {ctx.author.mention}.", allowed_mentions=None)
				# Remove the entry from the gold DB
				await cursor.execute("DELETE FROM gold WHERE server_id = :serverID AND user_id = :userID",
					{"serverID": ctx.guild.id, "userID": user.id})
				# Make sure that we remove the role reference from the users DB (if present)
				await cursor.execute("DELETE FROM user_roles WHERE server_id = :serverID AND user_id = :userID AND role_id = :roleID",
					{"serverID": ctx.guild.id, "userID": user.id, "roleID": goldRoleID})
				# Write to the DB
				await self.bot.db_connection.commit()

			elif view.response is None:
				# Action timed out
				await ctx.send("Pending gold remove action has timed out", ephemeral=True)

			else:
				# Action cancelled
				await ctx.send("TMTM Gold remove action cancelled.")


	@slash_util.slash_command(guild_id = blueonblue.debugServerID)
	async def gold_list(self, ctx: slash_util.Context):
		"""Lists users that have TMTM Gold"""
		if not (await blueonblue.checks.slash_is_admin(self.bot, ctx)):
			await ctx.send("You are not authorized to use this command", ephemeral=True)
			return

		# Start our DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Get a list of gold users in this server
			await cursor.execute("SELECT user_id, expiry_time FROM gold WHERE server_id = :serverID", {"serverID": ctx.guild.id})
			usersData = await cursor.fetchall()

			# Create our base embed
			goldEmbed = discord.Embed(
				title = "Gold Users",
				colour = GOLD_EMBED_COLOUR
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

				# Add the user information to the embed
				goldEmbed.add_field(name=userName, value=f"<t:{userData['expiry_time']}:F>", inline=False)

			# Send the embed information
			await ctx.send(embed = goldEmbed)

	@tasks.loop(minutes=1, reconnect=True)
	async def gold_loop(self):
		"""Checks if gold for a user has expired"""
		log.debug("Starting gold expiry check loop")
		# Start our DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Get a list of users that are past their expiry time
			# Get the current timestamp
			timeStamp = round(datetime.now(timezone.utc).timestamp())
			# Check if any users have expired gold
			await cursor.execute("SELECT server_id, user_id FROM gold WHERE expiry_time < :time", {"time": timeStamp})
			expiryData = await cursor.fetchall()
			# Iterate through our expiry list
			for userData in expiryData:
				log.debug(f"Gold expired for user {userData['user_id']} in server {userData['server_id']}.")
				guild = self.bot.get_guild(userData["server_id"])
				if guild is not None:
					# Make sure that we can find the guild
					# Find the moderation activity channel
					modChannel: discord.TextChannel = guild.get_channel(self.bot.serverConfig.getint(str(guild.id),"channel_mod_activity", fallback = -1))
					# Get the jail role
					goldRole = guild.get_role(self.bot.serverConfig.getint(str(guild.id),"role_gold", fallback = -1))
					# Only continue if the goldRole exists
					if goldRole is not None:
						user = guild.get_member(userData["user_id"])
						if user is not None:
							# We have found the user
							try:
								await user.remove_roles(goldRole, reason = "Jail timeout expired")
								await modChannel.send(f"TMTM Gold has expired for user {user.mention}.", allowed_mentions=None)
							except:
								await modChannel.send(f"Error removing expired TMTM Gold from user {user.display_name}. The user may no longer present in the server.", allowed_mentions=None)
								log.warning(f"Failed to remove expired TMTM Gold role from user. Guild: [{guild.id}]. User: [{user.id}].")
						else:
							# Could not find the user
							if modChannel is not None:
								# Retrieve a name from the users database
								await cursor.execute("SELECT display_name FROM users WHERE server_id = :serverID AND user_id = :userID",
									{"serverID": userData["server_id"], "userID": userData["user_id"]})
								# We should only have one result
								userInfo = await cursor.fetchone()
								# Send our information to the moderation activity channel
								await modChannel.send(f"TMTM Gold has expired for user {userInfo['display_name']}.", allowed_mentions=None)

						# Regardless of if we found the user or not, we need to remove their gold role from the roles table
						await cursor.execute("DELETE FROM user_roles WHERE server_id = :serverID AND user_id = :userID and role_id = :roleID",
							{"serverID": userData["server_id"], "userID": userData["user_id"], "roleID": goldRole.id})

			# Delete data of released users
			await cursor.execute("DELETE FROM gold WHERE expiry_time < :time", {"time": timeStamp})
			# Commit our changes
			await self.bot.db_connection.commit()

	@gold_loop.before_loop
	async def before_gold_loop(self):
		await self.bot.wait_until_ready() # Wait until the bot is ready

def setup(bot: blueonblue.BlueOnBlueBot):
	bot.add_cog(Gold(bot))