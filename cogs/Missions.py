import discord
from settings import config
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import gspread
import asyncio
import json
import requests
import os
from oauth2client.service_account import ServiceAccountCredentials

class Missions(commands.Cog, name="Missions"):
	def __init__(self, bot):
		self.bot = bot
		if (
			len(config["GITLAB"]["PROJECTS"]) > 0 or
			len(config["GITHUB"]["PROJECTS"]) > 0
		):
			self.git_task_time = 0
			self.git_task.start()
	
	def cog_unload(self):
		self.git_task.cancel()

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
		mission_sheet = doc.worksheet(config["MISSIONS"]["SHEET"]["WORKSHEET"])
		no_missions = True
		# Embed settings
		
		for i in mission_sheet.get_all_values():
			if (
				i[0] != "" and i[0] != "DATES" and i[1] != "" and 
				datetime.date(datetime.strptime(i[0],"%m/%d/%y")) > 
				datetime.date(datetime.now() + timedelta(days=-1))
			):
				no_missions = False
				missionArr = i[1].split(" - ")
				missionURL = config["MISSIONS"]["WIKI"] + missionArr[0].replace(" ","_")
				embed = discord.Embed(title=datetime.date(datetime.strptime(i[0],"%m/%d/%y")).strftime("%A") + ": " + i[0], color=0x2E86C1)
				embed.add_field(name="Mission", value="[" + missionArr[0] + "](" + missionURL + ")", inline=True)
				if len(missionArr) > 1:
					embed.add_field(name="Map", value=missionArr[1], inline=True)
				else:
					embed.add_field(name="Map", value="None", inline=True)
				embed.add_field(name="Author", value=i[2], inline=True)
				await ctx.send(embed=embed)
		
		if no_missions:
			await ctx.send("There aren't any missions scheduled right now. Why don't you schedule one?")
	
	@commands.command(
		name="op_audit",
		aliases=['audit']
	)
	#@commands.has_any_role(config["SERVER"]["ROLES"]["MEMBER"])
	async def op_audit(self,ctx, *, text: str=""):
		"""Submits a mission for auditing.
		
		Missions must be attached to the message, and must be submitted in .pbo format.
		Any text present in the command will be forwarded to the auditors as a note."""
		# TODO: Write filters to ensure that missions follow the correct file naming format
		if len(ctx.message.attachments) <= 0:
			await ctx.send("You have to attach your mission in order to submit it.")
			return
		for a in ctx.message.attachments:
			if a.filename[-4:] != ".pbo":
				await ctx.send("You can only submit missions in .pbo format.")
				return
			await ctx.send("%s, your mission has been submitted for auditing." % (ctx.author.mention))
			reply = "Mission submitted for audit by %s." % (ctx.author.mention)
			if text != "":
				reply += " Notes from the author below \n```"
				reply += text
				reply += "```"
			file = os.path.join(os.getcwd(),"temp",a.filename)
			await a.save(file)
			await self.bot.get_channel(config["SERVER"]["CHANNELS"]["MISSION_AUDIT"]).send(reply, file=discord.File(file))
			os.remove(file)
	
	@commands.command(
		name="op_schedule",
		brief="Schedules a mission to be played",
		aliases=["mission_schedule","schedule"]
	)
	async def op_schedule(self,ctx, date, *, text: str=""):
		"""Missions must be present in the audit list, and must be spelled *EXACTLY* as they are in the audit list (spaces and other special characters included).
		Dates must be provided in ISO 8601 date format (YYYY-MM-DD)."""
		
		# Google docs info
		scope = ['https://spreadsheets.google.com/feeds']
		creds = ServiceAccountCredentials.from_json_keyfile_name(config["MISSIONS"]["SHEET"]["API_TOKEN_FILE"], scope)
		client = gspread.authorize(creds)
		mission_doc = client.open_by_url(config["MISSIONS"]["SHEET"]["URL"])
		mission_sheet = mission_doc.worksheet(config["MISSIONS"]["SHEET"]["WORKSHEET"])
		audit_doc = client.open_by_url(config["MISSIONS"]["AUDIT_SHEET"]["URL"])
		audit_sheet = audit_doc.worksheet(config["MISSIONS"]["AUDIT_SHEET"]["WORKSHEET"])
		
		#Verify that the date is valid
		try:
			datetime.strptime(date,"%Y-%m-%d")
		except:
			await ctx.send("%s Dates need to be sent in ISO 8601 format! (YYYY-MM-DD)" % (ctx.author.mention))
			return 0
		
		#Grab the mission info from the audit sheet
		try:
			audit_cell = audit_sheet.find(text)
		except:
			audit_cell = None
		
		if audit_cell is not None:
			audit_row = audit_sheet.row_values(audit_cell.row)
		else:
			await ctx.send("%s, I could not find that mission on the audit list." % (ctx.author.mention))
			return 0
		
		try:
			datecell = mission_sheet.find(date) #Find the cell with the matching date
		except gspread.exceptions.CellNotFound:
			datecell = None
		
		if datecell is not None:
			#Date already exists in a cell.
			if mission_sheet.cell(datecell.row,2).value == '':
				#Insert the mission info into the sheet
				mission_sheet.update_cell(datecell.row,2,audit_row[0])
				mission_sheet.update_cell(datecell.row,3,audit_row[1])
				await ctx.send("%s, the mission '%s' has been successfully scheduled for %s." % (ctx.author.mention,audit_row[0],date))
			else:
				await ctx.send("%s, a mission has already been scheduled for that date." % (ctx.author.mention))
		else:
			#Date does not exist in a cell
			await ctx.send("%s, that date has not yet been added to the mission schedule. Please be patient." % (ctx.author.mention))
	
	@tasks.loop(minutes=1, reconnect=True)
	async def git_task(self):
		if self.git_task_time == 0:
			oldtm = datetime.utcnow().replace(microsecond=0) - timedelta(minutes=1)
			self.git_task_time = oldtm.isoformat() + ".000Z"
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

			r = requests.get("%s/projects/%s/repository/commits/?since='%s'&until='%s'" % (gitlab_url_api, gitlab_project, self.git_task_time, iso_time), headers=gitlab_header)
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
			
			r = requests.get("%s/repos/%s/commits?since='%s'&until='%s'" % (github_url_api, github_project, self.git_task_time, iso_time), auth=(github_user,github_token))
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
		self.git_task_time = iso_time
	
	@git_task.before_loop
	async def before_git_task(self):
		await self.bot.wait_until_ready() # Wait until the bot is ready

def setup(bot):
	bot.add_cog(Missions(bot))