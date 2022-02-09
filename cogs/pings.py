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
	await cursor.execute("DELETE FROM pings WHERE (server_id = :server_id AND ping_name = :ping)", {"server_id": guild.id, "ping": tag})

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
		self.db_check.start()

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

	@tasks.loop(seconds=1, reconnect = False, count=1)
	async def db_check(self):
		"""Checks that the database tables exist. Before loop function creates it if it doesn't."""
		log.debug("Creating ping tables if they don't exist.")

	@db_check.before_loop
	async def db_setup(self):
		"""Creates the db tables if they don't exist."""
		# We don't need to wait until the bot is ready for this loop
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

def setup(bot: blueonblue.BlueOnBlueBot):
	bot.add_cog(Pings(bot))
