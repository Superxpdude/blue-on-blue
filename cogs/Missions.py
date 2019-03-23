import discord
from settings import config
from discord.ext import commands
from datetime import datetime
from datetime import timedelta
import gspread
import asyncio
import json
import requests
from oauth2client.service_account import ServiceAccountCredentials

class Missions(commands.Cog, name="Missions"):
	def __init__(self, bot):
		self.bot = bot
		if (
			len(config["GITLAB"]["PROJECTS"]) > 0 or
			len(config["GITHUB"]["PROJECTS"]) > 0
		):
			self.git_task = self.bot.loop.create_task(self.git_background_task())

	@commands.command(
		name="ops",
		brief="Grabs a list of upcoming missions",
		aliases=['missions']
	)
	async def missions(self, ctx):
		# Google docs info
		scope = ['https://spreadsheets.google.com/feeds']
		creds = ServiceAccountCredentials.from_json_keyfile_name(config["MISSIONS"]["SHEET"]["API_TOKEN_FILE"], scope)
		client = gspread.authorize(creds)
		doc = client.open_by_url(config["MISSIONS"]["SHEET"]["URL"])
		mission_sheet = doc.worksheet("Current Month")
		# Embed settings
		
		for i in mission_sheet.get_all_values():
			if (
				i[0] != "" and i[0] != "DATES" and i[1] != "" and 
				datetime.date(datetime.strptime(i[0],"%m/%d/%y")) > 
				datetime.date(datetime.now() + timedelta(days=-1))
			):
				missionArr = i[1].split(" - ")
				missionURL = config["MISSIONS"]["WIKI"] + missionArr[0].replace(" ","_")
				embed = discord.Embed(title=datetime.date(datetime.strptime(i[0],"%m/%d/%y")).strftime("%A") + ": " + i[0], color=0x2E86C1)
				embed.add_field(name="Mission", value="[" + missionArr[0] + "](" + missionURL + ")", inline=True)
				embed.add_field(name="Map", value=missionArr[1], inline=True)
				embed.add_field(name="Author", value=i[2], inline=True)
				await ctx.send(embed=embed)
	
	
	
	async def git_background_task(self):
		await self.bot.wait_until_ready()
		while not self.bot.is_closed():
			try:
				try:
					old_time
				except NameError:
					oldtm = datetime.utcnow().replace(microsecond=0) - timedelta(minutes=1)
					old_time = oldtm.isoformat() + ".000Z"
				time = datetime.utcnow().replace(microsecond=0)
				iso_time = time.isoformat() + ".000Z"
				
				channel = self.bot.get_channel(config["SERVER"]["CHANNELS"]["ACTIVITY"])
				
				gitlab_url_api = config["GITLAB"]["API_URL"]
				gitlab_url = config["GITLAB"]["WEB_URL"]
				gitlab_header = {'Private-Token': config["GITLAB"]["API_TOKEN"]}
				gitlab_projects = config["GITLAB"]["PROJECTS"]
				
				github_url_api = config["GITHUB"]["API_URL"]
				github_url = config["GITHUB"]["WEB_URL"]
				github_projects = config["GITHUB"]["PROJECTS"]
				github_user = config["GITHUB"]["API_USER"]
				github_token = config["GITHUB"]["API_TOKEN"]
				
				for gitlab_project in gitlab_projects:
					gitlab_project_str = str(gitlab_project)

					project_info_raw = requests.get(
						gitlab_url_api + "/projects/" + gitlab_project_str, headers=gitlab_header
					)
					project_info = json.loads(project_info_raw.text)

					r = requests.get("%s/projects/%s/repository/commits/?since='%s'&until='%s'" % (gitlab_url_api, gitlab_project, old_time, iso_time), headers=gitlab_header)
					r_dict = json.loads(r.text)

					for i in r_dict:
						embed_title = i['committer_name'] + " committed to " + project_info['path_with_namespace']
						embed_desc = i['message']
						embed_url = project_info['web_url'] + "/commit/" + i['id']
						embed = discord.Embed(title=embed_title, description=embed_desc, color=0xfc6d26)
						embed.set_author(name="Gitlab", icon_url="http://files.superxp.ca/gitlab-icon-rgb.png", url=gitlab_url)
						embed.add_field(name=i['short_id'], value="[[Gitlab]](" + embed_url + ")", inline=False)
						await channel.send(embed=embed)
				
				for github_project in github_projects:
					project_info_raw = requests.get(
						github_url_api + "/repos/" + github_project, auth=(github_user,github_token)
					)
					project_info = json.loads(project_info_raw.text)
					
					r = requests.get("%s/repos/%s/commits?since='%s'&until='%s'" % (github_url_api, github_project, old_time, iso_time), auth=(github_user,github_token))
					r_dict = json.loads(r.text)
					
					for i in r_dict:
						embed_title = i['commit']['author']['name'] + " committed to " + project_info['full_name']
						embed_desc = i['commit']['message']
						embed_url = i['html_url']
						embed = discord.Embed(title=embed_title, description=embed_desc, color=0x4078c0)
						embed.set_author(name="Github", icon_url="http://files.superxp.ca/github-icon-light.png", url=github_url)
						embed.add_field(name=i['sha'][:7], value="[[Github]](" + embed_url + ")", inline=False)
						await channel.send(embed=embed)
				
				# Mark the current time as the old time
				old_time = iso_time

				await asyncio.sleep(60)
			except Exception as e:
				print(str(e))
				await asyncio.sleep(60)

def setup(bot):
	bot.add_cog(Missions(bot))