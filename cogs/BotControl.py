import discord
from discord.ext import commands

class BotControl(commands.Cog, name="Bot Control"):
	def __init__(self, bot):
		self.bot = bot

	@bot.command(brief='This kills the bot')
	@commands.is_owner()
	async def logout(self, ctx):
		await ctx.send("Goodbye")
		await bot.close()

	@logout.error
	async def logout_error(ctx,error):
		if isinstance(error, commands.CheckFailure):
			await ctx.send("Nothing to see here, move along comrade.")

def setup(bot):
	bot.add_cog(BotControl(bot))