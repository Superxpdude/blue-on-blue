import discord
from discord import app_commands
from discord.ext import commands

from datetime import timedelta
from typing import Literal

import blueonblue
from blueonblue.defines import PING_EMBED_COLOUR

import logging
_log = logging.getLogger(__name__)


def sanitize_check(text: str) -> str | None:
	"""Checks a ping title to check for invalid characters, or excessive length.

	Returns a string with an error message if an error was detected.
	Returns None if no error detected."""
	if text == "":
		return "You need to specify a valid ping!"
	elif text.count("<@") > 0:
		return "You can't use mentions in a ping!"
	elif len(text) > 20:
		return "Pings must be 20 characters or less!"
	elif text.count(":") > 1:
		return "You can't use emotes in a ping!"
	elif (not check_ascii(text)):
		return "You can't use non-ASCII characters in a ping!"
	elif "," in text:
		return "You cannot use commas in a ping!"
	else:
		return None


def check_ascii(text: str) -> bool:
	"""Checks that a string contains only ASCII characters.

	Returns True if the string only contains ASCII characters.
	Otherwise, returns False"""
	try:
		text.encode("ascii")
	except UnicodeEncodeError: # Non-ASCII characters present
		return False
	else: # Only ASCII characters present
		return True


class Pings(commands.Cog, name = "ping"):
	"""Ping users by a tag."""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		# Initialize our cache variable
		self.pingCache = {}

	async def cog_load(self):
		"""Initializes the cache for the cog"""
		async with self.bot.db.connect() as db:
			# Update the cache for all guilds
			for guild in self.bot.guilds:
				await self._update_ping_cache(db, guild.id)

	async def _update_ping_cache(self, db: blueonblue.db.DBConnection, guildID: int):
		"""Updates the bot's ping cache for a specific guild"""
		self.pingCache[guildID] = (await db.pings.server_pings(guildID))


	async def ping_autocomplete(self, interaction: discord.Interaction, current: str):
		"""Function to handle autocompletion of pings present in a guild"""
		if (interaction.guild is None) or (interaction.guild.id not in self.pingCache):
			# If the guild doesn't exist, or the cache doesn't exist return nothing
			return []
		else:
			# Command called in guild, and cache exists for that guild
			return[app_commands.Choice(name=ping, value=ping) for ping in self.pingCache[interaction.guild.id] if current.lower() in ping.lower()][:25]


	async def create_ping_embed(
			self,
			db: blueonblue.db.DBConnection,
			pingID: int,
			guild: discord.Guild,
			*,
			title_prefix: str | None = None
		) -> discord.Embed:
		"""Creates a "ping info" embed using the name and guild of a ping.

		Parameters
		----------
		db : blueonblue.db.DBConnection
			Blue on blue DB connection
		pingID : int
			Ping ID
		guild : discord.Guild
			Discord guild
		title_prefix : str | None, optional
			Adds a "prefix" to the title of the resulting embed, by default None

		Returns
		-------
		discord.Embed
			Discord embed
		"""
		# Get the name for the ping
		pingName = await db.pings.get_name(pingID)
		pingUserNames = []
		for user in (await db.pings.get_user_ids_by_ping_id(pingID)):
			member = guild.get_member(user)
			if member is not None:
				pingUserNames.append(member.display_name)

		# Get aliases for the ping
		pingAliases = await db.pings.get_alias_names(pingID)

		if title_prefix is not None:
			# Prefix present
			embedTitle = f"{title_prefix} Ping: {pingName} | Users: {len(pingUserNames)}"
		else:
			embedTitle = f"Ping: {pingName} | Users: {len(pingUserNames)}"

		# Now that we have all of our info, start creating our embed
		embed = discord.Embed(
			colour = PING_EMBED_COLOUR,
			title = embedTitle,
			description = f"```{', '.join(pingUserNames)}```"
		)
		if len(pingAliases) > 0:
			embed.add_field(
				name = "Aliases",
				value = f"```{', '.join(pingAliases)}```",
				inline = True
			)
		# Return the generated embed
		return embed


	# Establish app command groups
	pingGroup = app_commands.Group(
		name="ping_manage",
		description="Ping management commands",
		guild_only=True
	)
	pingAdmin = app_commands.Group(
		name="ping_admin",
		description="Administrative ping commands",
		guild_only=True,
		default_permissions=discord.Permissions(manage_messages=True)
	)

	@app_commands.command(name = "ping")
	@app_commands.describe(tag = "Name of ping")
	@app_commands.autocomplete(tag=ping_autocomplete)
	@app_commands.guild_only()
	async def ping(self, interaction: discord.Interaction, tag: str):
		"""Pings all users associated with a specific tag."""
		assert interaction.guild is not None

		san_check = sanitize_check(tag)
		if san_check is not None: # Validate our tag first
			await interaction.response.send_message(f"{interaction.user.mention}: {san_check}")
			return
		tag = tag.casefold() # String searching is case-sensitive

		# Begin our DB section
		async with self.bot.db.connect() as db:
			response = None
			ping_id = await db.pings.get_id(tag, interaction.guild.id) # Get the ID of the ping (or none if it doesn't exist)
			if ping_id is None:
				# Ping does not exist
				response = f"The tag `{tag}` does not exist. Try `/pinglist` for a list of active pings."
			else:
				# Ping exists
				pingUserIDs = await db.pings.get_user_ids_by_ping_id(ping_id)
				pingMentions: list[str] = []
				for userID in pingUserIDs:
					# Try to get the member object from the user ID
					member = interaction.guild.get_member(userID)
					if member is not None:
						# Member is present in the guild
						pingMentions.append(member.mention)

				# Check to see if we have any valid members
				if len(pingMentions) > 0:
					# Ping has users
					# Update the "last used time"
					await db.pings.update_ping_time(tag, interaction.guild.id)
					response = f"{interaction.user.mention} has pinged `{tag}`: " + " ".join(pingMentions) # Create the ping message
				else:
					# Ping is empty
					response = f"Ping `{tag}` appears to be empty. Performing cleanup." # Inform the user
					await db.pings.delete_tag(tag, interaction.guild.id)

			await db.commit() # Write data to the database

			# Send a response to the user.
			await interaction.response.send_message(response)

	@pingGroup.command(name = "me")
	@app_commands.describe(tag = "Name of ping")
	@app_commands.autocomplete(tag=ping_autocomplete)
	async def pingme(self, interaction: discord.Interaction, tag: str):
		"""Adds you to, or removes you from a ping list"""
		assert interaction.guild is not None
		assert isinstance(interaction.user, discord.Member)

		# Begin command function
		san_check = sanitize_check(tag)
		if san_check is not None:
			await interaction.response.send_message(f"{interaction.user.mention}: {san_check}")
			return
		tag = tag.casefold() # String searching is case-sensitive

		# Begin our DB section
		async with self.bot.db.connect() as db:
			response = None
			# Check if the user in in that ping list
			# Get the ping ID, and check if the ping exists
			if await db.pings.exists(tag, interaction.guild.id): # Ping exists
				# Check if the user is in the ping
				if await db.pings.has_user(tag, interaction.guild.id, interaction.user.id):
					# User already in ping
					success = await db.pings.remove_user(tag, interaction.guild.id, interaction.user.id)
					if success:
						response = f"{interaction.user.mention} You have been removed from ping: `{tag}`"
					else:
						response = f"{interaction.user.mention} There was an error removing you from ping: `{tag}`"

					# Check to see if the ping has any users left
					userCount = await db.pings.count_users(tag, interaction.guild.id)
					if userCount <= 0: # No users left in ping.
						await db.pings.delete_tag(tag, interaction.guild.id)
						await self._update_ping_cache(db, interaction.guild.id)
				else:
					# User not already in ping
					success = await db.pings.add_user(tag, interaction.guild.id, interaction.user.id)
					if success:
						response = f"{interaction.user.mention} You have been added to ping: `{tag}`"
					else:
						response = f"{interaction.user.mention} There was an error adding you to ping: `{tag}`"

			else: # Ping does not exist
				# We need to create the ping
				await db.pings.create(tag, interaction.guild.id)
				await self._update_ping_cache(db, interaction.guild.id)
				# Add the user to the ping
				success = await db.pings.add_user(tag, interaction.guild.id, interaction.user.id)
				if success:
					response = f"{interaction.user.mention} You have been added to ping: `{tag}`"
				else:
					response = f"{interaction.user.mention} There was an error adding you to ping: `{tag}`"
			await db.commit() # Write data to the database

			# Send a response to the user.
			await interaction.response.send_message(response)

	@pingGroup.command(name = "list")
	@app_commands.describe(mode = "Operation mode. 'All' lists all pings. 'Me' returns your pings.")
	async def pinglist(self, interaction: discord.Interaction, mode: Literal["all", "me"]="all"):
		"""Lists information about pings"""
		assert interaction.guild is not None

		# Begin our DB section
		async with self.bot.db.connect() as db:
			async with db.connection.cursor() as cursor:
				response = None
				pingEmbed = None
				# We need to figure out what kind of search we need to run
				if mode == "me": # Grab a list of pings that the user is in
					# userID matches author. Get list of ping IDs
					await cursor.execute("SELECT ping_id FROM ping_users WHERE (server_id = :server_id AND user_id = :user_id)",
						{"server_id": interaction.guild.id, "user_id": interaction.user.id})
					pingIDData = await cursor.fetchall() # Get the list of pings from the database
					pingIDs: list[int] = []
					for ping in pingIDData: # Iterate through our response
						if "ping_id" in ping.keys():
							pingIDs.append(ping["ping_id"])
					if len(pingIDs) > 0:
						# User is subscribed to at least one ping
						# Now that we have our ping IDs, we can grab a list of pings
						# This doesn't create an SQL injection vulnerability, despite formatting the query
						# This creates a string that looks like ?,?,?,?... where the number of ? matches the length of the pingID list
						await cursor.execute(f"SELECT ping_name FROM pings WHERE id IN ({','.join('?' * len(pingIDs))})", tuple(pingIDs))
						userPingData = await cursor.fetchall()
						userPings: list[str] = []
						for u in userPingData:
							if "ping_name" in u.keys():
								userPings.append(u["ping_name"])
						# Now we have a list of pings, get ready to print them
						if len(userPings) > 0:
							# We have at least one ping
							pingEmbed = discord.Embed(
								colour = PING_EMBED_COLOUR,
								title = f"Subscribed pings",
								#description = ", ".join(map(lambda n: f"`{n}`", sorted(userPings, key=str.casefold)))
								description = f"```{', '.join(sorted(userPings, key=str.casefold))}```"
							)
							pingEmbed.set_author(
								name = interaction.user.display_name,
								icon_url = interaction.user.display_avatar.url
							)
						else:
							# Found pings, but could not find their names
							response = f"{interaction.user.mention}, there was an error retrieving your pings."
					else:
						# Did not find any pings for the user
						response = f"{interaction.user.mention}, you are not currently subscribed to any pings."

				else:
					# Return all tags (that are not aliases)
					await cursor.execute("SELECT ping_name FROM pings WHERE server_id = :server_id AND alias_for IS NULL", {"server_id": interaction.guild.id})
					pingData = await cursor.fetchall()
					pingResults: list[str] = []
					for p in pingData:
						if "ping_name" in p.keys():
							pingResults.append(p["ping_name"])
					# Now that we have our ping names, we can form our response
					if len(pingResults) > 0:
						# We have at least one ping response
						pingEmbed = discord.Embed(
							colour = PING_EMBED_COLOUR,
							title = f"Ping list for {interaction.guild.name}",
							#description = ", ".join(map(lambda n: f"`{n}`", sorted(pingResults, key=str.casefold)))
							description = f"```{', '.join(sorted(pingResults, key=str.casefold))}```"
						)
					else:
						# No pings defined
						response = "There are currently no pings defined."

				# Send our response
				if pingEmbed is not None:
					await interaction.response.send_message(response, embed = pingEmbed)
				else:
					await interaction.response.send_message(response)
				# We don't need to commit to the DB, since we don't write anything here

	@pingGroup.command(name = "search")
	@app_commands.describe(tag = "The ping to search for")
	@app_commands.autocomplete(tag=ping_autocomplete)
	async def pingsearch(self, interaction: discord.Interaction, tag: str):
		"""Retrieves information about a ping"""
		assert interaction.guild is not None

		tag = tag.casefold() # String searching is case-sensitive

		# Begin our DB section
		async with self.bot.db.connect() as db:
			response = None
			pingEmbed = None # Initialize the ping variable in case we don't set it

			# Search to see if our ping exists
			if (await db.pings.exists(tag, interaction.guild.id)):
				# We found a direct match for that ping
				pingInfo = await db.pings.ping_info(tag, interaction.guild.id)
				alias = None
				if pingInfo.alias is not None:
					# Ping is an alias
					pingID = pingInfo.alias
					alias = await db.pings.get_name(pingID)
				else:
					# Ping is not an alias
					pingID = pingInfo.id
				# Retrieve a list of users subscribed to the referenced ping
				pingUserData = await db.pings.get_user_ids_by_ping_id(pingID)
				pingUserNames = []
				for p in pingUserData:
					member = interaction.guild.get_member(p)
					if member is not None: # If we could find the user
						pingUserNames.append(member.display_name)

				# Check if we have any aliases
				pingAliasNames = await db.pings.get_alias_names(pingID)

				# Check if we have any active users in the ping
				if len(pingUserNames) > 0:
					# We have active users in the ping
					pingEmbed = await self.create_ping_embed(db, pingID, interaction.guild)
				else:
					# No active users in the ping
					if alias is None:
						# Tag is not an alias
						if len(pingAliasNames) > 0: # If we have any aliases, note them
							response = f"Tag `{tag}` (aliases: `{', '.join(pingAliasNames)}`) is a valid ping, but has no users that are currently in this server."
						else:
							response = f"Tag `{tag}` is a valid ping, but has no users that are currently in this server."
					else:
						# Tag is an alias
						response = f"Tag `{tag}` is an alias for `{alias}` which is a valid ping, but has no users that are currently in this server."
			else:
				# No direct match. Search for pings matching that tag.
				pingResults = await db.pings.server_pings(interaction.guild.id, search = tag)
				# Now that we have our ping names, we can form our response
				if len(pingResults) > 0:
					# We have at least one ping response
					pingEmbed = discord.Embed(
						title = f"Ping search for `{tag}`",
						colour = PING_EMBED_COLOUR,
						#description = ", ".join(map(lambda n: f"`{n}`", sorted(pingResults, key=str.casefold)))
						description = f"```{', '.join(sorted(pingResults, key=str.casefold))}```"
					)
				else:
					# We did not find any search results
					response = f"{interaction.user.mention}, there are no tags for the search term: `{tag}`"

			# Send our response
			if pingEmbed is not None:
				await interaction.response.send_message(response, embed = pingEmbed)
			else:
				await interaction.response.send_message(response)

	@pingAdmin.command(name = "alias")
	@app_commands.describe(
		alias = "Alias to create / destroy",
		tag = "Ping to tie the alias to. Leave blank to remove alias."
	)
	@app_commands.autocomplete(tag=ping_autocomplete)
	async def pingalias(self, interaction: discord.Interaction, alias: str, tag: str | None = None):
		"""Creates (or removes) an alias for a ping"""
		assert interaction.guild is not None

		# Start our DB block
		async with self.bot.db.connect() as db:
			# Check if we need to create or destroy the alias
			if tag is not None:
				# Create an alias
				if await db.pings.exists(alias, interaction.guild.id):
					# Ping already exists with this tag
					# Check if the ping is an alias
					if await db.pings.is_alias(alias, interaction.guild.id):
						# Ping is an alias
						# Get the name of the primary ping
						primaryID = await db.pings.get_id(alias, interaction.guild.id)
						if primaryID is not None:
							primaryName = await db.pings.get_name(primaryID)
							await interaction.response.send_message(f"The alias `{alias}` already exists for the ping `{primaryName}`. Please clear the alias before trying to reassign it.", ephemeral=True)
						else:
							await interaction.response.send_message(f"The alias `{alias}` already exists. Please clear the alias before trying to reassign it.", ephemeral=True)
					else:
						# Ping is not an alias
						await interaction.response.send_message(f"A ping already exists with the tag `{alias}`. If you want to turn this tag into an alias, the ping must be deleted first.", ephemeral=True)
				else:
					# Ping does not already exist with the alias tag
					primaryID = await db.pings.get_id(tag, interaction.guild.id)
					if primaryID is not None:
						primaryName = await db.pings.get_name(primaryID)
						await db.pings.create_alias(alias, primaryID, interaction.guild.id)
						await db.commit() # Commit changes
						await interaction.response.send_message(f"Alias `{alias}` created for ping `{primaryName}`")
					else:
						await interaction.response.send_message(f"The ping `{tag}` does not exist. Alias could not be created.", ephemeral=True)

			else:
				# Tag does not exist. Destroy alias
				# Check if it exists first though to display an error message
				aliasExists = await db.pings.is_alias(alias, interaction.guild.id)
				if aliasExists:
					# Alias exists, destroy it
					primaryID = await db.pings.get_id(alias, interaction.guild.id)
					await db.pings.delete_alias(alias, interaction.guild.id)
					await db.commit() # Commit changes
					if primaryID is not None:
						# Primary ping identified
						primaryName = await db.pings.get_name(primaryID)
						# Get aliases for the primary ping
						primaryAliases = await db.pings.get_alias_names(primaryID)
						msg = f"Alias `{alias}` has been removed for ping `{primaryName}`"
						if len(primaryAliases) > 0:
							msg += f" (aliases: `{', '.join(primaryAliases)}`)"
						await interaction.response.send_message(msg)
					else:
						# Primary ping unknown
						await interaction.response.send_message(f"Alias `{alias}` has been removed")

				else:
					await interaction.response.send_message(f"The alias `{alias}` does not exist. If you are trying to create an alias, please specify a ping to bind the alias to.", ephemeral=True)

	@pingAdmin.command(name = "merge")
	@app_commands.describe(
		merge_from = "Ping that will be converted to an alias and merged",
		merge_to = "Ping that will be merged into"
	)
	@app_commands.autocomplete(
		merge_from=ping_autocomplete,
		merge_to=ping_autocomplete
	)
	async def pingmerge(self, interaction: discord.Interaction, merge_from: str, merge_to: str):
		"""Merges two pings"""
		assert interaction.guild is not None

		# Begin our DB section
		async with self.bot.db.connect() as db:
			# Get the names of the pings for our two pings
			fromID = await db.pings.get_id(merge_from, interaction.guild.id)
			if fromID is not None:
				fromName = await db.pings.get_name(fromID)
			else:
				fromName = None

			toID = await db.pings.get_id(merge_to, interaction.guild.id)
			if toID is not None:
				toName = await db.pings.get_name(toID)
			else:
				toName = None

			# Make sure these pings exist
			if fromName is None or fromID is None:
				# "From" ping not found
				await interaction.response.send_message(f"The ping `{merge_from}` does not exist. Please specify a valid ping to be merged.", ephemeral=True)
				return
			if toName is None or toID is None:
				# "To" ping not found
				await interaction.response.send_message(f"The ping `{merge_to}` does not exist. Please specify a valid ping to merge to.", ephemeral=True)
				return

			# Get aliases and usercounts for the pings if they exist
			fromAliases = await db.pings.get_alias_names(fromID)
			fromUserCount = await db.pings.count_active_users(merge_from, interaction.guild)

			toAliases = await db.pings.get_alias_names(toID)
			toUserCount = await db.pings.count_active_users(merge_to, interaction.guild)

			# Start preparing our message
			# Set up our alias texts first
			if len(fromAliases) > 0:
				fromAliasText = f", aliases: `{', '.join(fromAliases)}`"
			else:
				fromAliasText = ""
			if len(toAliases) > 0:
				toAliasText = f", aliases: `{', '.join(toAliases)}`"
			else:
				toAliasText = ""

			# Create our texts for the "from" and "to" pings
			#fromText = f"`{fromName}` (users: `{fromUserCount}`{fromAliasText})"
			#toText = f"`{toName}` (users: `{toUserCount}`{toAliasText})"

			# Set up our message and view
			messageText = f"{interaction.user.mention}, you are about to merge the following pings. This action is **irreversible**."
			view = blueonblue.views.ConfirmViewDanger(interaction.user, confirm="Merge")
			pingEmbeds = [
				await self.create_ping_embed(db, fromID, interaction.guild, title_prefix="Merge from"),
				await self.create_ping_embed(db, toID, interaction.guild, title_prefix="Merge to")
			]
			await interaction.response.send_message(messageText, view = view, embeds=pingEmbeds)
			view.message = await interaction.original_response()
			# Wait for the view to finish
			await view.wait()

			# Once we have a response, continue
			if view.response:
				# Action confirmed
				# We need to first clear any duplicate users from the ping to be merged
				fromUsers = await db.pings.get_user_ids_by_ping_id(fromID)
				toUsers = await db.pings.get_user_ids_by_ping_id(toID)
				deleteUsers = []
				# Get a list of users that need to be cleared from the "from" ping
				for u in fromUsers:
					if u in toUsers:
						deleteUsers.append(u)
				# Remove duplicate users from the "from" ping
				for d in deleteUsers:
					await db.pings.remove_user_by_id(fromID, d)
				# Now that our duplicate users have been removed from their pings, migrate all users and aliases
				await db.pings.migrate_ping(fromID, toID)
				# Delete the old ping
				await db.pings.delete_tag(fromName, interaction.guild.id)
				# Create an alias linking the old ping to the new ping
				await db.pings.create_alias(fromName, toID, interaction.guild.id)

				# Update the cache
				await self._update_ping_cache(db, interaction.guild.id)

				# Commit changes
				await db.commit()

				# Get new information about our final ping
				toAliasesNew = await db.pings.get_alias_names(toID)
				toTextNew = f"`{toName}`"
				if len(toAliasesNew) > 0:
					toTextNew += f" (aliases: `{', '.join(toAliasesNew)}`)"
				# Send our confirmation
				await interaction.followup.send(f"Ping `{fromName}` has been successfully merged into {toTextNew}.")

			elif not view.response:
				# Action cancelled
				await interaction.followup.send(f"Merge action cancelled.")

			else:
				# Notify the user that the action timed out
				await interaction.followup.send("Pending ping merge has timed out", ephemeral=True)

	@pingAdmin.command(name = "delete")
	@app_commands.describe(tag = "Ping to delete")
	@app_commands.autocomplete(tag=ping_autocomplete)
	async def pingdelete(self, interaction: discord.Interaction, tag: str):
		"""Forcibly deletes a ping"""
		assert interaction.guild is not None

		# We need to search for the ping
		# Begin our DB section
		async with self.bot.db.connect() as db:
			# Get our ping ID
			pingID = await db.pings.get_id(tag, interaction.guild.id)
			# Make sure we actually have a ping
			if pingID is None:
				await interaction.response.send_message(f"I could not find a ping for the tag: `{tag}`", ephemeral=True)
				return
			# Get the name of our main ping (in case our given tag was an alias)
			pingName = await db.pings.get_name(pingID)
			if pingName is None:
				await interaction.response.send_message(f"I could not find a ping for the tag: `{tag}`", ephemeral=True)
				return

			# Set up our message
			msg = f"{interaction.user.mention}, you are about to delete the following ping. This action is **irreversible**."
			pingEmbed = await self.create_ping_embed(db, pingID, interaction.guild)

			view = blueonblue.views.ConfirmViewDanger(interaction.user, confirm="Delete")
			await interaction.response.send_message(msg, embed = pingEmbed, view = view)
			view.message = await interaction.original_response()
			await view.wait()

			# Once we have a response, continue
			if view.response:
				# Action confirmed
				# Pretty straightforward, just delete the ping. SQLite foreign keys should handle the rest.
				await db.pings.delete_tag(pingName, interaction.guild.id)
				await self._update_ping_cache(db, interaction.guild.id) # Update the cache
				await interaction.followup.send(f"The ping `{pingName}` has been permanently deleted.")
			elif not view.response:
				# Action cancelled
				await interaction.followup.send(f"Delete action cancelled.")
			else:
				# Notify the user that the action timed out
				await interaction.followup.send("Pending ping delete has timed out", ephemeral=True)

	@pingAdmin.command(name = "purge")
	@app_commands.describe(
		user_threshold = "Threshold below which pings will be subject to deletion",
		days_since_last_use = "Pings last used greater than this number of days ago will be subject to deletion"
	)
	async def pingpurge(self, interaction: discord.Interaction, user_threshold: int=5, days_since_last_use: int=30):
		"""Purges pings that are inactive, and below a specified user count."""
		assert interaction.guild is not None

		# Start our DB block
		async with self.bot.db.connect() as db:
			# Start getting a list of all pings that are old enough to be up for deletion
			# Get a timestamp of the specified time
			timeThreshold = discord.utils.utcnow() - timedelta(days=days_since_last_use)

			# Get a list of pings that haven't been used recently
			pingNames = []
			for p in (await db.pings.server_pings(interaction.guild.id, beforeTime = timeThreshold)):
				# Ping names cannot be null/None
				if (await db.pings.count_active_users(p, interaction.guild) < user_threshold):
					pingNames.append(p)
			# Now that we have a list of ping names, we can continue
			if len(pingNames) > 0:
				# At least one ping was found
				# Prepare our message and view
				#msg = f"{ctx.author.mention}, you are about to permanently delete the following pings due to inactivity (less than `{user_threshold}` users, last used more than `{days_since_last_use}` days ago). "\
				#	f"This action is **irreversible**.\n```{', '.join(pingNames)}```"
				msg = f"{interaction.user.mention}, you are about to permanently delete the following pings due to inactivity (less than `{user_threshold}` users, last used more than `{days_since_last_use}` days ago)."
				pingEmbed = discord.Embed(
					title = f"Pings pending deletion",
					colour = PING_EMBED_COLOUR,
					#description = ", ".join(map(lambda n: f"`{n}`", sorted(pingNames, key=str.casefold)))
					description = f"```{', '.join(sorted(pingNames, key=str.casefold))}```"
				)
				view = blueonblue.views.ConfirmViewDanger(interaction.user, confirm="Purge")
				await interaction.response.send_message(msg, embed = pingEmbed, view = view)
				view.message = await interaction.original_response()
				await view.wait()

				# Handle the response
				if view.response:
					# Action confirmed
					# Delete all pings that met our search criteria
					for p in pingNames:
						await db.pings.delete_tag(p, interaction.guild.id)
					# Update the cache
					await self._update_ping_cache(db, interaction.guild.id)
					await interaction.followup.send(f"Pings have been successfully purged.")
				elif not view.response:
					# Action cancelled
					await interaction.followup.send(f"Purge action cancelled.")
				else:
					# Notify the user that the action timed out
					await interaction.followup.send("Pending ping purge has timed out", ephemeral=True)

			else:
				# Did not find any pings matching search criteria
				await interaction.response.send_message(f"{interaction.user.mention}, there were no pings found with fewer than `{user_threshold}` users that were last used more than `{days_since_last_use}` days ago.")

	@commands.Cog.listener()
	async def on_ready(self):
		"""Update our ping cache on reconnection.
		This needs to wait until the bot is ready, since it relies on being able to grab a list of guilds that the bot is in."""
		async with self.bot.db.connect() as db:
			# Update the cache for all guilds
			for guild in self.bot.guilds:
				await self._update_ping_cache(db, guild.id)

async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Pings(bot))
