from discord.ext import commands
import slash_util

import subprocess

import logging
log = logging.getLogger("blueonblue")

class BotControl(slash_util.Cog, name = "Bot Control"):
	"""Commands that control the bot's core functionality."""
	def __init__(self, bot,*args,**kwargs):
		super().__init__(bot, *args,**kwargs)
		self.bot: slash_util.Bot = bot

	@commands.command(brief="This kills the bot")
	@commands.is_owner()
	async def logout(self, ctx: commands.Context):
		await ctx.send("Goodbye")
		log.info(f"Bot terminated by {ctx.author.name}")
		await self.bot.close()

def setup(bot):
	bot.add_cog(BotControl(bot))
