import discord
from discord.ext import commands

import subprocess

import blueonblue

import logging

_log = logging.getLogger(__name__)


class BotControl(commands.Cog, name="Bot Control"):
	"""Commands that control the bot's core functionality."""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	@commands.command(brief="This kills the bot")
	@commands.is_owner()
	async def logout(self, ctx: commands.Context):
		await ctx.send("Goodbye")
		_log.info(f"Bot terminated by {ctx.author.name}")
		await self.bot.close()

	@commands.command(brief="Synchronizes app commands")
	@commands.is_owner()
	async def sync(self, ctx: commands.Context):
		await ctx.send("Synchronizing app commands")
		await self.bot.syncAppCommands()
		await ctx.send("App commands synchronized")

	@commands.command()
	@commands.is_owner()
	async def cogload(self, ctx: commands.Context, *, cog: str):
		"""Loads an extension cog.

		Cog name is case sensitive.
		Cogs must be placed in the "cogs" folder on the bot."""
		try:
			await self.bot.load_extension("cogs." + cog)
			# If we have a debug ID set, copy global commands to the guild
			if self.bot.config.debug_server is not None:
				self.bot.tree.copy_global_to(
					guild=discord.Object(self.bot.config.debug_server)
				)
		except Exception as e:
			await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
			_log.exception(f"Failed to load extension: {cog}")
		else:
			await ctx.send("**`SUCCESS`**")
			_log.info(f"Loaded extension: {cog}")

	@commands.command()
	@commands.is_owner()
	async def cogunload(self, ctx: commands.Context, *, cog: str):
		"""Unloads an extension cog.

		Cog name is case sensitive.
		Cogs must be placed in the "cogs" folder on the bot."""
		if cog != "botcontrol":  # Prevent unloading botcontrol
			try:
				await self.bot.unload_extension("cogs." + cog)
				# If we have a debug ID set, we need to update our copied commands
				if self.bot.config.debug_server is not None:
					guildObject = discord.Object(self.bot.config.debug_server)
					self.bot.tree.clear_commands(guild=guildObject)
					self.bot.tree.copy_global_to(guild=guildObject)
			except Exception as e:
				await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
				_log.exception(f"Error unloading extension: {cog}")
			else:
				await ctx.send("**`SUCCESS`**")
				_log.info(f"Unloaded extension: {cog}")
		else:
			await ctx.send(
				f"You cannot unload the bot control module! Try using `{ctx.prefix}cogreload` instead."
			)

	@commands.command()
	@commands.is_owner()
	async def cogreload(self, ctx: commands.Context, *, cog: str):
		"""Reloads an extension cog.

		Cog name is case sensitive.
		Cogs must be placed in the "cogs" folder on the bot."""
		try:
			await self.bot.reload_extension("cogs." + cog)
			# If we have a debug ID set, we need to rebuild our copied commands
			if self.bot.config.debug_server is not None:
				guildObject = discord.Object(self.bot.config.debug_server)
				self.bot.tree.clear_commands(guild=guildObject)
				self.bot.tree.copy_global_to(guild=guildObject)
		except Exception as e:
			await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
			_log.exception(f"Failed to reload extension: {cog}")
		else:
			await ctx.send("**`SUCCESS`**")
			_log.info(f"Reloaded extension: {cog}")

	@commands.command()
	@commands.is_owner()
	async def gitpull(self, ctx: commands.Context):
		"""Performs a "git pull" on the bot.

		Returns the output of the pull into chat.
		Cogs must still be manually reloaded to update them."""
		msg = await ctx.send("Performing git pull")
		out = subprocess.run(["git", "pull"], check=True, stdout=subprocess.PIPE).stdout
		outstr = out.decode("utf-8")

		await msg.edit(content=f"Performing git pull\n```{outstr}```")


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(BotControl(bot))
