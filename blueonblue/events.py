# Blue on blue standard bot events
# Use this for reference:
# https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/develop/redbot/core/events.py

from datetime import datetime
from discord.ext import commands
from blueonblue.config import config
import blueonblue.checks
import sys, traceback
import logging
log = logging.getLogger("blueonblue")

__all__ = ["init_events"]

def init_events(bot):

	@bot.event
	async def on_connect():
		if bot._uptime is None:
			log.info("Connected to Discord.")
	
	# On ready. Runs when bot is ready.
	@bot.event
	async def on_ready():
		if bot._uptime is not None:
			return
			
		bot._uptime = datetime.utcnow()
		initial_extensions = ["BotControl"] + config["BOT"]["COGS"] # Initial cogs to load
		
		# Try to load extensions
		log.info("Loading extensions...")
		for ext in initial_extensions:
			try:
				bot.load_extension("cogs." + ext)
			except Exception as e:
				log.exception(f'Failed to load extension: {ext}.')
			else:
				log.info(f'Loaded extension: {ext}.')
		log.info("Extensions loaded.")
		
		bot._guild = bot.get_guild(config["SERVER"]["ID"]) # Grab the server object
		
		log.info("Connected to servers: {}".format(bot.guilds))
		log.info("Blue on blue ready.")
	
	@bot.event
	async def on_message(message):
		await bot.process_commands(message) # This needs to be here for commands to work
		
	@bot.event
	async def on_command_completion(ctx):
		log.debug(f"Command {ctx.command} invoked by {ctx.author.name}")
	
	@bot.event
	async def on_command_error(ctx, error, error_force=False):
		"""The event triggered when an error is raised while invoking a command.
		ctx   : Context
		error : Exception"""
		
		# Allow commands to override default error handling behaviour
		if not error_force:
			if hasattr(ctx.command, "on_error"):
				return
			
			#if ctx.cog:
			#	if commands.Cog._get_overridden_method(ctx.cog.cog_command_error) is not None:
			#		return
		
		ignored = ()
		
		# Allows us to check for original exception raised and sent to CommandInvokeError
		# If nothing is found. We keep the exception passed to on_command_error.
		# Code taken from here: https://gist.github.com/EvieePy/7822af90858ef65012ea500bcecf1612
		error = getattr(error,"original",error)
		
		# Stop here if the error is in the ignored list
		if isinstance(error,ignored):
			return
			
		elif isinstance(error, commands.MissingRequiredArgument):
			await ctx.send("%s, you're missing some arguments." % (ctx.author.mention))
			await ctx.send_help(ctx.command)
		
		elif isinstance(error, commands.UserInputError):
			await ctx.send_help()
		
		elif isinstance(error, commands.CommandNotFound):
			return await ctx.send("%s, you have typed an invalid command. You can use %shelp to view the command list." % (ctx.author.mention, ctx.prefix))
		
		elif isinstance(error, commands.CommandInvokeError):
			await ctx.send("Error in command '{}'. Please check the logs for details.".format(
				ctx.command.qualified_name
			))
			#print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
			#traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
			log.exception('Ignoring exception in command {}:'.format(ctx.command))
			
		elif isinstance(error, commands.NoPrivateMessage):
			await ctx.send("That command cannot be used in private messages.")
		
		elif isinstance(error, blueonblue.checks.ChannelUnauthorized):
			chids = error.channels # Channels in ID form
			chs = []
			for c in chids:
				ch = ctx.guild.get_channel(c)
				if ch is not None:
					chs.append(ch.mention)
			
			if len(chs)>1:
				message = "{usr}, the command '{cmd}' can only be used in the following channels: ".format(usr=ctx.author.mention,cmd=ctx.command.qualified_name)
			elif len(chs)==1:
				message = "{usr}, the command '{cmd}' can only be used in the following channel: ".format(usr=ctx.author.mention,cmd=ctx.command.qualified_name)
			else:
				message = "{usr}, the command '{cmd}' cannot be used in this channel.".format(usr=ctx.author.mention,cmd=ctx.command.qualified_name)
			
			# Add the channel identifiers to the string
			message += ", ".join(chs)
			
			await ctx.send(message)
		
		# If we don't have a handler for that error type, execute default error code.
		else:
			#print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
			log.exception('Ignoring exception in command {}:'.format(ctx.command))
			traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)