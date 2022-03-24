import discord
from discord import app_commands
from discord.ext import commands, tasks

from datetime import datetime, timedelta, timezone
from typing import Literal

import blueonblue

import logging
log = logging.getLogger("blueonblue")

GOLD_EMBED_COLOUR = 0xFF3491

class Gold(app_commands.Group, commands.Cog, name="gold"):
	"""Gold user functions"""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		self.gold_loop.start()

	async def cog_load(self):
		"""Initializes the database for the cog.
		Creates the tables if they don't exist."""
		async with self.bot.dbConnection.cursor() as cursor:
			# Create the tables if they do not exist
			await cursor.execute("CREATE TABLE if NOT EXISTS gold (\
				server_id INTEGER NOT NULL,\
				user_id INTEGER NOT NULL,\
				expiry_time INTEGER,\
				UNIQUE(server_id,user_id))")
			# Commit changes to the DB
			await self.bot.dbConnection.commit()

	async def cog_unload(self):
		self.gold_loop.stop()

	@app_commands.command(name = "add")
	@app_commands.describe(user = "User to be given TMTM gold.")
	@app_commands.describe(time = "Time duration for TMTM Gold. Default unit is days.")
	@app_commands.describe(time_unit = "Unit of measurement for ""time"" parameter.")
	async def add(self, interaction: discord.Interaction, user: discord.Member, time: float, time_unit: Literal["minutes", "hours", "days", "weeks"] = "days"):
		"""Gives TMTM Gold to a user"""
		if not await blueonblue.checks.app_is_admin(interaction):
			return

		# Start our DB block
		async with self.bot.dbConnection.cursor() as cursor:
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
			expiryTimeStamp = round((discord.utils.utcnow() + timeDelta).timestamp())

			# Create a "time text"
			timeText = int(time) if time==int(time) else time

			# Build our embed and view
			view = blueonblue.views.ConfirmView(interaction.user)
			goldEmbed = discord.Embed(
				title = f"Gold to be given for `{timeText} {time_unit}` until",
				description=f"<t:{expiryTimeStamp}:F>",
				colour = GOLD_EMBED_COLOUR
			)
			goldEmbed.set_author(
				name = user.display_name,
				icon_url = user.avatar.url
			)
			await interaction.response.send_message(f"{interaction.user.mention}, you are about to give TMTM Gold to the following user.", view = view, embed=goldEmbed)
			view.message = await interaction.original_message()
			# Wait for the view to finish
			await view.wait()

			# Once we have a response, continue
			if view.response:
				# Action confirmed. Give gold to the user
				# Get the mod activity channel
				modChannel: discord.TextChannel = interaction.guild.get_channel(self.bot.serverConfig.getint(str(interaction.guild.id),"channel_mod_activity", fallback = -1))
				# We need to check if the user is already present in the gold DB
				await cursor.execute("SELECT * FROM gold WHERE server_id = :serverID AND user_id = :userID", {"serverID": interaction.guild.id, "userID": user.id})
				userData = await cursor.fetchone()
				if userData is None:
					# User not in gold DB
					# Add the "gold" role to the user
					goldRole = interaction.guild.get_role(self.bot.serverConfig.getint(str(interaction.guild.id),"role_gold", fallback = -1))
					goldReason = f"TMTM Gold given by {interaction.user.display_name} for {timeText} {time_unit}."
					try:
						await user.add_roles(goldRole, reason = goldReason)
						await cursor.execute("INSERT OR REPLACE INTO gold (server_id, user_id, expiry_time) VALUES \
						(:serverID, :userID, :expiryTime)", {"serverID": interaction.guild.id, "userID": user.id, "expiryTime": expiryTimeStamp})
						await interaction.followup.send(f"TMTM Gold has been given to {user.mention}.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
						await modChannel.send(f"User {user.mention} has been given TMTM Gold by {interaction.user.mention} for {timeText} {time_unit}.", allowed_mentions=discord.AllowedMentions.none())
					except:
						await interaction.followup.send("Failed to assign roles to gold user.")
				else:
					# User in gold DB. Only update expiry time.
					await cursor.execute("UPDATE gold SET expiry_time = :expiryTime WHERE server_id = :serverID AND user_id = :userID",
						{"serverID": interaction.guild.id, "userID": user.id, "expiryTime": expiryTimeStamp})
					await interaction.followup.send(f"Updated expiry time for user {user.mention}.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
					await modChannel.send(f"TMTM Gold for user {user.mention} has been modified by {interaction.user.mention} to {timeText} {time_unit}.", allowed_mentions=discord.AllowedMentions.none())

				# Commit changes to the DB
				await self.bot.dbConnection.commit()

			elif view.response is None:
				# Notify the user that the action timed out
				await interaction.followup.send("Pending TMTM Gold action has timed out", ephemeral=True)

			else:
				# Action cancelled
				await interaction.followup.send("TMTM Gold action cancelled")

	@app_commands.command(name = "remove")
	@app_commands.describe(user = "User to have TMTM Gold removed")
	async def remove(self, interaction: discord.Interaction, user: discord.Member):
		"""Removes TMTM Gold from a user"""
		if not await blueonblue.checks.app_is_admin(interaction):
			return

		# Start our DB block
		async with self.bot.dbConnection.cursor() as cursor:
			# Check if the user is already jailed
			await cursor.execute("SELECT user_id, expiry_time FROM gold WHERE server_id = :serverID AND user_id = :userID",
				{"serverID": interaction.guild.id, "userID": user.id})
			userData = await cursor.fetchone()
			if userData is None:
				# User not jailed
				await interaction.response.send_message(f"I could not find {user.mention} in the gold list.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
				return

			expiryTimeStamp = userData["expiry_time"]

			# User present in gold table. Create our embed and message.
			view = blueonblue.views.ConfirmView(interaction.user)
			goldEmbed = discord.Embed(
				title = f"User has TMTM Gold until",
				description=f"<t:{expiryTimeStamp}:F>",
				colour = GOLD_EMBED_COLOUR
			)
			goldEmbed.set_author(
				name = user.display_name,
				icon_url = user.avatar.url
			)
			await interaction.response.send_message(f"{interaction.user.mention}, you are about to remove TMTM Gold from the following user.", view = view, embed=goldEmbed)
			view.message = await interaction.original_message()
			# Wait for the view to finish
			await view.wait()

			# Once we have a response, continue
			if view.response:
				# Action confirmed. Remove gold.
				# Get the mod activity channel
				modChannel: discord.TextChannel = interaction.guild.get_channel(self.bot.serverConfig.getint(str(interaction.guild.id),"channel_mod_activity", fallback = -1))
				# Get the gold role
				goldRoleID = self.bot.serverConfig.getint(str(interaction.guild.id),"role_gold", fallback = -1)
				goldRole = interaction.guild.get_role(goldRoleID)
				goldReason = f"TMTM Gold removed by {interaction.user.display_name}"
				# Remove the role from the user (if present)
				if goldRole in user.roles:
					await user.remove_roles(goldRole, reason = goldReason)
				await interaction.followup.send(f"TMTM gold removed for {user.mention}.", ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
				await modChannel.send(f"User {user.mention} has had TMTM Gold removed by {interaction.user.mention}.", allowed_mentions=discord.AllowedMentions.none())
				# Remove the entry from the gold DB
				await cursor.execute("DELETE FROM gold WHERE server_id = :serverID AND user_id = :userID",
					{"serverID": interaction.guild.id, "userID": user.id})
				# Make sure that we remove the role reference from the users DB (if present)
				await cursor.execute("DELETE FROM user_roles WHERE server_id = :serverID AND user_id = :userID AND role_id = :roleID",
					{"serverID": interaction.guild.id, "userID": user.id, "roleID": goldRoleID})
				# Write to the DB
				await self.bot.dbConnection.commit()

			elif view.response is None:
				# Action timed out
				await interaction.followup.send("Pending gold remove action has timed out", ephemeral=True)

			else:
				# Action cancelled
				await interaction.followup.send("TMTM Gold remove action cancelled.")


	@app_commands.command(name = "list")
	async def list(self, interaction: discord.Interaction):
		"""Lists users that have TMTM Gold"""
		if not await blueonblue.checks.app_is_admin(interaction):
			return

		# Start our DB block
		async with self.bot.dbConnection.cursor() as cursor:
			# Get a list of gold users in this server
			await cursor.execute("SELECT user_id, expiry_time FROM gold WHERE server_id = :serverID", {"serverID": interaction.guild.id})
			usersData = await cursor.fetchall()

			# Create our base embed
			goldEmbed = discord.Embed(
				title = "Gold Users",
				colour = GOLD_EMBED_COLOUR
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

				# Add the user information to the embed
				goldEmbed.add_field(name=userName, value=f"<t:{userData['expiry_time']}:F>", inline=False)

			# Send the embed information
			await interaction.response.send_message(embed = goldEmbed)

	@tasks.loop(minutes=1, reconnect=True)
	async def gold_loop(self):
		"""Checks if gold for a user has expired"""
		log.debug("Starting gold expiry check loop")
		# Start our DB block
		async with self.bot.dbConnection.cursor() as cursor:
			# Get a list of users that are past their expiry time
			# Get the current timestamp
			timeStamp = round(discord.utils.utcnow().timestamp())
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
								await modChannel.send(f"TMTM Gold has expired for user {user.mention}.", allowed_mentions=discord.AllowedMentions.none())
							except:
								await modChannel.send(f"Error removing expired TMTM Gold from user {user.display_name}. The user may no longer present in the server.", allowed_mentions=discord.AllowedMentions.none())
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
								await modChannel.send(f"TMTM Gold has expired for user {userInfo['display_name']}.", allowed_mentions=discord.AllowedMentions.none())

						# Regardless of if we found the user or not, we need to remove their gold role from the roles table
						await cursor.execute("DELETE FROM user_roles WHERE server_id = :serverID AND user_id = :userID and role_id = :roleID",
							{"serverID": userData["server_id"], "userID": userData["user_id"], "roleID": goldRole.id})

			# Delete data of released users
			await cursor.execute("DELETE FROM gold WHERE expiry_time < :time", {"time": timeStamp})
			# Commit our changes
			await self.bot.dbConnection.commit()

	@gold_loop.before_loop
	async def before_gold_loop(self):
		await self.bot.wait_until_ready() # Wait until the bot is ready

async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Gold(bot))
