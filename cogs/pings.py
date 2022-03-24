import discord
from discord import app_commands
from discord.ext import commands

import asqlite
from datetime import datetime, timezone, timedelta
from typing import Literal, List

import blueonblue

import logging
log = logging.getLogger("blueonblue")

# Define our ping embed colour
PING_EMBED_COLOUR = 0xFFA500 # Orange

def sanitize_check(text: str) -> str:
	"""Checks a ping title to check for invalid characters, or excessive length.

	Returns a string with an error message if an error was detected.
	Returns None if no error detected."""
	if text == "":
		return "You need to specify a valid ping!"
	elif text.count("<@") > 0:
		return "You can't use mentiones in a ping!"
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

async def ping_exists(tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> bool:
	"""Check if a ping exists in the database for a specific guild.
	If the ping exists, returns True. Otherwise returns False.
	"""
	tag = tag.casefold() # Ensure that our ping is lowercase
	await cursor.execute("SELECT id FROM pings WHERE server_id = :server_id AND ping_name = :ping", {"server_id": guild.id, "ping": tag})
	ping = await cursor.fetchone()
	if ping is None: # Ping does not exist
		return False
	else: # Ping exists
		return True

async def ping_is_alias(tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> bool:
	"""Gets the alias reference for a ping.
	Returns True if the ping exists AND is an alias. Otherwise returns False."""
	tag = tag.casefold()
	await cursor.execute("SELECT alias_for FROM pings WHERE server_id = :server_id AND ping_name = :ping AND alias_for IS NOT NULL", {"server_id": guild.id, "ping": tag})
	is_alias = await cursor.fetchone()
	if is_alias is None: # Alias is null, or ping doesn't exist
		return False
	else: # Alias is not null, and therefore exists
		return True

async def ping_get_id(tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> int | None:
	"""Gets the ID reference for a ping.
	If the ping is an alias, get the alias ID. Otherwise, get the ping ID.
	Returns None if the ping was not found."""
	tag = tag.casefold()
	await cursor.execute("SELECT id, alias_for FROM pings WHERE server_id = :server_id AND ping_name = :ping", {"server_id": guild.id, "ping": tag})
	ping = await cursor.fetchone()

	if ping is None: # Ping does not exist
		return None
	else: # Ping exists
		if ping["alias_for"] is not None:
			return ping["alias_for"]
		else:
			return ping["id"]

async def ping_get_name(id: int, cursor: asqlite.Cursor) -> str | None:
	"""Gets the name of a ping from its ID.
	If the ping cannot be found, returns None."""
	await cursor.execute("SELECT ping_name FROM pings WHERE id = :id", {"id": id})
	pingData = await cursor.fetchone()

	if pingData is None: # Ping does not exist
		return None
	else: # Ping exists
		if pingData["ping_name"] is not None:
			return pingData["ping_name"]
		else: # We couldn't find the ping name
			return None

async def ping_get_alias_names(id: int, cursor: asqlite.Cursor) -> List[str]:
	"""Gets the names of all aliases for a given ping.
	Returns a list containing all names.
	When no aliases are present, the returned list will be empty."""
	aliasNames = []
	await cursor.execute("SELECT ping_name FROM pings WHERE alias_for = :pingID", {"pingID": id})
	aliasData = await cursor.fetchall()
	for a in aliasData:
		aliasNames.append(a["ping_name"])
	return aliasNames

async def ping_create(tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> None:
	"""Creates a ping in the database.
	Use ping_exists() to check if the ping exists or not first."""
	tag = tag.casefold()
	time = round(datetime.now(timezone.utc).timestamp()) # Get the current time in timestamp format
	await cursor.execute("INSERT INTO pings (server_id, ping_name, last_used_time) VALUES (:server_id, :ping, :time)",
		{"server_id": guild.id, "ping": tag, "time": time})

async def ping_delete(tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> None:
	"""Removes a ping from the database"""
	tag = tag.casefold()
	ping_id = await ping_get_id(tag, guild, cursor)
	await cursor.execute("DELETE FROM pings WHERE (server_id = :server_id AND id = :ping)", {"server_id": guild.id, "ping": ping_id})

async def ping_create_alias(tag: str, pingID: int, guild: discord.Guild, cursor: asqlite.Cursor) -> None:
	"""Creates an alias for an existing ping"""
	tag = tag.casefold()
	await cursor.execute("INSERT INTO pings (server_id, ping_name, alias_for) VALUES (:server_id, :alias, :pingID)",
		{"server_id": guild.id, "alias": tag, "pingID": pingID})

async def ping_delete_alias(tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> None:
	"""Deletes an alias for an existing ping"""
	tag = tag.casefold()
	await cursor.execute("DELETE FROM pings WHERE (server_id = :server_id AND ping_name = :tag AND alias_for IS NOT NULL)",
		{"server_id": guild.id, "tag": tag})

async def ping_update_time(tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> bool:
	"""Updates the "last used time" of a ping in the database."""
	tag = tag.casefold()
	time = round(datetime.now(timezone.utc).timestamp()) # Get the current time in timestamp format
	ping_id = await ping_get_id(tag, guild, cursor)
	await cursor.execute("UPDATE pings SET last_used_time = :time WHERE id = :ping", {"time": time, "ping": ping_id}) # Ping IDs are globally unique

async def ping_add_user(tag: str, guild: discord.Guild, user: discord.Member, cursor: asqlite.Cursor) -> bool:
	"""Adds a user to a ping.
	Checks if the ping is an alias, and handles it accordingly.
	Returns False if an error was encountered."""
	tag = tag.casefold()
	# Get the ID of the ping
	ping_id = await ping_get_id(tag, guild, cursor)
	if ping_id is not None: # Ping exists.
		await cursor.execute("INSERT OR REPLACE INTO ping_users (server_id, ping_id, user_id) VALUES (:server_id, :ping, :user_id)",
			{"server_id": guild.id, "ping": ping_id, "user_id": user.id})
		return True
	else: # Ping does not exist. Could not add user to ping.
		return False

async def ping_remove_user(tag: str, guild: discord.Guild, user: discord.Member, cursor: asqlite.Cursor) -> bool:
	"""Removes a user from a ping.
	Checks if the ping is an alias, and handles it accordingly.
	Returns False if an error was encountered."""
	tag = tag.casefold()
	# Get the ID of the ping
	ping_id = await ping_get_id(tag, guild, cursor)
	if ping_id is not None: # Ping exists.
		# This doesn't actually need a server reference, since ping IDs must be globally unique.
		await cursor.execute("DELETE FROM ping_users WHERE (ping_id = :ping AND user_id = :user_id)",
			{"ping": ping_id, "user_id": user.id})
		return True
	else: # Ping does not exist. Could not remove user from ping.
		return False

async def ping_remove_user_by_id(pingID: int, userID: int, cursor: asqlite.Cursor) -> bool:
	"""Removes a user from a ping.
	Requires a ping ID and user ID
	Returns False if an error was encountered."""
	# This doesn't need a server reference, since ping IDs must be globally unique.
	await cursor.execute("DELETE FROM ping_users WHERE (ping_id = :ping AND user_id = :user_id)",
		{"ping": pingID, "user_id": userID})
	return True

async def ping_has_user(tag: str, guild: discord.Guild, user: discord.Member, cursor: asqlite.Cursor) -> bool:
	"""Checks if a user is already in a ping.
	Returns True if the user is in the ping.
	Otherwise, returns False."""
	tag = tag.casefold()
	# Get the ID of the ping
	ping_id = await ping_get_id(tag, guild, cursor)
	if ping_id is not None: # Ping exists.
		await cursor.execute("SELECT user_id FROM ping_users WHERE server_id = :server_id AND ping_id = :ping AND user_id = :user_id",
			{"server_id": guild.id, "ping": ping_id, "user_id": user.id})
		userPing = await cursor.fetchone()
		if userPing is not None: # User exists in ping.
			return True
		else: # Ping exists. User is not in ping.
			return False
	else: # Ping does not exist. User could not be in ping.
		return False

async def ping_count_users(tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> int:
	"""Returns the number of users present in a ping.
	Pings that don't exist will return -1."""
	tag = tag.casefold()
	# Get the ID of the ping
	ping_id = await ping_get_id(tag, guild, cursor)
	if ping_id is None: # Ping does not exist
		return -1
	else: # Ping exists
		await cursor.execute("SELECT COUNT(*) FROM ping_users WHERE server_id = :server_id AND ping_id = :ping", {"server_id": guild.id, "ping": ping_id})
		userCount = await cursor.fetchone()
		return userCount[0] # This entry has to be on the return. The await can't be subscripted.

async def ping_count_active_users(tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> int:
	"""Returns the number of users present in a ping that are currently in the server.
	This is slower than ping_count_users().
	Pings that don't exist will return -1."""
	tag = tag.casefold()
	# Get the ID of the ping
	ping_id = await ping_get_id(tag, guild, cursor)
	if ping_id is None: # Ping does not exist
		return -1
	else: # Ping exists
		await cursor.execute("SELECT user_id FROM ping_users WHERE ping_id = :ping", {"ping": ping_id})
		userIDs = await cursor.fetchall()
		userCount = 0 # Start our count
		for u in userIDs:
			user = guild.get_member(u["user_id"])
			if user is not None:
				userCount += 1 # Increment usercount by 1
		# Return our usercount
		return userCount

async def ping_get_user_ids_by_id(id: int, cursor: asqlite.Cursor) -> list[int]:
	"""Returns a list of user IDs present in a ping by using the ping ID.
	Empty or invalid pings will return an empty list."""
	userIDList = [] # Create our empty user ID list
	# Grab data from the DB
	await cursor.execute("SELECT user_id FROM ping_users WHERE ping_id = :ping", {"ping": id})
	pingData = await cursor.fetchall()
	for p in pingData:
		if "user_id" in p.keys():
			userIDList.append(p["user_id"])
	# Return our list of userIDs
	return userIDList

async def create_ping_embed(tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> discord.Embed | None:
	"""Creates a "ping info" embed using the name and guild of a ping."""
	tag = tag.casefold()
	# Get the ID of the ping
	pingID = await ping_get_id(tag, guild, cursor)
	# If the ping was not found
	if pingID is None:
		return None
	else:
		# We have a ping ID
		return await create_ping_embed_from_id(pingID, cursor)

async def create_ping_embed_from_id(
		id: int,
		guild: discord.Guild,
		cursor: asqlite.Cursor,
		*,
		title_prefix: str = None
	) -> discord.Embed | None:
	"""Creates a "ping info" embed using the ID of a ping.
	"title_prefix" is an optional argument that adds a "prefix" to the title of the resulting embed."""
	# Get the name of the ping
	pingName = await ping_get_name(id, cursor)
	if pingName is None:
		return None
	# Get user names
	pingUserIDs = await ping_get_user_ids_by_id(id, cursor)
	pingUserNames = []
	for user in pingUserIDs:
		member = guild.get_member(user)
		if member is not None:
			pingUserNames.append(member.display_name)
	# Get aliases for the ping
	pingAliases = await ping_get_alias_names(id, cursor)

	# Convert pingUsers and pingAliases to the format we need for the embed
	# This put backticks around each entry in the array
	#pingUserTexts = list(map(lambda n: f"`{n}`", pingUserNames))
	#pingAliasTexts = list(map(lambda n: f"`{n}`", pingAliases))

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

class Pings(app_commands.Group, commands.Cog, name = "ping"):
	"""Ping users by a tag."""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		# Initialize our cache variable
		self.pingCache = {}

	async def cog_load(self):
		"""Initializes the database for the cog.
		Creates the tables if they don't exist."""
		async with self.bot.dbConnection.cursor() as cursor:
			# Create the tables if they do not exist
			await cursor.execute("CREATE TABLE if NOT EXISTS pings (\
				id INTEGER PRIMARY KEY AUTOINCREMENT,\
				server_id INTEGER NOT NULL,\
				ping_name TEXT NOT NULL,\
				last_used_time INTEGER,\
				alias_for INTEGER,\
				UNIQUE(server_id,ping_name),\
				FOREIGN KEY (alias_for) REFERENCES pings (id) ON DELETE CASCADE)")
			await cursor.execute("CREATE TABLE if NOT EXISTS ping_users (\
				server_id INTEGER NOT NULL,\
				ping_id INTEGER,\
				user_id INTEGER NOT NULL,\
				UNIQUE(server_id,ping_id,user_id),\
				FOREIGN KEY (ping_id) REFERENCES pings (id) ON DELETE CASCADE)")
			await self.bot.dbConnection.commit()

			# Update the cache for all guilds
			for guild in self.bot.guilds:
				await self._update_ping_cache(guild, cursor)

	async def _update_ping_cache(self, guild: discord.Guild, cursor: asqlite.Cursor):
		"""Updates the bot's ping cache for a specific guild"""
		await cursor.execute("SELECT ping_name FROM pings WHERE server_id = :server_id AND alias_for IS NULL", {"server_id": guild.id})
		pingData = await cursor.fetchall()
		pingResults: list[str] = []
		for p in pingData:
			if "ping_name" in p.keys():
				pingResults.append(p["ping_name"])

		# Set the value for the cache
		self.pingCache[guild.id] = pingResults

	async def ping_autocomplete(self, interaction: discord.Interaction, current: str):
		"""Function to handle autocompletion of pings present in a guild"""
		if (interaction.guild is None) or (interaction.guild.id not in self.pingCache):
			# If the guild doesn't exist, or the cache doesn't exist return nothing
			return []
		else:
			# Command called in guild, and cache exists for that guild
			return[app_commands.Choice(name=ping, value=ping) for ping in self.pingCache[interaction.guild.id] if current.lower() in ping.lower()][:25]

	@app_commands.command(name = "ping")
	@app_commands.describe(tag = "Name of ping")
	@app_commands.autocomplete(tag=ping_autocomplete)
	async def ping(self, interaction: discord.Interaction, tag: str):
		"""Pings all users associated with a specific tag."""
		san_check = sanitize_check(tag)
		if san_check is not None: # Validate our tag first
			await interaction.response.send_message(f"{interaction.user.mention}: {san_check}")
			return
		tag = tag.casefold() # String searching is case-sensitive

		# Begin our DB section
		async with self.bot.dbConnection.cursor() as cursor:
			response = None
			ping_id = await ping_get_id(tag, interaction.guild, cursor) # Get the ID of the ping (or none if it doesn't exist)
			if ping_id is None:
				# Ping does not exist
				response = f"The tag `{tag}` does not exist. Try `/pinglist` for a list of active pings."
			else:
				# Ping exists
				pingUserIDs = await ping_get_user_ids_by_id(ping_id, cursor)
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
					await ping_update_time(tag, interaction.guild, cursor)
					response = f"{interaction.user.mention} has pinged `{tag}`: " + " ".join(pingMentions) # Create the ping message
				else:
					# Ping is empty
					response = f"Ping `{tag}` appears to be empty. Performing cleanup." # Inform the user
					await ping_delete(tag, interaction.guild, cursor)

			await self.bot.dbConnection.commit() # Write data to the database

			# Send a response to the user.
			await interaction.response.send_message(response)

	@app_commands.command(name = "me")
	@app_commands.describe(tag = "Name of ping")
	@app_commands.autocomplete(tag=ping_autocomplete)
	async def pingme(self, interaction: discord.Interaction, tag: str):
		"""Adds you to, or removes you from a ping list"""

		# Begin command function
		san_check = sanitize_check(tag)
		if san_check is not None:
			await interaction.response.send_message(f"{interaction.user.mention}: {san_check}")
			return
		tag = tag.casefold() # String searching is case-sensitive

		# Begin our DB section
		async with self.bot.dbConnection.cursor() as cursor:
			response = None
			# Check if the user in in that ping list
			# Get the ping ID, and check if the ping exists
			if await ping_exists(tag, interaction.guild, cursor): # Ping exists
				# Check if the user is in the ping
				if await ping_has_user(tag, interaction.guild, interaction.user, cursor):
					# User already in ping
					success = await ping_remove_user(tag, interaction.guild, interaction.user, cursor)
					if success:
						response = f"{interaction.user.mention} You have been removed from ping: `{tag}`"
					else:
						response = f"{interaction.user.mention} There was an error removing you from ping: `{tag}`"

					# Check to see if the ping has any users left
					userCount = await ping_count_users(tag, interaction.guild, cursor)
					if userCount <= 0: # No users left in ping.
						await ping_delete(tag, interaction.guild, cursor)
						await self._update_ping_cache(interaction.guild, cursor)
				else:
					# User not already in ping
					success = await ping_add_user(tag, interaction.guild, interaction.user, cursor)
					if success:
						response = f"{interaction.user.mention} You have been added to ping: `{tag}`"
					else:
						response = f"{interaction.user.mention} There was an error adding you to ping: `{tag}`"

			else: # Ping does not exist
				# We need to create the ping
				await ping_create(tag, interaction.guild, cursor)
				await self._update_ping_cache(interaction.guild, cursor)
				# Add the user to the ping
				success = await ping_add_user(tag, interaction.guild, interaction.user, cursor)
				if success:
					response = f"{interaction.user.mention} You have been added to ping: `{tag}`"
				else:
					response = f"{interaction.user.mention} There was an error adding you to ping: `{tag}`"
			await self.bot.dbConnection.commit() # Write data to the database

			# Send a response to the user.
			await interaction.response.send_message(response)

	@app_commands.command(name = "list")
	@app_commands.describe(mode = "Operation mode. 'All' lists all pings. 'Me' returns your pings.")
	async def pinglist(self, interaction: discord.Interaction, mode: Literal["all", "me"]="all"):
		"""Lists information about pings"""

		# Begin our DB section
		async with self.bot.dbConnection.cursor() as cursor:
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
							icon_url = interaction.user.avatar.url
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
			await interaction.response.send_message(response, embed = pingEmbed)
			# We don't need to commit to the DB, since we don't write anything here

	@app_commands.command(name = "search")
	@app_commands.describe(tag = "The ping to search for")
	@app_commands.autocomplete(tag=ping_autocomplete)
	async def pingsearch(self, interaction: discord.Interaction, tag: str):
		"""Retrieves information about a ping"""
		tag = tag.casefold() # String searching is case-sensitive

		# Begin our DB section
		async with self.bot.dbConnection.cursor() as cursor:
			response = None
			# Search to see if our ping exists
			await cursor.execute("SELECT id, alias_for FROM pings WHERE server_id = :server_id AND ping_name = :ping", {"server_id": interaction.guild.id, "ping": tag})
			pingInfo = await cursor.fetchone()
			pingEmbed = None # Initialize the ping variable in case we don't set it
			if pingInfo is not None:
				# We found a direct match for that ping
				alias = None
				if pingInfo["alias_for"] is not None:
					# Ping is an alias
					pingID = pingInfo["alias_for"]
					alias = await ping_get_name(pingID, cursor)
				else:
					# Ping is not an alias
					pingID = pingInfo["id"]
				# Retrieve a list of users subscribed to the referenced ping
				pingUserData = await ping_get_user_ids_by_id(pingID, cursor)
				pingUserNames = []
				for p in pingUserData:
					member = interaction.guild.get_member(p)
					if member is not None: # If we could find the user
						pingUserNames.append(member.display_name)

				# Check if we have any aliases
				pingAliasNames = await ping_get_alias_names(pingID, cursor)

				# Check if we have any active users in the ping
				if len(pingUserNames) > 0:
					# We have active users in the ping
					pingEmbed = await create_ping_embed_from_id(pingID, interaction.guild, cursor)
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
				# This can't be used with a dict for parameters, since the LIKE statement won't be happy with it
				await cursor.execute("SELECT ping_name FROM pings WHERE server_id = ? AND ping_name LIKE ? AND alias_for IS NULL", (interaction.guild.id,"%"+tag+"%",))
				pingData = await cursor.fetchall()
				pingResults: list[str] = []
				for p in pingData:
					if p["ping_name"] is not None: # Ensure that we have a ping name
						pingResults.append(p["ping_name"])
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
			await interaction.response.send_message(response, embed = pingEmbed)

	#pingManageGroup = app_commands.Group(name="ping_manage", description="Commands to manage the ping list")

	@app_commands.command(name = "alias")
	@app_commands.describe(alias = "Alias to create / destroy")
	@app_commands.describe(tag = "Ping to tie the alias to. Leave blank to remove alias.")
	@app_commands.autocomplete(tag=ping_autocomplete)
	async def pingalias(self, interaction: discord.Interaction, alias: str, tag: str = None):
		"""Creates (or removes) an alias for a ping"""
		# Start our DB block
		async with self.bot.dbConnection.cursor() as cursor:
			# Check if we need to create or destroy the alias
			if tag is not None:
				# Create an alias
				if await ping_exists(alias, interaction.guild, cursor):
					# Ping already exists with this tag
					# Check if the ping is an alias
					if await ping_is_alias(alias, interaction.guild, cursor):
						# Ping is an alias
						# Get the name of the primary ping
						primaryID = await ping_get_id(alias, interaction.guild, cursor)
						if primaryID is not None:
							primaryName = await ping_get_name(primaryID, cursor)
							await interaction.response.send_message(f"The alias `{alias}` already exists for the ping `{primaryName}`. Please clear the alias before trying to reassign it.", ephemeral=True)
						else:
							await interaction.response.send_message(f"The alias `{alias}` already exists. Please clear the alias before trying to reassign it.", ephemeral=True)
					else:
						# Ping is not an alias
						await interaction.response.send_message(f"A ping already exists with the tag `{alias}`. If you want to turn this tag into an alias, the ping must be deleted first.", ephemeral=True)
				else:
					# Ping does not already exist with the alias tag
					primaryID = await ping_get_id(tag, interaction.guild, cursor)
					if primaryID is not None:
						primaryName = await ping_get_name(primaryID, cursor)
						await ping_create_alias(alias, primaryID, interaction.guild, cursor)
						await self.bot.dbConnection.commit() # Commit changes
						await interaction.response.send_message(f"Alias `{alias}` created for ping `{primaryName}`")
					else:
						await interaction.response.send_message(f"The ping `{tag}` does not exist. Alias could not be created.", ephemeral=True)

			else:
				# Tag does not exist. Destroy alias
				# Check if it exists first though to display an error message
				aliasExists = await ping_is_alias(alias, interaction.guild, cursor)
				if aliasExists:
					# Alias exists, destroy it
					primaryID = await ping_get_id(alias, interaction.guild, cursor)
					await ping_delete_alias(alias, interaction.guild, cursor)
					await self.bot.dbConnection.commit() # Commit changes
					if primaryID is not None:
						# Primary ping identified
						primaryName = await ping_get_name(primaryID, cursor)
						# Get aliases for the primary ping
						primaryAliases = await ping_get_alias_names(primaryID, cursor)
						msg = f"Alias `{alias}` has been removed for ping `{primaryName}`"
						if len(primaryAliases) > 0:
							msg += f" (aliases: `{', '.join(primaryAliases)}`)"
						await interaction.response.send_message(msg)
					else:
						# Primary ping unknown
						await interaction.response.send_message(f"Alias `{alias}` has been removed")

				else:
					await interaction.response.send_message(f"The alias `{alias}` does not exist. If you are trying to create an alias, please specify a ping to bind the alias to.", ephemeral=True)

	@app_commands.command(name = "merge")
	@app_commands.describe(merge_from = "Ping that will be converted to an alias and merged")
	@app_commands.describe(merge_to = "Ping that will be merged into")
	@app_commands.autocomplete(merge_from=ping_autocomplete)
	@app_commands.autocomplete(merge_to=ping_autocomplete)
	async def pingmerge(self, interaction: discord.Interaction, merge_from: str, merge_to: str):
		"""Merges two pings"""

		# Begin our DB section
		async with self.bot.dbConnection.cursor() as cursor:
			# Get the names of the pings for our two pings
			fromID = await ping_get_id(merge_from, interaction.guild, cursor)
			fromName = await ping_get_name(fromID, cursor)

			toID = await ping_get_id(merge_to, interaction.guild, cursor)
			toName = await ping_get_name(toID, cursor)

			# Make sure these pings exist
			if fromName is None:
				# "From" ping not found
				await interaction.response.send_message(f"The ping `{merge_from}` does not exist. Please specify a valid ping to be merged.", ephemeral=True)
				return
			if toName is None:
				# "To" ping not found
				await interaction.response.send_message(f"The ping `{merge_to}` does not exist. Please specify a valid ping to merge to.", ephemeral=True)
				return

			# Get aliases and usercounts for the pings if they exist
			fromAliases = await ping_get_alias_names(fromID, cursor)
			fromUserCount = await ping_count_active_users(merge_from, interaction.guild, cursor)

			toAliases = await ping_get_alias_names(toID, cursor)
			toUserCount = await ping_count_active_users(merge_to, interaction.guild, cursor)

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
				await create_ping_embed_from_id(fromID, interaction.guild, cursor, title_prefix="Merge from"),
				await create_ping_embed_from_id(toID, interaction.guild, cursor, title_prefix="Merge to")
			]
			await interaction.response.send_message(messageText, view = view, embeds=pingEmbeds)
			view.message = await interaction.original_message()
			# Wait for the view to finish
			await view.wait()

			# Once we have a response, continue
			if view.response:
				# Action confirmed
				# We need to first clear any duplicate users from the ping to be merged
				fromUsers = await ping_get_user_ids_by_id(fromID, cursor)
				toUsers = await ping_get_user_ids_by_id(toID, cursor)
				deleteUsers = []
				# Get a list of users that need to be cleared from the "from" ping
				for u in fromUsers:
					if u in toUsers:
						deleteUsers.append(u)
				# Remove duplicate users from the "from" ping
				for d in deleteUsers:
					await ping_remove_user_by_id(fromID, d, cursor)
				# Now that our duplicate users have been removed from their pings, migrate all users and aliases
				await cursor.execute("UPDATE ping_users SET ping_id = :toID WHERE ping_id = :fromID", {"toID": toID, "fromID": fromID})
				# Migrate existing aliases
				await cursor.execute("UPDATE pings SET alias_for = :toID WHERE alias_for = :fromID", {"toID": toID, "fromID": fromID})
				# Delete the old ping
				await ping_delete(fromName, interaction.guild, cursor)
				# Create an alias linking the old ping to the new ping
				await ping_create_alias(fromName, toID, interaction.guild, cursor)

				# Update the cache
				await self._update_ping_cache(interaction.guild, cursor)

				# Commit changes
				await self.bot.dbConnection.commit()

				# Get new information about our final ping
				toAliasesNew = await ping_get_alias_names(toID, cursor)
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

	@app_commands.command(name = "delete")
	@app_commands.describe(tag = "Ping to delete")
	@app_commands.autocomplete(tag=ping_autocomplete)
	async def pingdelete(self, interaction: discord.Interaction, tag: str):
		"""Forcibly deletes a ping"""

		# We need to search for the ping
		# Begin our DB section
		async with self.bot.dbConnection.cursor() as cursor:
			# Get our ping ID
			pingID = await ping_get_id(tag, interaction.guild, cursor)
			# Make sure we actually have a ping
			if pingID is None:
				await interaction.response.send_message(f"I could not find a ping for the tag: `{tag}`", ephemeral=True)
				return
			# Get the name of our main ping (in case our given tag was an alias)
			pingName = await ping_get_name(pingID, cursor)

			# Set up our message
			msg = f"{interaction.user.mention}, you are about to delete the following ping. This action is **irreversible**."
			pingEmbed = await create_ping_embed_from_id(pingID, interaction.guild, cursor)

			view = blueonblue.views.ConfirmViewDanger(interaction.user, confirm="Delete")
			await interaction.response.send_message(msg, embed = pingEmbed, view = view)
			view.message = await interaction.original_message()
			await view.wait()

			# Once we have a response, continue
			if view.response:
				# Action confirmed
				# Pretty straightforward, just delete the ping. SQLite foreign keys should handle the rest.
				await ping_delete(pingName, interaction.guild, cursor)
				await self._update_ping_cache(interaction.guild, cursor) # Update the cache
				await interaction.followup.send(f"The ping `{pingName}` has been permanently deleted.")
			elif not view.response:
				# Action cancelled
				await interaction.followup.send(f"Delete action cancelled.")
			else:
				# Notify the user that the action timed out
				await interaction.followup.send("Pending ping delete has timed out", ephemeral=True)

	@app_commands.command(name = "purge")
	@app_commands.describe(user_threshold = "Threshold below which pings will be subject to deletion")
	@app_commands.describe(days_since_last_use = "Pings last used greater than this number of days ago will be subject to deletion")
	async def pingpurge(self, interaction: discord.Interaction, user_threshold: int=5, days_since_last_use: int=30):
		"""Purges pings that are inactive, and below a specified user count."""

		# Start our DB block
		async with self.bot.dbConnection.cursor() as cursor:
			# Start getting a list of all pings that are old enough to be up for deletion
			# Get a timestamp of the specified time
			timeThreshold = discord.utils.utcnow() - timedelta(days=days_since_last_use)
			timeStamp = round(timeThreshold.timestamp())
			# Use this timestamp to search for pings
			await cursor.execute("SELECT ping_name FROM pings WHERE server_id = :server_id AND last_used_time < :time AND alias_for IS NULL",
				{"server_id": interaction.guild.id, "time": timeStamp})
			pingData = await cursor.fetchall()
			pingNames = []
			for p in pingData:
				# Ping names cannot be null/None
				if (await ping_count_active_users(p["ping_name"], interaction.guild, cursor) < user_threshold):
					pingNames.append(p["ping_name"])
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
				view.message = await interaction.original_message()
				await view.wait()

				# Handle the response
				if view.response:
					# Action confirmed
					# Delete all pings that met our search criteria
					for p in pingNames:
						await ping_delete(p, interaction.guild, cursor)
					# Update the cache
					await self._update_ping_cache(interaction.guild, cursor)
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
		async with self.bot.dbConnection.cursor() as cursor:
			for guild in self.bot.guilds:
				await self._update_ping_cache(guild, cursor)

async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Pings(bot))
