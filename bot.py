import discord
import json
import requests
import datetime
import asyncio
import configparser
from discord.ext import commands
#print(discord.__version__)  # check to make sure at least once you're on the right version!

token = open("token.txt", "r").read()  # I've opted to just save my token to a text file.
gitlab_api = open("gitlab-api.txt", "r").read()
gitlab_header = {'Private-Token': gitlab_api}
gitlab_project = 9158064
gitlab_project_str = str(gitlab_project)

# URL to the gitlab instance
gitlab_url = "https://gitlab.com"
gitlab_url_api = gitlab_url + "/api/v4"

# Define the prefix function
def get_prefix(client, message):
	# Set the prefixes
	prefixes = ['$$']
	
	# if not message.guild:
	#	#prefixes = ['$$']
	
	# Allow users to mention the bot instead of using a prefix
	return commands.when_mentioned_or(*prefixes)(client, message)

bot = commands.Bot(
	command_prefix=get_prefix,
	description="TMTM Bot",
	case_insensitive=True #Allow commands to be case insensitive
)

@bot.command()
async def test(ctx, *args):
	await ctx.send('Hello')

@bot.command()
async def channelID(ctx):
	print(ctx.channel.id) # Prints the discord channel ID of the current channel in the console

async def no_check(ctx):
	return ctx.author.id == 1

@bot.command()
@commands.is_owner()
##@commands.check(no_check)
async def no(ctx):
	await ctx.send("Pass")

@no.error
async def no_error(ctx,error):
	if isinstance(error, commands.CheckFailure):
		await ctx.send("Fail")

bot.load_extension("cogs.BotControl")

@bot.event  # event decorator/wrapper. More on decorators here: https://pythonprogramming.net/decorators-intermediate-python-tutorial/
async def on_ready():  # method expected by client. This runs once when connected
	print(f'We have logged in as {bot.user}')  # notification of login.
	#await client.get_channel(556943548650487838).send("Channel target")
	#print(discord.utils.get(message.server.channels, name="bot-test"))
	#print(discord.utils.get(client.get_all_channels(), guild__name="Super's Notes",name="bot-test"))
	#print(discord.utils.get(server.channels,name="bot-test"))
	for server in bot.guilds:
		if server.name == "Super's Notes":
			break
	
	for channel in server.channels:
		if channel.name == "bot-test":
			break
	
	print(channel.id)
	await channel.send("Connected")


@bot.event
async def on_message(message):  # event that happens per any message.
	await bot.process_commands(message) # This line needs to be here for commands to work
#	if {client.user} != {message.author}:
#		# each message has a bunch of attributes. Here are a few.
#		# check out more by print(dir(message)) for example.
#		#print(dir(message))
#		#print(f"{message.channel}: {message.author}: {message.author.name}: {message.content}")
#		print(f"{message.channel}: {message.channel.id}: {message.author}: {message.author.name}: {message.content}")
#
#		if "$$git" in message.content.lower():
#			project_info_raw = requests.get(gitlab_url_api + "/projects/" + gitlab_project_str, headers=gitlab_header)
#			project_info = json.loads(project_info_raw.text)
#			r = requests.get(gitlab_url_api + "/projects/" + gitlab_project_str + "/repository/commits/?all=true", headers=gitlab_header)
#			r_dict = json.loads(r.text)
#			for i in r_dict:
#				#await message.channel.send(str(i['short_id']))
#				embed_title = i['committer_name'] + " committed to " + project_info['path_with_namespace']
#				embed_desc = i['message']
#				embed_url = project_info['web_url'] + "/commit/" + i['id']
#				embed = discord.Embed(title=embed_title, description=embed_desc, color=0xfc6d26)
#				embed.set_author(name="Gitlab", icon_url="http://files.superxp.ca/gitlab-icon-rgb.png", url=gitlab_url)
#				embed.add_field(name=i['short_id'], value="[[Gitlab]](" + embed_url + ")", inline=False)
#				#embed.set_footer(text=i['short_id'])
#				await message.channel.send(embed=embed)
#		
#		if "$$embed" in message.content.lower():
#			embed = discord.Embed(title="Title", description="Desc", color=0x00ff00)
#			embed.set_author(name="Gitlab", icon_url="http://files.superxp.ca/gitlab-icon-rgb.png")
#			embed.add_field(name="Field1", value="val1", inline=False)
#			embed.add_field(name="Field2", value="val2", inline=False)
#			await message.channel.send(embed=embed)
#		
#		if "$$logout" == message.content.lower():
#			await client.close()
#			
#		if "$$servers" in message.content.lower():
#			#print(dir(client))
#			print(client.guilds)

#@client.event
#async def git_background_task():
#	await client.wait_until_ready()
#	
#	while not client.is_closed():
#		try:
#			time = datetime.datetime.utcnow().replace(microsecond=0).isoformat()
#			channel = client.get_channel(556943548650487838)
#			await channel.send(time)
#			await asyncio.sleep(10)
#		except Exception as e:
#			print(str(e))
#			await asyncio.sleep(10)

#client.loop.create_task(git_background_task())
bot.run(token, bot=True, reconnect=True)  # recall my token was saved!