import discord
from discord.ext import commands, tasks
import blueonblue
from blueonblue.config import config
from datetime import datetime, timedelta
import json
from google.oauth2 import service_account

class Events(commands.Cog, name='Events'):

    def __init__(self, bot):
        self.bot = bot
        self.event_channel = config['SERVER']['CHANNELS']['EVENT_ANNOUNCEMENTS']

    #@commands.command(name='register_event')
    #async def register_event(self, context, text_blob: str=""):
	
		@commands.command(
		name="events",
		brief="Grabs a list of upcoming events"
		aliases=['event']
	)
	@commands.max_concurrency(1,per=commands.BucketType.channel,wait=False)
	async def events(self, ctx):
		
		# Google docs info
		scope = ['https://www.googleapis.com/auth/calendar']
		credentials = service_account.Credentials.from_service_account_file(config["MISSIONS"]["SHEET"]["API_TOKEN_FILE"])
		scoped_credentials = credentials.with_scopes(scope)
		service = build("calendar","v3", credentials=credentials)
		result = service.events().list(calendarId=config["EVENTS"]["CALENDAR"]["CALENDAR_ID"], timeMin=now, maxResults=10, singleEvents=True, orderBy='startTime').execute()
		
		# Probably don't need this
		no_events = True
		# Embed settings
		
		# Find the specific columns that we need on the sheet
		# Google sheets refer to the first cell as cell 1, so we need to add one to our indexes
		# TODO: Update this to handle errors properly
		#col_date = mission_sheet.row_values(1).index("Date") + 1
		#col_mission = mission_sheet.row_values(1).index("Mission") + 1
		#col_map = mission_sheet.row_values(1).index("Map") + 1
		#col_author = mission_sheet.row_values(1).index("Author(s)") + 1
		#col_medical = mission_sheet.row_values(1).index("Medical") + 1
		#col_contact = mission_sheet.row_values(1).index("Contact DLC") + 1
		#col_notes = mission_sheet.row_values(1).index("Notes") + 1
		
#		for i in mission_sheet.get_all_values():
#			try:
#				datevar = datetime.strptime(i[0],"%Y-%m-%d")
#			except:
#				datevar = None
#			if datevar is not None:
#				if (
#					i[2] != "" and 
#					datetime.date(datevar) > 
#					datetime.date(datetime.now() + timedelta(days=-1))
#				):
#					no_missions = False
#					missionArr = [i[2],i[3]]
#					missionURL = config["MISSIONS"]["WIKI"] + missionArr[0].replace(" ","_")
#					if i[col_contact - 1] == "TRUE":
#						missionContact = True
#					else:
#						missionContact = False
#					if i[col_medical - 1] == "Advanced":
#						missionAdvMed = True
#					else:
#						missionAdvMed = False
#					missionTitle = datetime.date(datetime.strptime(i[0],"%Y-%m-%d")).strftime("%A") + ": " + i[0]
#					
#					# Set the embed colour
#					if missionContact == True:
#						missionColour = 0x00BB00 # Green to represent Contact DLC missions
#					elif missionAdvMed == True:
#						missionColour = 0xDF0000 # Red to represent Advanced medical missions
#					else:
#						missionColour = 0x2E86C1 # Start with the default blue
#					
#					# Append notes to the embed title
#					if missionContact == True:
#						missionTitle += ", Contact DLC"
#					if missionAdvMed == True:
#						missionTitle += ", Advanced Medical"
#					
#					embed = discord.Embed(title=missionTitle, color=missionColour)
#					embed.add_field(name="Mission", value="[" + missionArr[0] + "](" + missionURL + ")", inline=True)
#					if len(missionArr) > 1:
#						embed.add_field(name="Map", value=missionArr[1], inline=True)
#					else:
#						embed.add_field(name="Map", value="None", inline=True)
#					embed.add_field(name="Author", value=i[4], inline=True)
#					if (i[col_notes - 1] != ""):
#						embed.add_field(name="Notes", value=i[col_notes -1], inline=False)
#					await ctx.send(embed=embed)
#		
#		if no_missions:
#		 	await ctx.send("There aren't any missions scheduled right now. Why don't you schedule one?")
	
def setup(bot):
	bot.add_cog(Events(bot))