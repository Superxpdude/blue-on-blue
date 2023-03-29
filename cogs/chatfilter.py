import discord
from discord import app_commands
from discord.ext import commands

from typing import List

import blueonblue

import logging
_log = logging.getLogger(__name__)

CHATFILTER_EMBED_COLOUR = 0xff0000

@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
class ChatFilter(commands.GroupCog, group_name="chatfilter"):
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
		"""Initializes the database for the cog."""
		await self._update_all_lists()

	async def _update_all_lists(self) -> None:
		"""Update the chat filter lists"""
		# Start the DB block
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				# Reset our existing lists from memory
				keyList = []
				for g in self.bot.guilds:
					keyList.append(g.id)

				self.allowList = dict.fromkeys(keyList, [])
				self.blockList = dict.fromkeys(keyList, [])

				# Get data from the DB
				await cursor.execute("SELECT * FROM chatfilter")
				filterData = await cursor.fetchall()
				for f in filterData:
					serverID = f["server_id"]
					if serverID in keyList:
						# Server is present in list
						if f["filter_list"]:
							# Exclusion list
							self.allowList[serverID].append(f["string"])
						else:
							# Filter list
							self.blockList[serverID].append(f["string"])
				# To ensure that we remove longer words first, we need to sort the exclusion list
				for k in self.allowList:
					self.allowList[k].sort(key = len, reverse=True)

	async def _update_server_lists(self, guild: discord.Guild):
		"""Update the chat filter lists for a single server"""
		# Start the DB block
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				# Don't reset the entire filter lists
				self.allowList[guild.id] = []
				self.blockList[guild.id] = []

				# Get data from the DB
				await cursor.execute("SELECT filter_list, string FROM chatfilter WHERE server_id = :server_id", {"server_id": guild.id})
				filterData = await cursor.fetchall()
				for f in filterData:
					if f["filter_list"]:
						# Exclusion list
						self.allowList[guild.id].append(f["string"])
					else:
						# Filter list
						self.blockList[guild.id].append(f["string"])
				# To ensure that we remove longer words first, we need to sort the exclusion list
				self.allowList[guild.id].sort(key = len, reverse=True)

	async def _add_chatfilter_entry(self, string: str, filterlist: int|str, guild: discord.Guild) -> None:
		"""Adds an entry to a chat filter list
		List == 0 for the block list, 1 for the allow list"""
		if type(filterlist) == str:
			if filterlist == "block":
				filterlist = 0 # Filter list
			else:
				filterlist = 1 # Exclusion list

		# Start the DB block
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				# Add our entry to the DB
				await cursor.execute("INSERT OR REPLACE INTO chatfilter (server_id, filter_list, string) VALUES (:server_id, :list, :string)",
					{"server_id": guild.id, "list": filterlist, "string": string.casefold()})
				await db.commit()
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
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
				# Remove our entry from the DB
				await cursor.execute("DELETE FROM chatfilter WHERE (server_id = :server_id AND filter_list = :list AND string = :string)",
					{"server_id": guild.id, "list": filterlist, "string": string.casefold()})
				await db.commit()
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
		async with self.bot.db.connect() as db:
			async with db.cursor() as cursor:
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
		excludeList = self.allowList[guild.id] if guild.id in self.allowList else []
		filterlist = self.blockList[guild.id] if guild.id in self.blockList else []
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
		assert message.guild is not None
		text = message.content.casefold()
		return self._check_text(text, message.guild)

	def _check_thread(self, thread: discord.Thread):
		"""Runs a thread title through the chat filter."""
		# Casefold for string comparison
		text = thread.name.casefold()
		return self._check_text(text, thread.guild)

	async def _flag_message(self, message: discord.Message):
		"""Flags a message for violating the chat filter."""
		assert message.guild is not None
		assert isinstance(message.channel, discord.TextChannel)
		timestamp = message.edited_at if message.edited_at is not None else message.created_at

		embed = discord.Embed(
			title = f"{message.channel.parent}: {message.channel.name}" if isinstance(message.channel, discord.Thread) else message.channel.name,
			description = message.content,
			colour = CHATFILTER_EMBED_COLOUR,
			timestamp = timestamp
		)
		embed.set_author(
			name = message.author.display_name,
			icon_url = message.author.display_avatar.url
		)

		# Delete our flagged message
		await message.delete()
		# Log the deletion
		logChannel = await self.bot.serverConfig.channel_mod_activity.get(message.guild)
		if logChannel is not None:
			await logChannel.send(embed=embed)

	async def _flag_thread(self, thread: discord.Thread, before: discord.Thread | None = None):
		"""Reports a user for triggering the chat filter on a thread title."""
		guild: discord.Guild = thread.guild
		auditLog = None
		if guild.me.guild_permissions.view_audit_log:
			# Bot has permissions to view audit log
			if before is None:
				# Thread creation
				# This should only give us a single audit entry, so this shouldn't have any problems
				async for entry in guild.audit_logs(limit=1,action=discord.AuditLogAction.thread_create):
					auditLog = entry
			else:
				# Thread update
				async for entry in guild.audit_logs(limit=1,action=discord.AuditLogAction.thread_update):
					auditLog = entry
			title = "Thread Title"
			assert auditLog is not None
			author = auditLog.user
		else:
			title = "Thread Title, check audit log for confirmation"
			author = thread.owner

		assert author is not None
		# If the author is a bot, exit
		if author.bot:
			return

		# Create our embed
		embed = discord.Embed(
			title = title,
			description = thread.name,
			colour = CHATFILTER_EMBED_COLOUR,
			timestamp = auditLog.created_at if auditLog is not None else None
		)
		embed.set_author(
			name = author.display_name,
			icon_url = author.display_avatar.url
		)

		# Log the thread
		logChannel = await self.bot.serverConfig.channel_mod_activity.get(thread.guild)
		if logChannel is not None:
			await logChannel.send(embed=embed)

		# Act on the thread
		if before is None:
			# Thread creation. Edit the thread
			await thread.edit(name=f"thread-{thread.id}")
		else:
			# Existing thread
			await thread.edit(name=before.name)

	blockListGroup = app_commands.Group(name="blocklist", description="Commands to manage the chatfilter blocklist", guild_only=True)

	@blockListGroup.command(name = "show")
	async def blockListShow(self, interaction: discord.Interaction):
		"""Shows the block list"""
		assert interaction.guild is not None

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
		assert interaction.guild is not None

		# Add to list
		await self._add_chatfilter_entry(string, "block", interaction.guild)
		await interaction.response.send_message(f"{interaction.user.mention}, the string `{string}` has been added to the block list.")

	@blockListGroup.command(name="remove")
	@app_commands.describe(string="The string to remove from the list")
	async def blockListRemove(self, interaction: discord.Interaction, string: str):
		"""Removes an entry from the block list"""
		assert interaction.guild is not None

		# Remove from list
		await self._remove_chatfilter_entry(string, "block", interaction.guild)
		await interaction.response.send_message(f"{interaction.user.mention}, the string `{string}` has been removed from the block list.")

	allowListGroup = app_commands.Group(name="allowlist", description="Commands to manage the chatfilter allowlist", guild_only=True)

	@allowListGroup.command(name = "show")
	async def allowListShow(self, interaction: discord.Interaction):
		"""Shows the allow list"""
		assert interaction.guild is not None

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
		assert interaction.guild is not None

		# Add to list
		await self._add_chatfilter_entry(string, "allow", interaction.guild)
		await interaction.response.send_message(f"{interaction.user.mention}, the string `{string}` has been added to the allow list.")

	@allowListGroup.command(name="remove")
	@app_commands.describe(string="The string to remove from the list")
	async def allowListRemove(self, interaction: discord.Interaction, string: str):
		"""Removes an entry from the allow list"""
		assert interaction.guild is not None

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
	async def on_thread_create(self, thread: discord.Thread):
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
