import discord
from discord.ext import commands, tasks
import blueonblue
from blueonblue.config import config
from datetime import datetime, timedelta
import gspread
import asyncio
import json
import requests
import os
from oauth2client.service_account import ServiceAccountCredentials

import logging
log = logging.getLogger("blueonblue")

async def decode_file_name(self,ctx,filename):
	"""Decodes the file name for a mission to collect information about it.
	Returns a dict of parameters if successful, otherwise returns False."""
	
	filearr = filename.split(".")
	
	# Check if the file name ends with pbo
	if filearr[-1:][0].lower() != "pbo":
		await ctx.send("Missions can only be submitted in .pbo format.")
		return False
	
	# Check if there are any erroneous periods in the file name
	if len(filearr) != 3:
		await ctx.send("File names can only have periods to denote the map and file extension.")
		return False
	
	map = filearr[-2:][0].lower() # The map will always be the second-last entry here
	
	# Check if the mission is a test mission
	if filename.split("_")[0].lower() == "test":
		arr = filename.split("_")[1:]
	else:
		arr = filename.split("_")
	
	# Grab the mission type
	try:
		type = arr[0].lower()
		if not (type in ["coop", "tvt", "cotvt", "zeus", "zgm"]):
			await ctx.send("'%s' is not a valid mission type!" % (type))
			return False
	except:
		await ctx.send("I could not determine the game type of your mission.")
		return False
	
	# Grab the player count
	try:
		playercount = int(arr[1])
	except:
		await ctx.send("I could not determine the player count in your mission.")
		return False
	
	return {"gametype": type, "playercount": playercount, "map": map}

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
		aliases=['missions','op']
	)
	@commands.max_concurrency(1,per=commands.BucketType.channel,wait=False)
	async def missions(self, ctx):
		# Google docs info
		scope = ['https://spreadsheets.google.com/feeds']
		creds = ServiceAccountCredentials.from_json_keyfile_name(config["MISSIONS"]["SHEET"]["API_TOKEN_FILE"], scope)
		client = gspread.authorize(creds)
		doc = client.open_by_url(config["MISSIONS"]["SHEET"]["URL"])
		mission_sheet = doc.worksheet(config["MISSIONS"]["SHEET"]["WORKSHEET"])
		no_missions = True
		# Embed settings
		
		# Find the specific columns that we need on the sheet
		# Google sheets refer to the first cell as cell 1, so we need to add one to our indexes
		# TODO: Update this to handle errors properly
		col_date = mission_sheet.row_values(1).index("Date") + 1
		col_mission = mission_sheet.row_values(1).index("Mission") + 1
		col_map = mission_sheet.row_values(1).index("Map") + 1
		col_author = mission_sheet.row_values(1).index("Author(s)") + 1
		col_medical = mission_sheet.row_values(1).index("Medical") + 1
		col_contact = mission_sheet.row_values(1).index("Contact DLC") + 1
		col_notes = mission_sheet.row_values(1).index("Notes") + 1
		
		for i in mission_sheet.get_all_values():
			try:
				datevar = datetime.strptime(i[0],"%Y-%m-%d")
			except:
				datevar = None
			if datevar is not None:
				if (
					i[2] != "" and 
					datetime.date(datevar) > 
					datetime.date(datetime.now() + timedelta(days=-1))
				):
					no_missions = False
					missionArr = [i[2],i[3]]
					missionURL = config["MISSIONS"]["WIKI"] + missionArr[0].replace(" ","_")
					if i[col_contact - 1] == "TRUE":
						missionContact = True
					else:
						missionContact = False
					if i[col_medical - 1] == "Advanced":
						missionAdvMed = True
					else:
						missionAdvMed = False
					missionTitle = datetime.date(datetime.strptime(i[0],"%Y-%m-%d")).strftime("%A") + ": " + i[0]
					
					# Set the embed colour
					if missionContact == True:
						missionColour = 0x00BB00 # Green to represent Contact DLC missions
					elif missionAdvMed == True:
						missionColour = 0xDF0000 # Red to represent Advanced medical missions
					else:
						missionColour = 0x2E86C1 # Start with the default blue
					
					# Append notes to the embed title
					if missionContact == True:
						missionTitle += ", Contact DLC"
					if missionAdvMed == True:
						missionTitle += ", Advanced Medical"
					
					embed = discord.Embed(title=missionTitle, color=missionColour)
					embed.add_field(name="Mission", value="[" + missionArr[0] + "](" + missionURL + ")", inline=True)
					if len(missionArr) > 1:
						embed.add_field(name="Map", value=missionArr[1], inline=True)
					else:
						embed.add_field(name="Map", value="None", inline=True)
					embed.add_field(name="Author", value=i[4], inline=True)
					if (i[col_notes - 1] != ""):
						embed.add_field(name="Notes", value=i[col_notes -1], inline=False)
					await ctx.send(embed=embed)
		
		if no_missions:
			await ctx.send("There aren't any missions scheduled right now. Why don't you schedule one?")
	
	@missions.error
	async def missions_on_error(self, ctx, error):
		if isinstance(error, commands.MaxConcurrencyReached):
			return # Ignore max concurrency errors
		else:
			await ctx.bot.on_command_error(ctx, getattr(error, "original", error), error_force=True)
	
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
			missioninfo = await decode_file_name(self,ctx,a.filename)
			if missioninfo is False:
				await ctx.send("%s, I encountered some errors when submitting your mission for auditing. "
							"Please ensure that your mission file name follows the correct naming format. "
							"\nExample: `coop_52_daybreak_v1_6.Altis.pbo`" % (ctx.author.mention))
				return 0
			await ctx.send("%s, your mission has been submitted for auditing." % (ctx.author.mention))
			reply = "Mission submitted for audit by %s." % (ctx.author.mention)
			if text != "":
				reply += " Notes from the author below \n```"
				reply += text
				reply += "```"
			file = os.path.join(os.getcwd(),"temp",a.filename)
			await a.save(file)
			mess = await self.bot.get_channel(config["SERVER"]["CHANNELS"]["MISSION_AUDIT"]).send(reply, file=discord.File(file))
			try: 
				await mess.pin()
			except discord.Forbidden:
				await self.bot.get_channel(config["SERVER"]["CHANNELS"]["MISSION_AUDIT"]).send("I do not have permissions to pin this audit.")
			except discord.NotFound:
				await self.bot.get_channel(config["SERVER"]["CHANNELS"]["MISSION_AUDIT"]).send("I ran into an issue pinning an audit message.")
			except discord.HTTPException:
				await self.bot.get_channel(config["SERVER"]["CHANNELS"]["MISSION_AUDIT"]).send("Pinning the audit message failed. The pin list might be full!")
			os.remove(file)
	
	@commands.command(
		name="op_schedule",
		brief="Schedules a mission to be played",
		aliases=["mission_schedule","schedule"]
	)
	@blueonblue.checks.in_any_channel(config["SERVER"]["CHANNELS"]["BOT"])
	@commands.guild_only()
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
		#datestr = datevar.strftime("%m/%d/%y")
		datestr = datevar.strftime("%Y-%m-%d")
		
		# Find the specific columns that we need on the sheet
		# Google sheets refer to the first cell as cell 1, so we need to add one to our indexes
		# TODO: Update this to handle errors properly
		col_date = mission_sheet.row_values(1).index("Date") + 1
		col_mission = mission_sheet.row_values(1).index("Mission") + 1
		col_map = mission_sheet.row_values(1).index("Map") + 1
		col_author = mission_sheet.row_values(1).index("Author(s)") + 1
		col_medical = mission_sheet.row_values(1).index("Medical") + 1
		col_contact = mission_sheet.row_values(1).index("Contact DLC") + 1
		col_notes = mission_sheet.row_values(1).index("Notes") + 1
		
		try:
			datecell = mission_sheet.find(datestr) #Find the cell with the matching date
		except gspread.exceptions.CellNotFound:
			datecell = None
		
		if datecell is not None:
			#Date already exists in a cell.
			if mission_sheet.cell(datecell.row,col_mission).value == '':
				#Insert the mission info into the sheet
				mission_sheet.update_cell(datecell.row,col_mission,audit_row[0])
				mission_sheet.update_cell(datecell.row,col_map,audit_row[1])
				mission_sheet.update_cell(datecell.row,col_author,audit_row[2])
				mission_sheet.update_cell(datecell.row,col_medical,"Basic")
				if audit_row[1] == "Livonia":
					mission_sheet.update_cell(datecell.row,col_contact,True)
				else:
					mission_sheet.update_cell(datecell.row,col_contact,False)
				await ctx.send("%s, the mission '%s' has been successfully scheduled for %s." % (ctx.author.mention,audit_row[0],date))
			else:
				await ctx.send("%s, a mission has already been scheduled for that date." % (ctx.author.mention))
		else:
			await ctx.send("%s, missions can not be scheduled that far in advance at this time. Please contact the mission master if you need to schedule a mission that far in advance." % (ctx.author.mention))
			#Date does not exist in a cell
			#await ctx.send("%s, that date has not yet been added to the mission schedule. Please be patient." % (ctx.author.mention))
			
			#Iterate through all available rows, find a cell that has a date that exceeds the provided date
			#colDates = mission_sheet.col_values(1)
			#dtFound = 3 #If we do not find a date, add this number to the row to insert
			
			#for idx,val in enumerate(colDates,start=1):
			#	try:
			#		dt = datetime.strptime(val, "%m/%d/%y")
			#	except:
			#		continue #If we can't make a date value, skip the cell and continue
			#	
			#	#Check to see if the date we found exceeds the scheduled date
			#	if dt > datevar:
			#		dtFound = 0
			#		break
			
			# Insert a new row with the mission info.
			# If we did not find a date that exceeds ours, we add a row at the bottom of the sheet
			#mission_sheet.insert_row([datestr,audit_row[0] + " - " + audit_row[1],audit_row[2]],idx + dtFound)
			#await ctx.send("%s, the mission '%s' has been successfully scheduled for %s." % (ctx.author.mention,audit_row[0],date))
			
	@commands.command(
		name="schedule_cancel",
		brief="Removes a mission from the schedule",
		aliases=["mission_schedule_cancel","op_schedule_cancel"]
	)
	@commands.check(blueonblue.checks.check_group_mods)
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
		datestr = datevar.strftime("%Y-%m-%d")
		
		# Check if the date exists in the schedule doc
		try:
			datecell = mission_sheet.find(datestr) #Find the cell with the matching date
		except gspread.exceptions.CellNotFound:
			# If we can't find the date, exit and let the user know.
			datecell = None
			await ctx.send("%s I could not find a mission scheduled for %s." % (ctx.author.mention,date))
			return 0
		
		# Find the specific columns that we need on the sheet
		# Google sheets refer to the first cell as cell 1, so we need to add one to our indexes
		# TODO: Update this to handle errors properly
		col_date = mission_sheet.row_values(1).index("Date") + 1
		col_mission = mission_sheet.row_values(1).index("Mission") + 1
		col_map = mission_sheet.row_values(1).index("Map") + 1
		col_author = mission_sheet.row_values(1).index("Author(s)") + 1
		col_medical = mission_sheet.row_values(1).index("Medical") + 1
		col_contact = mission_sheet.row_values(1).index("Contact DLC") + 1
		col_notes = mission_sheet.row_values(1).index("Notes") + 1
		
		# Check to make sure a mission is scheduled for that date
		if mission_sheet.cell(datecell.row,col_mission).value == "":
			# If not, let the user know.
			await ctx.send("%s I could not find a mission scheduled for %s." % (ctx.author.mention,date))
			return 0
		
		# Now that we know the date exists, we have to remove it.
		# We're going to grab the mission name so that we can let the user know.
		old_name = mission_sheet.cell(datecell.row,col_mission).value
		
		# If there are blank cells before AND after the date, it's probably a far future date.
		if (
			mission_sheet.cell(datecell.row - 1, col_date).value == "" and
			mission_sheet.cell(datecell.row + 1, col_date).value == ""
		):
			# If it's a far future date, delete the row entirely
			mission_sheet.delete_row(datecell.row)
		else:
			# If it's in the current month, clear the mission, author, and notes cells
			mission_sheet.update_cell(datecell.row,col_mission,"")
			mission_sheet.update_cell(datecell.row,col_map,"")
			mission_sheet.update_cell(datecell.row,col_author,"")
			mission_sheet.update_cell(datecell.row,col_medical,"")
			mission_sheet.update_cell(datecell.row,col_contact,False)
			mission_sheet.update_cell(datecell.row,col_notes,"")
		
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