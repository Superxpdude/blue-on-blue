import discord
from discord import app_commands
from discord.ext import commands

from typing import Literal, List

import blueonblue

import logging
log = logging.getLogger("blueonblue")

CHATFILTER_EMBED_COLOUR = 0xff0000

class ChatFilter(app_commands.Group, commands.Cog, name="chatfilter"):
	"""Chat filter module.

	These commands can only be used by authorized users."""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		# Initialize our filter lists
		self.blockList = {}
		self.allowList = {}

	# Async cog setup function
	async def cog_load(self):
		"""Initializes the database for the cog.
		Creates the tables if they don't exist."""
		async with self.bot.dbConnection.cursor() as cursor:
			# Create the tables if they do not exist
			# "filterlist" value determines if the string is on the filter list (0) or the exclusion list (1)
			await cursor.execute("CREATE TABLE if NOT EXISTS chatfilter (\
				server_id INTEGER NOT NULL,\
				filter_list INTEGER NOT NULL,\
				string TEXT NOT NULL,\
				UNIQUE(server_id,filter_list,string))")
			await self.bot.dbConnection.commit()
		await self._update_all_lists()

	async def _update_all_lists(self) -> None:
		"""Update the chat filter lists"""
		# Start the DB block
		async with self.bot.dbConnection.cursor() as cursor:
			# Reset our existing lists from memory
			keyList = []
			for g in self.bot.guilds:
				keyList.append(str(g.id))

			self.allowList = dict.fromkeys(keyList, [])
			self.blockList = dict.fromkeys(keyList, [])

			# Get data from the DB
			await cursor.execute("SELECT * FROM chatfilter")
			filterData = await cursor.fetchall()
			for f in filterData:
				serverStr = str(f["server_id"])
				if serverStr in keyList:
					# Server is present in list
					if f["filter_list"]:
						# Exclusion list
						self.allowList[serverStr].append(f["string"])
					else:
						# Filter list
						self.blockList[serverStr].append(f["string"])
			# To ensure that we remove longer words first, we need to sort the exclusion list
			for k in self.allowList:
				self.allowList[k].sort(key = len, reverse=True)

	async def _update_server_lists(self, guild: discord.Guild):
		"""Update the chat filter lists for a single server"""
		# Start the DB block
		async with self.bot.dbConnection.cursor() as cursor:
			# Don't reset the entire filter lists
			serverStr = str(guild.id)
			self.allowList[serverStr] = []
			self.blockList[serverStr] = []

			# Get data from the DB
			await cursor.execute("SELECT filter_list, string FROM chatfilter WHERE server_id = :server_id", {"server_id": guild.id})
			filterData = await cursor.fetchall()
			for f in filterData:
				if f["filter_list"]:
					# Exclusion list
					self.allowList[serverStr].append(f["string"])
				else:
					# Filter list
					self.blockList[serverStr].append(f["string"])
			# To ensure that we remove longer words first, we need to sort the exclusion list
			self.allowList[serverStr].sort(key = len, reverse=True)

	async def _add_chatfilter_entry(self, string: str, filterlist: int|str, guild: discord.Guild) -> None:
		"""Adds an entry to a chat filter list
		List == 0 for the block list, 1 for the allow list"""
		if type(filterlist) == str:
			if filterlist == "block":
				filterlist = 0 # Filter list
			else:
				filterlist = 1 # Exclusion list

		# Start the DB block
		async with self.bot.dbConnection.cursor() as cursor:
			# Add our entry to the DB
			await cursor.execute("INSERT OR REPLACE INTO chatfilter (server_id, filter_list, string) VALUES (:server_id, :list, :string)",
				{"server_id": guild.id, "list": filterlist, "string": string.casefold()})
			await self.bot.dbConnection.commit()
			await self._update_server_lists(guild)

	async def _remove_chatfilter_entry(self, string: str, filterlist: int|str, guild: discord.Guild) -> None:
		"""Removes an entry to a chat filter list
		List == 0 for the block list, 1 for the allow list"""
		if type(filterlist) == str:
			if filterlist == "block":
				filterlist = 0 # Filter list
			else:
				filterlist = 1 # Exclusion list

		# Start the DB block
		async with self.bot.dbConnection.cursor() as cursor:
			# Remove our entry from the DB
			await cursor.execute("DELETE FROM chatfilter WHERE (server_id = :server_id AND filter_list = :list AND string = :string)",
				{"server_id": guild.id, "list": filterlist, "string": string.casefold()})
			await self.bot.dbConnection.commit()
			await self._update_server_lists(guild)

	async def _get_chatfilterlist(self, filterlist: int|str, guild: discord.Guild) -> List[str]:
		"""Returns the entries in a chat filter list
		List == 0 for the block list, 1 for the allow list"""
		if type(filterlist) == str:
			if filterlist == "block":
				filterlist = 0 # Block list
			else:
				filterlist = 1 # Allow list

		await self._update_server_lists(guild)

		# Start the DB block
		async with self.bot.dbConnection.cursor() as cursor:
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
		excludeList = self.allowList[str(guild.id)]
		filterlist = self.blockList[str(guild.id)]
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

	blockListGroup = app_commands.Group(name="blocklist", description="Commands to manage the chatfilter blocklist")

	@blockListGroup.command(name = "show")
	async def blockListShow(self, interaction: discord.Interaction):
		"""Shows the block list"""
		filterEntries = await self._get_chatfilterlist("block", interaction.guild)
		filterEmbed = discord.Embed(
			colour = CHATFILTER_EMBED_COLOUR,
			title = f"{interaction.guild.name} chatfilter block list",
			description = ", ".join(map(lambda n: f"`{n}`", sorted(filterEntries, key=str.casefold)))
		)
		await interaction.response.send_message(embed = filterEmbed)

	@blockListGroup.command(name="add")
	@app_commands.describe(string="The string to add to the list")
	async def blockListAdd(self, interaction: discord.Interaction, string: str):
		"""Adds an entry to the block list"""
		# Add to list
		await self._add_chatfilter_entry(string, "block", interaction.guild)
		await interaction.response.send_message(f"{interaction.user.mention}, the string `{string}` has been added to the block list.")

	@blockListGroup.command(name="remove")
	@app_commands.describe(string="The string to remove from the list")
	async def blockListRemove(self, interaction: discord.Interaction, string: str):
		"""Removes an entry from the block list"""
		# Remove from list
		await self._remove_chatfilter_entry(string, "block", interaction.guild)
		await interaction.response.send_message(f"{interaction.user.mention}, the string `{string}` has been removed from the block list.")

	allowListGroup = app_commands.Group(name="allowlist", description="Commands to manage the chatfilter allowlist")

	@allowListGroup.command(name = "show")
	async def allowListShow(self, interaction: discord.Interaction):
		"""Shows the allow list"""
		filterEntries = await self._get_chatfilterlist("allow", interaction.guild)
		filterEmbed = discord.Embed(
			colour = CHATFILTER_EMBED_COLOUR,
			title = f"{interaction.guild.name} chatfilter allow list",
			description = ", ".join(map(lambda n: f"`{n}`", sorted(filterEntries, key=str.casefold)))
		)
		await interaction.response.send_message(embed = filterEmbed)

	@allowListGroup.command(name="add")
	@app_commands.describe(string="The string to add to the list")
	async def allowListAdd(self, interaction: discord.Interaction, string: str):
		"""Adds an entry to the allow list"""
		# Add to list
		await self._add_chatfilter_entry(string, "allow", interaction.guild)
		await interaction.response.send_message(f"{interaction.user.mention}, the string `{string}` has been added to the allow list.")

	@allowListGroup.command(name="remove")
	@app_commands.describe(string="The string to remove from the list")
	async def allowListRemove(self, interaction: discord.Interaction, string: str):
		"""Removes an entry from the allow list"""
		# Remove from list
		await self._remove_chatfilter_entry(string, "allow", interaction.guild)
		await interaction.response.send_message(f"{interaction.user.mention}, the string `{string}` has been removed from the allow list.")

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

async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(ChatFilter(bot))
