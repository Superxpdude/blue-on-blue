import discord
from discord.ext import commands
import slash_util

from typing import Literal, List

import blueonblue

import logging
log = logging.getLogger("blueonblue")

CHATFILTER_EMBED_COLOUR = 0xff0000

class ChatFilter(slash_util.Cog, name="Chat Filter"):
	"""Chat filter module.

	These commands can only be used by authorized users."""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		# Set up our DB
		self.bot.loop.create_task(self.db_init())
		# Initialize our filter lists
		self.exclusionList = {}
		self.filterlist = {}

	async def db_init(self):
		"""Initializes the database for the cog.
		Creates the tables if they don't exist."""
		async with self.bot.db_connection.cursor() as cursor:
			# Create the tables if they do not exist
			# "filterlist" value determines if the string is on the filter list (0) or the exclusion list (1)
			await cursor.execute("CREATE TABLE if NOT EXISTS chatfilter (\
				server_id INTEGER NOT NULL,\
				filterlist INTEGER NOT NULL,\
				string TEXT NOT NULL,\
				UNIQUE(server_id,filterlist,string))")
			await self.bot.db_connection.commit()

	async def _update_all_lists(self) -> None:
		"""Update the chat filter lists"""
		# Start the DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Reset our existing lists from memory
			keyList = []
			for g in self.bot.guilds:
				keyList.append(str(g.id))

			self.exclusionList = dict.fromkeys(keyList, [])
			self.filterlist = dict.fromkeys(keyList, [])

			# Get data from the DB
			await cursor.execute("SELECT * FROM chatfilter")
			filterData = await cursor.fetchall()
			for f in filterData:
				serverStr = str(f["server_id"])
				if serverStr in keyList:
					# Server is present in list
					if f["filter_list"]:
						# Exclusion list
						self.exclusionList[serverStr].append(f["string"])
					else:
						# Filter list
						self.filterlist[serverStr].append(f["string"])
			# To ensure that we remove longer words first, we need to sort the exclusion list
			for k in self.exclusionList:
				self.exclusionList[k].sort(key = len, reverse=True)

	async def _update_server_lists(self, guild: discord.Guild):
		"""Update the chat filter lists for a single server"""
		# Start the DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Don't reset the entire filter lists
			serverStr = str(guild.id)
			self.exclusionList[serverStr] = []
			self.filterlist[serverStr] = []

			# Get data from the DB
			await cursor.execute("SELECT filter_list, string FROM chatfilter WHERE server_id = :server_id", {"server_id": guild.id})
			filterData = await cursor.fetchall()
			for f in filterData:
				if f["filter_list"]:
					# Exclusion list
					self.exclusionList[serverStr].append(f["string"])
				else:
					# Filter list
					self.filterlist[serverStr].append(f["string"])
			# To ensure that we remove longer words first, we need to sort the exclusion list
			self.exclusionList[serverStr].sort(key = len, reverse=True)

	async def _add_chatfilter_entry(self, string: str, filterlist: int|str, guild: discord.Guild) -> None:
		"""Adds an entry to a chat filter list
		List == 0 for the filter list, 1 for the exclusion list"""
		if type(filterlist) == str:
			if filterlist == "filter":
				filterlist = 0 # Filter list
			else:
				filterlist = 1 # Exclusion list

		# Start the DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Add our entry to the DB
			await cursor.execute("INSERT OR REPLACE INTO chatfilter (server_id, filter_list, string) VALUES (:server_id, :list, :string)",
				{"server_id": guild.id, "list": filterlist, "string": string.casefold()})
			await self.bot.db_connection.commit()
			await self._update_server_lists(guild)

	async def _remove_chatfilter_entry(self, string: str, filterlist: int|str, guild: discord.Guild) -> None:
		"""Removes an entry to a chat filter list
		List == 0 for the filter list, 1 for the exclusion list"""
		if type(filterlist) == str:
			if filterlist == "filter":
				filterlist = 0 # Filter list
			else:
				filterlist = 1 # Exclusion list

		# Start the DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Remove our entry from the DB
			await cursor.execute("DELETE FROM chatfilter WHERE (server_id = :server_id AND filter_list = :list AND string = :string)",
				{"server_id": guild.id, "list": filterlist, "string": string.casefold()})
			await self.bot.db_connection.commit()
			await self._update_server_lists(guild)

	async def _get_chatfilterlist(self, filterlist: int|str, guild: discord.Guild) -> List[str]:
		"""Returns the entries in a chat filter list
		List == 0 for the filter list, 1 for the exclusion list"""
		if type(filterlist) == str:
			if filterlist == "filter":
				filterlist = 0 # Filter list
			else:
				filterlist = 1 # Exclusion list

		await self._update_server_lists(guild)

		# Start the DB block
		async with self.bot.db_connection.cursor() as cursor:
			# Get our values from the DB
			await cursor.execute("SELECT string FROM chatfilter WHERE (server_id = :server_id AND filter_list = :list)",
				{"server_id": guild.id, "list": filterlist})
			filterData = await cursor.fetchall()
			filterEntries = []
			for f in filterData:
				filterEntries.append(f["string"])
			return filterEntries

	def _check_text(self, text: str, guild: discord.Guild) -> bool:
		"""Checks a text string against the chatfilter for a guild.
		Returns False if no issues found. Returns True if the text violates the chatfilter."""
		# Grab the lists for this guild
		excludeList = self.exclusionList[str(guild.id)]
		filterlist = self.filterlist[str(guild.id)]
		# Remove any excluded strings from the processed text
		processed = text
		if any(excludeStrings in text for excludeStrings in excludeList):
			for excludeString in excludeList:
				processed = processed.replace(excludeString, "")
		# Remove special characters from the text
		for i in [" ","-","_",":",";"]:
			processed = processed.replace(i, "")
		# Check for any filtered words/phrases
		if any(filterStrings in processed for filterStrings in filterlist):
			# Filtered string found
			return True
		else:
			# No issues detected
			return False

	def _check_message(self, message: discord.Message):
		"""Runs a message through the chat filter."""
		# Casefold for string comparison
		text = message.content.casefold()
		return self._check_text(text, message.guild)

	def _check_thread(self, thread: discord.Thread):
		"""Runs a thread title through the chat filter."""
		# Casefold for string comparison
		text = thread.name.casefold()
		return self._check_text(text, thread.guild)

	async def _flag_message(self, message: discord.Message):
		"""Flags a message for violating the chat filter."""
		timestamp = message.edited_at if message.edited_at is not None else message.created_at
		embed = discord.Embed(
			title = f"{message.channel.parent}: {message.channel}" if hasattr(message.channel, "parent") else message.channel.name,
			description = message.content,
			colour = CHATFILTER_EMBED_COLOUR,
			timestamp = timestamp
		)
		embed.set_author(
			name = message.author.display_name,
			icon_url = message.author.avatar.url
		)

		# Delete our flagged message
		await message.delete()
		# Log the deletion
		logChannel = message.guild.get_channel(self.bot.serverConfig.getint(str(message.guild.id), "channel_mod_activity"))
		if logChannel is not None:
			await logChannel.send(embed=embed)

	async def _flag_thread(self, thread: discord.Thread, before: discord.Thread = None):
		"""Reports a user for triggering the chat filter on a thread title."""
		guild: discord.Guild = thread.guild
		if guild.me.guild_permissions.view_audit_log:
			# Bot has permissions to view audit log
			if before is None:
				# Thread creation
				auditLog = await guild.audit_logs(limit=1,action=discord.AuditLogAction.thread_create).flatten()
			else:
				# Thread update
				auditLog = await guild.audit_logs(limit=1,action=discord.AuditLogAction.thread_update).flatten()
			title = "Thread Title"
			author = auditLog[0].user
		else:
			title = "Thread Title, check audit log for confirmation"
			author = thread.owner

		# If the author is a bot, exit
		if author.bot:
			return

		# Create our embed
		embed = discord.Embed(
			title = title,
			description = thread.name,
			colour = CHATFILTER_EMBED_COLOUR,
			timestamp = auditLog[0].created_at
		)
		embed.set_author(
			name = author.display_name,
			icon_url = author.avatar.url
		)

		# Log the thread
		logChannel = guild.get_channel(self.bot.serverConfig.getint(str(guild.id), "channel_mod_activity"))
		if logChannel is not None:
			await logChannel.send(embed=embed)

		# Act on the thread
		if before is None:
			# Thread creation. Edit the thread
			await thread.edit(name=f"thread-{thread.id}")
		else:
			# Existing thread
			await thread.edit(name=before.name)

	@slash_util.slash_command(guild_id = blueonblue.debugServerID)
	@slash_util.describe(filterlist = "Chatfilter list to use")
	@slash_util.describe(mode = "Mode of operation")
	@slash_util.describe(string = "Text to add/remove from chatfilter list")
	async def chatfilter(self, ctx: slash_util.Context, filterlist: Literal["filter", "exclude"], mode: Literal["show", "add", "remove"], string: str = None):
		"""Controls chat filter settings"""
		if not (await blueonblue.checks.slash_is_moderator(self.bot, ctx)):
			await ctx.send("You are not authorized to use this command", ephemeral=True)
			return

		if (mode != "show") and (string is None):
			await ctx.send("A string must be provided when trying to add or remove from a filter list.", ephemeral=True)
			return

		if filterlist == "filter":
			filterlist = 0
		else:
			filterlist = 1

		if filterlist == 1:
			filterText = "exclusion"
		else:
			filterText = "filter"

		if string is not None:
			string = string.casefold()

		if mode == "add":
			# Add to list
			await self._add_chatfilter_entry(string, filterlist, ctx.guild)
			await ctx.send(f"{ctx.author.mention}, the string `{string}` has been added to the {filterText} list.")
		elif mode == "remove":
			# Remove from list
			await self._remove_chatfilter_entry(string, filterlist, ctx.guild)
			await ctx.send(f"{ctx.author.mention}, the string `{string}` has been removed from the {filterText} list.")
		else:
			# Show list
			filterEntries = await self._get_chatfilterlist(filterlist, ctx.guild)
			filterEmbed = discord.Embed(
				colour = CHATFILTER_EMBED_COLOUR,
				title = f"{ctx.guild.name} chatfilter {filterText} list",
				description = ", ".join(map(lambda n: f"`{n}`", sorted(filterEntries, key=str.casefold)))
			)
			await ctx.send(embed = filterEmbed)


	@commands.Cog.listener()
	async def on_message(self, message: discord.Message):
		if (message.author != self.bot.user) and (not message.is_system()) and (message.guild is not None):
			if self._check_message(message):
				await self._flag_message(message)

	@commands.Cog.listener()
	async def on_message_edit(self, before: discord.Message, after: discord.Message):
		if (after.author != self.bot.user) and (not after.is_system()) and (after.guild is not None):
			if self._check_message(after):
				await self._flag_message(after)

	@commands.Cog.listener()
	async def on_thread_join(self, thread: discord.Thread):
		if self._check_thread(thread):
			await self._flag_thread(thread)

	@commands.Cog.listener()
	async def on_thread_update(self, before: discord.Thread, after: discord.Thread):
		if self._check_thread(after):
			await self._flag_thread(after,before)

	@commands.Cog.listener()
	async def on_ready(self):
		"""Refresh our chatfilter lists in memory on reconnection.
		This needs to wait until the bot is ready, since it relies on being able to grab a list of guilds that the bot is in."""
		await self._update_all_lists()

	@commands.command()
	async def update_list(self, ctx: commands.Context):
		await self._update_all_lists()

def setup(bot: blueonblue.BlueOnBlueBot):
	bot.add_cog(ChatFilter(bot))
