import discord
from discord.ext import commands, tasks
import blueonblue
from blueonblue.config import config
from blueonblue.bot import bot as bluebot
import logging
log = logging.getLogger("blueonblue")

from aiohttp import web
import asyncio

async def hello(request):
	print(request)
	print(request.headers["Host"])
	print("Host" in request.headers)
	return web.Response(text="Hello World")
	
async def msg(request):
	gld = bluebot.get_guild(config["SERVER"]["ID"])
	chnl = gld.get_channel(config["SERVER"]["CHANNELS"]["BOT"])
	await chnl.send("Web message!")
	return web.Response(text="Message sent")

async def hook_gitlab(request):
	# Make sure that our secret token is valid!
	if request.headers["x-gitlab-token"] != config["WEB"]["GITLAB-TOKEN"]:
		log.warning("Gitlab token does not match config file: [%s]" % (request.headers["x-gitlab-token"]))
		return web.Response(status=403)
	
	gld = bluebot.get_guild(config["SERVER"]["ID"])
	chnl = gld.get_channel(config["SERVER"]["CHANNELS"]["BOT"])
	
	
	
async def hook(request):
	data = await request.json()
	if request.headers["Content-Type"] == "application/json":
		print("JSON!")
		print(data["event_name"])
#	if request.body_exists:
#		print(await request.read())
	return web.Response(status=200)

async def webserver_start(self):
	app = web.Application()
	app.add_routes([web.get('/', hello)])
	app.add_routes([web.get('/msg', msg)])
	runner = web.AppRunner(app)
	await runner.setup()
	site = web.TCPSite(runner, 'localhost', 8080)
	self._webrunner = runner
	await site.start()

async def webserver_close(self):
	await self._webrunner.cleanup()

class Web(commands.Cog, name="Web"):
	"""Web server test cog."""
	def __init__(self,bot):
		self.bot = bot
		asyncio.get_event_loop().create_task(webserver_start(self))
	
	def cog_unload(self):
		asyncio.get_event_loop().create_task(webserver_close(self))

def setup(bot):
	bot.add_cog(Web(bot))