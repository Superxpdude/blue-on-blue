from discord.ext import commands
import slash_util

import subprocess

import logging

import blueonblue
log = logging.getLogger("blueonblue")

class BotControl(slash_util.Cog, name = "Bot Control"):
	"""Commands that control the bot's core functionality."""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(bot, *args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	@commands.command(brief="This kills the bot")
	@commands.is_owner()
	async def logout(self, ctx: commands.Context):
		await ctx.send("Goodbye")
		log.info(f"Bot terminated by {ctx.author.name}")
		await self.bot.close()

	@logout.error
	async def logout_error(self, ctx: commands.Context, error):
		if isinstance(error, commands.CheckFailure):
			await ctx.send("Nothing to see here, move along comrarde.")
		else:
			await ctx.bot.on_command_error(ctx,error,error_force=True)

	@commands.command()
	@commands.is_owner()
	async def cogload(self, ctx: commands.Context, *, cog: str):
		"""Loads an extension cog.

		Cog name is case sensitive.
		Cogs must be placed in the "cogs" folder on the bot."""
		try:
			self.bot.load_extension("cogs." + cog)
		except Exception as e:
			await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
			log.exception(f"Failed to load extension: {cog}.")
		else:
			await ctx.send("**`SUCCESS`**")
			log.info(f"Loaded extension: {cog}.")
			# Add the extension to the config list
			if cog not in ["botcontrol","users"]:
				self.bot.config["COGS"][cog] = "True"
				self.bot.write_config()

	@commands.command()
	@commands.is_owner()
	async def cogunload(self, ctx: commands.Context, *, cog: str):
		"""Unloads an extension cog.

		Cog name is case sensitive.
		Cogs must be placed in the "cogs" folder on the bot."""
		if cog != "botcontrol": # Prevent unloading botcontrol
			try:
				self.bot.unload_extension("cogs." + cog)
			except Exception as e:
				await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
				log.exception(f"Error unloading extension: {cog}.")
			else:
				await ctx.send("**`SUCCESS`**")
				log.info(f"Error unloading extension: {cog}.")

				# Disable the extension in the config
				if cog not in ["botcontrol","users"]:
					self.bot.config["COGS"][cog] = "False"
					self.bot.write_config()
		else:
			await ctx.send(f"You cannot unload the bot control module! Try using `{ctx.prefix}cogreload` instead.")

	@commands.command()
	@commands.is_owner()
	async def cogreload(self, ctx: commands.Context, *, cog: str):
		"""Reloads an extension cog.

		Cog name is case sensitive.
		Cogs must be placed in the "cogs" folder on the bot."""
		try:
			self.bot.reload_extension("cogs." + cog)
		except Exception as e:
			await ctx.send(f"**`ERROR:`** {type(e).__name__} - {e}")
			log.exception(f"Failed to reload extension: {cog}.")
		else:
			await ctx.send("**`SUCCESS`**")
			log.info(f"Reloaded extension: {cog}.")

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

	@commands.command()
	@commands.is_owner()
	async def br(self, ctx: commands.Context):
		await ctx.send("Break!")
		print("Break")
		await ctx.send("Continue!")

def setup(bot: blueonblue.BlueOnBlueBot):
	bot.add_cog(BotControl(bot))
