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
import blueonblue

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
		
		# Audit sheet row format:
		# ["Mission Name", "Author", "Version", "Auditor", "Audit Date", "Expiry Date", "Modpack version", "CRC32 Hash"]
		
		#Verify that the date is valid
		try:
			datevar = datetime.strptime(date,"%Y-%m-%d")
		except:
			await ctx.send("%s Dates need to be sent in ISO 8601 format! (YYYY-MM-DD)" % (ctx.author.mention))
			return 0
		
		# Check to ensure that the mission is not being scheduled too far in advance
		if (datevar - datetime.now()) > timedelta(365):
			await ctx.send("%s, you cannot schedule missions more than one year in advance!" % (ctx.author.mention))
			return 0
		
		# Google docs info
		scope = ['https://spreadsheets.google.com/feeds']
		creds = ServiceAccountCredentials.from_json_keyfile_name(config["MISSIONS"]["SHEET"]["API_TOKEN_FILE"], scope)
		client = gspread.authorize(creds)
		mission_doc = client.open_by_url(config["MISSIONS"]["SHEET"]["URL"])
		mission_sheet = mission_doc.worksheet(config["MISSIONS"]["SHEET"]["WORKSHEET"])
		
		# The audit list is stored on a wiki
		# The values here need to be moved to a config file at some point
		#audit_doc = client.open_by_url(config["MISSIONS"]["AUDIT_SHEET"]["URL"])
		#audit_sheet = audit_doc.worksheet(config["MISSIONS"]["AUDIT_SHEET"]["WORKSHEET"])
		r_url = "https://wiki.tmtm.gg/api.php"
		r_params = {
			"action": "parse",
			"page": "Audited Mission List",
			"prop": "wikitext",
			"section": 1,
			"format": "json"
		}
		
		# Grab the text from the wiki
		r_res = requests.Session().get(url=r_url, params=r_params)
		r_data = r_res.json()
		r_txt = r_data["parse"]["wikitext"]["*"] # Grab the text from the result
		r_lines = r_txt.split("\n") # Split text by newline
		
		# Iterate through the result to generate a list of lists containing the table
		r_entries = [] # Define our empty list first
		for l in r_lines:
			if not l.startswith("{{"): # We only care about lines that start with {{
				continue
			# Remove the leading and trailing curly braces
			l = l.replace("{","")
			l = l.replace("}","")
			l = l.split("|") # Split the line using pipes
			del l[0] # Delete the first value, this is the template name on the wiki
			r_entries.append(l)
		
		# Now that we have our list, find the row that contains the mission in question
		for audit_row in r_entries:
			if audit_row[0].lower() == text.lower():
				break
			audit_row = None
		
		# If we did not find a matching row, return an error
		if audit_row is None:
			await ctx.send("%s, I could not find that mission on the audit list." % (ctx.author.mention))
			return 0
			
		# Put a placeholder if the map name is missing
		if audit_row[1] == "":
			audit_row[1] = "TBD"
		
		#Grab the mission info from the audit sheet
		#try:
		#	audit_cell = audit_sheet.find(text)
		#except:
		#	audit_cell = None
		
		#if audit_cell is not None:
		#	audit_row = audit_sheet.row_values(audit_cell.row)
		#else:
		#	await ctx.send("%s, I could not find that mission on the audit list." % (ctx.author.mention))
		#	return 0
			
		#Convert the date from ISO 8601 to MM/DD/YY for compatibility with the existing doc
		datestr = datevar.strftime("%m/%d/%y")
		
		try:
			datecell = mission_sheet.find(datestr) #Find the cell with the matching date
		except gspread.exceptions.CellNotFound:
			datecell = None
		
		if datecell is not None:
			#Date already exists in a cell.
			if mission_sheet.cell(datecell.row,2).value == '':
				#Insert the mission info into the sheet
				mission_sheet.update_cell(datecell.row,2,audit_row[0] + " - " + audit_row[1])
				mission_sheet.update_cell(datecell.row,3,audit_row[2])
				await ctx.send("%s, the mission '%s' has been successfully scheduled for %s." % (ctx.author.mention,audit_row[0],date))
			else:
				await ctx.send("%s, a mission has already been scheduled for that date." % (ctx.author.mention))
		else:
			#Date does not exist in a cell
			#await ctx.send("%s, that date has not yet been added to the mission schedule. Please be patient." % (ctx.author.mention))
			
			#Iterate through all available rows, find a cell that has a date that exceeds the provided date
			colDates = mission_sheet.col_values(1)
			dtFound = 3 #If we do not find a date, add this number to the row to insert
			
			for idx,val in enumerate(colDates,start=1):
				try:
					dt = datetime.strptime(val, "%m/%d/%y")
				except:
					continue #If we can't make a date value, skip the cell and continue
				
				#Check to see if the date we found exceeds the scheduled date
				if dt > datevar:
					dtFound = 0
					break
			
			# Insert a new row with the mission info.
			# If we did not find a date that exceeds ours, we add a row at the bottom of the sheet
			mission_sheet.insert_row([datestr,audit_row[0] + " - " + audit_row[1],audit_row[2]],idx + dtFound)
			await ctx.send("%s, the mission '%s' has been successfully scheduled for %s." % (ctx.author.mention,audit_row[0],date))
			
	@commands.command(
		name="schedule_cancel",
		brief="Removes a mission from the schedule",
		aliases=["mission_schedule_cancel","op_schedule_cancel"]
	)
	@commands.check(blueonblue.check_group_mods)
	async def op_schedule_cancel(self,ctx, date):
		"""The date must be provided in the ISO 8601 date format (YYYY-MM-DD)."""
		
		#Verify that the date is valid
		try:
			datevar = datetime.strptime(date,"%Y-%m-%d")
		except:
			await ctx.send("%s Dates need to be sent in ISO 8601 format! (YYYY-MM-DD)" % (ctx.author.mention))
			return 0
		
		# Google docs info
		scope = ['https://spreadsheets.google.com/feeds']
		creds = ServiceAccountCredentials.from_json_keyfile_name(config["MISSIONS"]["SHEET"]["API_TOKEN_FILE"], scope)
		client = gspread.authorize(creds)
		mission_doc = client.open_by_url(config["MISSIONS"]["SHEET"]["URL"])
		mission_sheet = mission_doc.worksheet(config["MISSIONS"]["SHEET"]["WORKSHEET"])
		
		# Convert the date from ISO 8601 to MM/DD/YY for compatibility with the existing doc
		datestr = datevar.strftime("%m/%d/%y")
		
		# Check if the date exists in the schedule doc
		try:
			datecell = mission_sheet.find(datestr) #Find the cell with the matching date
		except gspread.exceptions.CellNotFound:
			# If we can't find the date, exit and let the user know.
			datecell = None
			await ctx.send("%s I could not find a mission scheduled for %s." % (ctx.author.mention,date))
			return 0
		
		# Check to make sure a mission is scheduled for that date
		if mission_sheet.cell(datecell.row,2).value == "":
			# If not, let the user know.
			await ctx.send("%s I could not find a mission scheduled for %s." % (ctx.author.mention,date))
			return 0
		
		# Now that we know the date exists, we have to remove it.
		# We're going to grab the mission name so that we can let the user know.
		old_name = mission_sheet.cell(datecell.row,2).value.split(" - ")[0]
		
		# If there are blank cells before AND after the date, it's probably a far future date.
		if (
			mission_sheet.cell(datecell.row - 1, 1).value == "" and
			mission_sheet.cell(datecell.row + 1, 1).value == ""
		):
			# If it's a far future date, delete the row entirely
			mission_sheet.delete_row(datecell.row)
		else:
			# If it's in the current month, clear the mission, author, and notes cells
			mission_sheet.update_cell(datecell.row,2,"")
			mission_sheet.update_cell(datecell.row,3,"")
			mission_sheet.update_cell(datecell.row,4,"")
		
		# Let the user know that we have cleared the mission schedule
		await ctx.send("%s, '%s' has been removed as the scheduled mission for %s." % (ctx.author.mention,old_name,date))
	
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