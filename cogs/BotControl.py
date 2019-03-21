import discord
from discord.ext import commands
from settings import config

class BotControl(commands.Cog, name="Bot Control"):
	def __init__(self, bot):
		self.bot = bot
	
	# Function that checks if a user can use ping control functions
	async def check_bot_control(ctx):
		roles = ctx.author.roles
		authors = [134830326789832704,96018174163570688]
		if (
			config["SERVER"]["ROLES"]["ADMIN"] in roles or
			config["SERVER"]["ROLES"]["MODERATOR"] in roles or
			ctx.author.id in authors
		):
			return True
		else:
			return False

	@commands.command(brief='This kills the bot')
	@commands.check(check_bot_control)
	async def logout(self, ctx):
		await ctx.send("Goodbye")
		await self.bot.close()

	@logout.error
	async def logout_error(self,ctx,error):
		if isinstance(error, commands.CheckFailure):
			await ctx.send("Nothing to see here, move along comrade.")
	
	@commands.command(name='cog_load', hidden=True)
	@commands.check(check_bot_control)
	async def cog_load(self, ctx, *, cog: str):
		"""Command which Loads a Module.
		Remember to use dot path. e.g: cogs.owner"""
	
		try:
			self.bot.load_extension(cog)
		except Exception as e:
			await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
		else:
			await ctx.send('**`SUCCESS`**')
	
	@commands.command(name='cog_unload', hidden=True)
	@commands.check(check_bot_control)
	async def cog_unload(self, ctx, *, cog: str):
		"""Command which Unloads a Module.
		Remember to use dot path. e.g: cogs.owner"""
		
		if cog != "cogs.BotControl":
			try:
				self.bot.unload_extension(cog)
			except Exception as e:
				await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
			else:
				await ctx.send('**`SUCCESS`**')
		else:
			await ctx.send("You cannot unload the bot control module!")
	
	@commands.command(name='cog_reload', hidden=True)
	@commands.check(check_bot_control)
	async def cog_reload(self, ctx, *, cog: str):
		"""Command which Reloads a Module.
		Remember to use dot path. e.g: cogs.owner"""
		
		if cog != "cogs.BotControl":
			try:
				self.bot.unload_extension(cog)
				self.bot.load_extension(cog)
			except Exception as e:
				await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
			else:
				await ctx.send('**`SUCCESS`**')
		else:
			await ctx.send("You cannot unload the bot control module!")


def setup(bot):
	bot.add_cog(BotControl(bot))