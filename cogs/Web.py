import discord
from discord.ext import commands, tasks
import blueonblue
from blueonblue.config import config
from blueonblue.bot import bot as bluebot
import logging
log = logging.getLogger("blueonblue")

from aiohttp import web
import asyncio
import hmac
import hashlib

async def hello(request):
	print(request)
	print(request.headers["Host"])
	print("Host" in request.headers)
	return web.Response(text="Hello World")

async def hook_gitlab(request):
	# Check if we were sent some JSON data
	if request.headers["Content-Type"] != "application/json":
		log.info("Gitlab webhook received with content type: [%s]" % (request.headers["Content-Type"]))
		return web.Response(status=415) # Return "Unsupported Media Type" if we did not receive json
	
	# Make sure that our secret token is valid!
	if request.headers["x-gitlab-token"] != config["WEB"]["GITLAB-TOKEN"]:
		log.warning("Gitlab token does not match config file: [%s]" % (request.headers["x-gitlab-token"]))
		return web.Response(status=401) # Return "Unauthorized" if the token did not match
	
	# Now that we know the data is good, we can do something with it
	# TODO: See if I can find a way to return the HTTP-200 response before sending the discord notifications
	gld = bluebot.get_guild(config["SERVER"]["ID"])
	chnl = gld.get_channel(config["SERVER"]["CHANNELS"]["ACTIVITY"])
	data = await request.json()
	
	# Push event
	if data["event_name"].casefold() == "push".casefold():
		log.info(f"Gitlab webhook received. Push event for project {data['project']['path_with_namespace']}")
		repo_name = data["project"]["name"]
		repo_branch = data["ref"].split("/")[2]
		# Iterate through all of our commits
		for c in data["commits"]:
			embed_title = f"{c['author']['name']} committed to [{repo_name}:{repo_branch}]"
			embed_desc = c["message"]
			embed_url = c["url"]
			embed = discord.Embed(title=embed_title, description=embed_desc, color=0x4078c0)
			embed.set_author(name="Gitlab", icon_url"http://files.superxp.ca/gitlab-icon-light.png", url=config["GITLAB"]["WEB_URL"])
			embed.add_field(name=c["id"][:7], value="[[Github]](" + embed_url + ")", inline=False)
			await channel.send(embed=embed)
	
	# Return the web response
	return web.Response(status=200)
	
async def hook_github(request):
	# Check if we were sent some JSON data
	if request.headers["Content-Type"] != "application/json":
		log.info("Github webhook received with content type: [%s]" % (request.headers["Content-Type"]))
		return web.Response(status=415) # Return "Unsupported Media Type" if we did not receive json
	
	# Check to ensure that the data is valid, and encoded with the github token
	payload = await request.read() # Grab the raw data payload
	signature = hmac.new(config["WEB"]["GITHUB-TOKEN"].encode(), payload, hashlib.sha1).hexdigest() # Calculate the hash using the github token, and the payload
	
	#Compare the hash that was sent with the one that we calculated
	if not hmac.compare_digest(signature, request.headers["x-hub-signature"].split("=")[1]):
		# If no match, return a 401 unauthorized
		log.warning("Github webhook received with invalid signature.")
		return web.Response(status=401) # Return "Unauthorized" if the signature did not match
	
	# Now that we know the data is good, we can do something with it
	# TODO: See if I can find a way to return the HTTP-200 response before sending the discord notifications
	gld = bluebot.get_guild(config["SERVER"]["ID"])
	chnl = gld.get_channel(config["SERVER"]["CHANNELS"]["ACTIVITY"])
	data = await request.json()
	
	# Push event
	if request.headers["x-github-event"].casefold() == "push".casefold():
		log.info(f"Github webhook received. Push event for repository {data['repository']['full_name']}")
		repo_name = data["repository"]["full_name"].split("/")[1]
		repo_branch = data["ref"].split("/")[2]
		# Iterate through all of our commits
		for c in data["commits"]:
			embed_title = f"{c['author']['name']} committed to [{repo_name}:{repo_branch}]"
			embed_desc = c["message"]
			embed_url = c["url"]
			embed = discord.Embed(title=embed_title, description=embed_desc, color=0x4078c0)
			embed.set_author(name="Github", icon_url"http://files.superxp.ca/github-icon-light.png", url=config["GITHUB"]["WEB_URL"])
			embed.add_field(name=c["id"][:7], value="[[Github]](" + embed_url + ")", inline=False)
			await channel.send(embed=embed)
	
	# New release published (THIS SECTION WIP)
#	if request.headers["x-github-event"].casefold() == "push".casefold():
#		# Only act if the release was published
#		if data["action"].casefold() == "published".casefold():
		
	# Return the web response
	return web.Response(status=200)

async def webserver_start(self):
	app = web.Application()
	app.add_routes([web.get('/', hello),web.post("/github",hook_github),web.post("/gitlab",hook_gitlab)])
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