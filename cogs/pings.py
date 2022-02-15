import discord
from discord.ext import commands, tasks
import slash_util

import asqlite
from datetime import datetime, timezone

import blueonblue

import logging
log = logging.getLogger("blueonblue")

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

async def ping_exists(self, tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> bool:
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

async def ping_is_alias(self, tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> bool:
	"""Gets the alias reference for a ping.
	Returns True if the ping exists AND is an alias. Otherwise returns False."""
	tag = tag.casefold()
	await cursor.execute("SELECT alias_for FROM pings WHERE server_id = :server_id AND ping_name = :ping AND alias_for IS NOT NULL", {"server_id": guild.id, "ping": tag})
	is_alias = await cursor.fetchone()
	if is_alias is None: # Alias is null, or ping doesn't exist
		return False
	else: # Alias is not null, and therefore exists
		return True

async def ping_get_id(self, tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> int | None:
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

async def ping_create(self, tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> None:
	"""Creates a ping in the database.
	Use ping_exists() to check if the ping exists or not first."""
	tag = tag.casefold()
	time = round(datetime.now(timezone.utc).timestamp()) # Get the current time in timestamp format
	await cursor.execute("INSERT OR REPLACE INTO pings (server_id, ping_name, last_used_time) VALUES (:server_id, :ping, :time)",
		{"server_id": guild.id, "ping": tag, "time": time})

async def ping_delete(self, tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> None:
	"""Removes a ping from the database"""
	tag = tag.casefold()
	ping_id = await ping_get_id(self, tag, guild, cursor)
	await cursor.execute("DELETE FROM pings WHERE (server_id = :server_id AND id = :ping)", {"server_id": guild.id, "ping": ping_id})

async def ping_update_time(self, tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> bool:
	"""Updates the "last used time" of a ping in the database."""
	tag = tag.casefold()
	time = round(datetime.now(timezone.utc).timestamp()) # Get the current time in timestamp format
	ping_id = await ping_get_id(self, tag, guild, cursor)
	await cursor.execute("UPDATE pings SET last_used_time = :time WHERE id = :ping", {"time": time, "ping": ping_id}) # Ping IDs are globally unique

async def ping_add_user(self, tag: str, guild: discord.Guild, user: discord.Member, cursor: asqlite.Cursor) -> bool:
	"""Adds a user to a ping.
	Checks if the ping is an alias, and handles it accordingly.
	Returns False if an error was encountered."""
	tag = tag.casefold()
	# Get the ID of the ping
	ping_id = await ping_get_id(self, tag, guild, cursor)
	if ping_id is not None: # Ping exists.
		await cursor.execute("INSERT OR REPLACE INTO ping_users (server_id, ping_id, user_id) VALUES (:server_id, :ping, :user_id)",
			{"server_id": guild.id, "ping": ping_id, "user_id": user.id})
		return True
	else: # Ping does not exist. Could not add user to ping.
		return False

async def ping_remove_user(self, tag: str, guild: discord.Guild, user: discord.Member, cursor: asqlite.Cursor) -> bool:
	"""Removes a user from a ping.
	Checks if the ping is an alias, and handles it accordingly.
	Returns False if an error was encountered."""
	tag = tag.casefold()
	# Get the ID of the ping
	ping_id = await ping_get_id(self, tag, guild, cursor)
	if ping_id is not None: # Ping exists.
		# This doesn't actually need a server reference, since ping IDs must be globally unique.
		await cursor.execute("DELETE FROM ping_users WHERE (ping_id = :ping AND user_id = :user_id)",
			{"ping": ping_id, "user_id": user.id})
		return True
	else: # Ping does not exist. Could not add user to ping.
		return False

async def ping_has_user(self, tag: str, guild: discord.Guild, user: discord.Member, cursor: asqlite.Cursor) -> bool:
	"""Checks if a user is already in a ping.
	Returns True if the user is in the ping.
	Otherwise, returns False."""
	tag = tag.casefold()
	# Get the ID of the ping
	ping_id = await ping_get_id(self, tag, guild, cursor)
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

async def ping_count_users(self, tag: str, guild: discord.Guild, cursor: asqlite.Cursor) -> int:
	"""Returns the number of users present in a ping.
	Pings that don't exist will return -1."""
	tag = tag.casefold()
	# Get the ID of the ping
	ping_id = await ping_get_id(self, tag, guild, cursor)
	if ping_id is None: # Ping does not exist
		return -1
	else: # Ping exists
		await cursor.execute("SELECT COUNT(*) FROM ping_users WHERE server_id = :server_id AND ping_id = :ping", {"server_id": guild.id, "ping": ping_id})
		userCount = await cursor.fetchone()
		return userCount[0] # This entry has to be on the return. The await can't be subscripted.

async def ping_get_user_ids_by_id(self, id: int, cursor: asqlite.Cursor) -> list[int]:
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

class Pings(slash_util.Cog, name = "Pings"):
	"""Ping users by a tag."""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(bot, *args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		self.bot.loop.create_task(self.db_init())

	async def db_init(self):
		"""Initializes the database for the cog.
		Creates the tables if they don't exist."""
		async with self.bot.db_connection.cursor() as cursor:
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
			await self.bot.db_connection.commit()

	@commands.command()
	async def ping(self, ctx: commands.Context, *, tag: str=""):
		"""Pings all users associated with a specific tag.
		Any text on a new line will be ignored. You can use this to send a message along with a ping."""
		tag = tag.split("\n")[0]
		san_check = sanitize_check(tag)
		if san_check is not None: # Validate our tag first
			await ctx.send(f"{ctx.author.mention}: {san_check}")
			return
		tag = tag.casefold() # String searching is case-sensitive

		# Begin our DB section
		async with self.bot.db_connection.cursor() as cursor:
			response = None
			ping_id = await ping_get_id(self, tag, ctx.guild, cursor) # Get the ID of the ping (or none if it doesn't exist)
			if ping_id is None:
				# Ping does not exist
				response = f"{ctx.author.mention} This tag does not exist. Try `{ctx.prefix}pinglist` for a list of active pings."
			else:
				# Ping exists
				pingUserIDs = await ping_get_user_ids_by_id(self, ping_id, cursor)
				pingMentions: list[discord.Member] = []
				for userID in pingUserIDs:
					# Try to get the member object from the user ID
					member = ctx.guild.get_member(userID)
					if member is not None:
						# Member is present in the guild
						pingMentions.append(member.mention)

				# Check to see if we have any valid members
				if len(pingMentions) > 0:
					# Ping has users
					# Update the "last used time"
					await ping_update_time(self, tag, ctx.guild, cursor)
					response = f"{ctx.author.mention} has pinged `{tag}`: " + " ".join(pingMentions) # Create the ping message
				else:
					# Ping is empty
					response = f"{ctx.author.mention} Ping `{tag}` appears to be empty. Performing cleanup." # Inform the user
					await ping_delete(self, tag, ctx.guild, cursor)

			await self.bot.db_connection.commit() # Write data to the database

			# Send a response to the user.
			if response is None:
				response = f"{ctx.author.mention} It looks like there was an error with the command `{ctx.command.name}`"

			await ctx.send(response)

	@commands.command()
	async def pingme(self, ctx: commands.Context, *, tag: str=""):
		"""Adds or removes you from a ping list.
		If you're not in the list, it will add you to the list.
		If you are in the list, it will remove you from the list."""
		san_check = sanitize_check(tag)
		if san_check is not None:
			await ctx.send(f"{ctx.author.mention}: {san_check}")
			return
		tag = tag.casefold() # String searching is case-sensitive

		# Begin our DB section
		async with self.bot.db_connection.cursor() as cursor:
			response = None
			# Check if the user in in that ping list
			# Get the ping ID, and check if the ping exists
			if await ping_exists(self, tag, ctx.guild, cursor): # Ping exists
				# Check if the user is in the ping
				if await ping_has_user(self, tag, ctx.guild, ctx.author, cursor):
					# User already in ping
					success = await ping_remove_user(self, tag, ctx.guild, ctx.author, cursor)
					if success:
						response = f"{ctx.author.mention} You have been removed from ping: `{tag}`"
					else:
						response = f"{ctx.author.mention} There was an error removing you from ping: `{tag}`"

					# Check to see if the ping has any users left
					userCount = await ping_count_users(self, tag, ctx.guild, cursor)
					if userCount <= 0: # No users left in ping.
						await ping_delete(self, tag, ctx.guild, cursor)
				else:
					# User not already in ping
					success = await ping_add_user(self, tag, ctx.guild, ctx.author, cursor)
					if success:
						response = f"{ctx.author.mention} You have been added to ping: `{tag}`"
					else:
						response = f"{ctx.author.mention} There was an error adding you to ping: `{tag}`"

			else: # Ping does not exist
				# We need to create the ping
				await ping_create(self, tag, ctx.guild, cursor)
				# Add the user to the ping
				success = await ping_add_user(self, tag, ctx.guild, ctx.author, cursor)
				if success:
					response = f"{ctx.author.mention} You have been added to ping: `{tag}`"
				else:
					response = f"{ctx.author.mention} There was an error adding you to ping: `{tag}`"
			await self.bot.db_connection.commit() # Write data to the database

			# Send a response to the user.
			if response is None:
				response = f"{ctx.author.mention} It looks like there was an error with the command `{ctx.command.name}`"

			await ctx.send(response)

	@commands.command()
	async def pinglist(self, ctx: commands.Context, *, tag: str=""):
		"""Lists information about pings.

		When called with no tag, it will list all active tags.
		When called with a tag, it will list all users subscribed to that tag.
		When called with a mention to yourself, it will list all pings that you are currently subscribed to.
		Supports searching for tags. Entering a partial tag will return all valid matches."""
		tag = tag.casefold() # String searching is case-sensitive

		# Begin our DB section
		async with self.bot.db_connection.cursor() as cursor:
			response = None
			# We need to figure out what kind of search we need to run
			if "<@" in tag: # Search by user
				userID = tag.replace("<","").replace("@","").replace("!","").replace(">","")
				if not userID.isnumeric():
					response = f"{ctx.author.mention}: Error reading pinglist criteria."
				else:
					# UserID is numeric
					if int(userID) == ctx.author.id:
						# userID matches author. Get list of ping IDs
						await cursor.execute("SELECT ping_id FROM ping_users WHERE (server_id = :server_id AND user_id = :user_id)",
							{"server_id": ctx.guild.id, "user_id": ctx.author.id})
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
								response = f"{ctx.author.mention}, you are currently subscribed to the following pings: "\
									"\n```" + ", ".join(userPings) + "```"
							else:
								# Found pings, but could not find their names
								response = f"{ctx.author.mention}, there was an error retrieving your pings."
						else:
							# Did not find any pings for the user
							response = f"{ctx.author.mention}, you are not currently subscribed to any pings."
					else:
						# userID does not match author
						response = f"{ctx.author.mention}, you cannot check a ping list for another user!"

			elif len(tag) > 0:
				# Ping provided. Search to see if it exists
				await cursor.execute("SELECT id, alias_for FROM pings WHERE server_id = :server_id AND ping_name = :ping", {"server_id": ctx.guild.id, "ping": tag})
				pingInfo = await cursor.fetchone()
				if pingInfo is not None:
					# We found a direct match for that ping
					alias = None
					if pingInfo["alias_for"] is not None:
						# Ping is an alias
						pingID = pingInfo["alias_for"]
						await cursor.execute("SELECT ping_name FROM pings WHERE id = :ping", {"ping": pingID})
						aliasData = await cursor.fetchone()
						if (aliasData is not None) and ("ping_name" in aliasData.keys()):
							alias = aliasData["ping_name"]
					else:
						# Ping is not an alias
						pingID = pingInfo["id"]
					# Retrieve a list of users subscribed to the referenced ping
					await cursor.execute("SELECT user_id FROM ping_users WHERE ping_id = :ping", {"ping": pingID})
					pingUserData = await cursor.fetchall()
					pingUserNames = []
					for p in pingUserData:
						member = ctx.guild.get_member(p["user_id"])
						if member is not None: # If we could find the user
							pingUserNames.append(member.display_name)
					# Now that we have our display names, create our response
					if alias is None:
						# Not an alias
						response = f"Tag `{tag}` mentions the following users: \n```{', '.join(pingUserNames)}```"
					else:
						# Tag is an alias
						response = f"Tag `{tag}` is an alias for `{alias}`, which mentions the following users: \n```{', '.join(pingUserNames)}```"
				else:
					# No direct match. Search for pings matching that tag.
					# This can't be used with a dict for parameters, since the LIKE statement won't be happy with it
					await cursor.execute("SELECT ping_name FROM pings WHERE server_id = ? AND ping_name LIKE ? AND alias_for IS NULL", (ctx.guild.id,"%"+tag+"%",))
					pingData = await cursor.fetchall()
					pingResults: list[str] = []
					for p in pingData:
						if p["ping_name"] is not None: # Ensure that we have a ping name
							pingResults.append(p["ping_name"])
					# Now that we have our ping names, we can form our response
					if len(pingResults) > 0:
						# We have at least one ping response
						response = f"Tag search for `{tag}`: \n```{', '.join(sorted(pingResults, key=str.casefold))}```"
					else:
						# We did not find any search results
						response = f"{ctx.author.mention}, there are no tags for the search term: `{tag}`"

			else:
				# No tag is provided. Return all tags (that are not aliases)
				await cursor.execute("SELECT ping_name FROM pings WHERE server_id = :server_id AND alias_for IS NULL", {"server_id": ctx.guild.id})
				pingData = await cursor.fetchall()
				pingResults: list[str] = []
				for p in pingData:
					if "ping_name" in p.keys():
						pingResults.append(p["ping_name"])
				# Now that we have our ping names, we can form our response
				if len(pingResults) > 0:
					# We have at least one ping response
					response = f"Tag list: \n```{', '.join(pingResults)}```"
				else:
					# No pings defined
					response = "There are currently no pings defined."

			if response is None:
				response = f"{ctx.author.mention} It looks like there was an error with the command `{ctx.command.name}`"

			# Send our response
			await ctx.send(response)
			# We don't need to commit to the DB, since we don't write anything here

def setup(bot: blueonblue.BlueOnBlueBot):
	bot.add_cog(Pings(bot))
