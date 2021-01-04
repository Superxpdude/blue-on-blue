import discord
from discord.ext import commands, tasks
import blueonblue
from blueonblue.config import config
from datetime import datetime, date
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from tinydb import TinyDB, Query
import logging
log = logging.getLogger("blueonblue")

class Events(commands.Cog, name='Events'):

	def __init__(self, bot):
		self.bot = bot
		self.db = TinyDB('db/events.json', sort_keys=True, indent=4) # Define the database
		#self.event_channel = config['SERVER']['CHANNELS']['EVENT_ANNOUNCEMENTS']
	
	@commands.command(
		name="events",
		brief="Grabs a list of upcoming events",
		aliases=['event']
	)
	@commands.max_concurrency(1,per=commands.BucketType.channel,wait=False)
	async def events(self, ctx):
		
		# Database info
		planner_tbl = self.db.table('event_planners')
		
		# Google docs info
		scope = ['https://www.googleapis.com/auth/calendar']
		credentials = service_account.Credentials.from_service_account_file(config["MISSIONS"]["SHEET"]["API_TOKEN_FILE"])
		scoped_credentials = credentials.with_scopes(scope)
		service = build("calendar","v3", credentials=credentials)
		now = datetime.utcnow().isoformat() + "Z"
		tz = "America/Winnipeg"
		result = service.events().list(calendarId=config["EVENTS"]["CALENDAR"]["CALENDAR_ID"], timeMin=now, maxResults=5, singleEvents=True, orderBy='startTime', timeZone=tz).execute()
		
		if len(result["items"]) > 0:
			for e in result["items"]:
				# We need to check both in case we have events that are set up as "All day events"
				startTime = datetime.fromisoformat(e["start"]["dateTime"]) if "dateTime" in e["start"].keys() else None
				startDate = date.fromisoformat(e["start"]["date"]) if "date" in e["start"].keys() else None
				
				if "summary" not in e.keys():
					log.info("Event calendar event found with no summary")
					continue
				
				if startTime is not None:
					tz = startTime.utcoffset()
					tzText = "CST" if (tz.days * 24) + (tz.seconds / 3600) <= -6 else "CDT"
					timeText = startTime.strftime("%I:%M%p {tz}, %A: %Y-%m-%d").format(tz=tzText).lstrip("0")
				elif startDate is not None:
					timeText = startDate.strftime("%A: %Y-%m-%d")
				else:
					timeText = "Date not found"
				
				embedColour = 0x9B59B6 # Discord purple
				
				embed = discord.Embed(title=e["summary"], description=timeText, url=config["EVENTS"]["CALENDAR"]["PUBLIC_URL"], color=embedColour)
				
				if "description" in e.keys():
					embed.add_field(name="\u200b", value=e["description"], inline=False) # Zero-width blank character as the title
				
				if ("creator" in e.keys()) and ("email" in e["creator"].keys()):
					planner_info = planner_tbl.get(Query().email == e["creator"]["email"])
					if (planner_info is not None) and ("displayName" in planner_info.keys()):
						embed.set_footer(text=f"Organized by {planner_info['displayName']}")
						
				await ctx.send(embed=embed)
				
		else:
			await ctx.send("There are no events scheduled at this time.")
	
def setup(bot):
	bot.add_cog(Events(bot))