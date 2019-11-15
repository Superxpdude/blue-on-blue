import discord
from discord.ext import commands
import logging
log = logging.getLogger("blueonblue")

class BotControl(commands.Cog, name="Bot Control"):
	"""Commands that control the bot's base functionality."""
	def __init__(self,bot):
		self.bot = bot
		
	# Function that checks if a user can use ping control functions
	# To be replaced
	async def check_bot_control(ctx):
		authors = [134830326789832704,96018174163570688]
		if (
			ctx.author.id in authors
		):
			return True
		else:
			return False
	
	@commands.command(brief='This kills the bot')
	@commands.check(check_bot_control)
	async def logout(self, ctx):
		await ctx.send("Goodbye")
		log.info("Bot terminated by '%s'" % (ctx.author.name))
		await self.bot.close()
	
	@logout.error
	async def logout_error(self,ctx,error):
		if isinstance(error, commands.CheckFailure):
			await ctx.send("Nothing to see here, move along comrade.")
		else:
			await ctx.bot.on_command_error(ctx,error,error_force=True)
	
	@commands.command(name='cogload', hidden=True)
	@commands.check(check_bot_control)
	async def cogload(self, ctx, *, cog: str):
		"""Command which Loads a Module.
		Cog name is case sensitive."""
	
		try:
			self.bot.load_extension("cogs." + cog)
		except Exception as e:
			await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
			log.exception(f'Failed to load extension: {cog}.')
		else:
			await ctx.send('**`SUCCESS`**')
			log.info(f'Loaded extension: {cog}.')
	
	@commands.command(name='cogunload', hidden=True)
	@commands.check(check_bot_control)
	async def cogunload(self, ctx, *, cog: str):
		"""Command which Unloads a Module.
		Cog name is case sensitive."""
		
		if cog != "BotControl":
			try:
				self.bot.unload_extension("cogs." + cog)
			except Exception as e:
				await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
				log.exception(f'Error unloading extension: {cog}.')
			else:
				await ctx.send('**`SUCCESS`**')
				log.info(f'Unloaded extension: {cog}.')
		else:
			await ctx.send("You cannot unload the bot control module!")
	
	@commands.command(name='cogreload', hidden=True)
	@commands.check(check_bot_control)
	async def cogreload(self, ctx, *, cog: str):
		"""Command which Reloads a Module.
		Cog name is case sensitive."""
		
		if cog != "BotControl":
			try:
				self.bot.reload_extension("cogs." + cog)
			except Exception as e:
				await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
				log.exception(f'Failed to reload extension: {cog}.')
			else:
				await ctx.send('**`SUCCESS`**')
				log.info(f'Reloaded extension: {cog}.')
		else:
			await ctx.send("You cannot unload the bot control module!")

def setup(bot):
	bot.add_cog(BotControl(bot))