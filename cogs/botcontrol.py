import discord
from discord.ext import commands

import subprocess

import blueonblue

import logging
_log = logging.getLogger("blueonblue")

class BotControl(commands.Cog, name = "Bot Control"):
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

	@commands.command()
	@commands.is_owner()
	async def cogload(self, ctx: commands.Context, *, cog: str):
		"""Loads an extension cog.

		Cog name is case sensitive.
		Cogs must be placed in the "cogs" folder on the bot."""
		try:
			await self.bot.load_extension("cogs." + cog)
		except Exception as e:
			await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
			_log.exception(f"Failed to load extension: {cog}")
		else:
			await ctx.send("**`SUCCESS`**")
			_log.info(f"Loaded extension: {cog}")
			# Synchronize slash commands
			await self.bot.syncAppCommands()

	@commands.command()
	@commands.is_owner()
	async def cogunload(self, ctx: commands.Context, *, cog: str):
		"""Unloads an extension cog.

		Cog name is case sensitive.
		Cogs must be placed in the "cogs" folder on the bot."""
		if cog != "botcontrol": # Prevent unloading botcontrol
			try:
				await self.bot.unload_extension("cogs." + cog)
			except Exception as e:
				await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
				_log.exception(f"Error unloading extension: {cog}")
			else:
				await ctx.send("**`SUCCESS`**")
				_log.info(f"Unloaded extension: {cog}")
				# Synchronize slash commands
				await self.bot.syncAppCommands()
		else:
			await ctx.send(f"You cannot unload the bot control module! Try using `{ctx.prefix}cogreload` instead.")

	@commands.command()
	@commands.is_owner()
	async def cogreload(self, ctx: commands.Context, *, cog: str):
		"""Reloads an extension cog.

		Cog name is case sensitive.
		Cogs must be placed in the "cogs" folder on the bot."""
		try:
			await self.bot.reload_extension("cogs." + cog)
		except Exception as e:
			await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
			_log.exception(f"Failed to reload extension: {cog}")
		else:
			await ctx.send("**`SUCCESS`**")
			_log.info(f"Reloaded extension: {cog}")
			# Synchronize slash commands
			await self.bot.syncAppCommands()

	@commands.command()
	@commands.is_owner()
	async def gitpull(self, ctx: commands.Context):
		"""Performs a "git pull" on the bot.

		Returns the output of the pull into chat.
		Cogs must still be manually reloaded to update them."""
		msg = await ctx.send("Performing git pull")
		out = subprocess.run(["git", "pull"], check=True, stdout=subprocess.PIPE).stdout
		outstr = out.decode("utf-8")

		await msg.edit(f"Performing git pull\n```{outstr}```")

async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(BotControl(bot))
