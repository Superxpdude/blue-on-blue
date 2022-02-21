import discord
from discord.ext import commands, tasks
import slash_util

from datetime import datetime, timedelta
import gspread_asyncio
from google.oauth2.service_account import Credentials

import blueonblue

import logging
log = logging.getLogger("bloeonblue")

MISSION_EMBED_WS_COLOUR = 0xC2B280
MISSION_EMBED_ADVMED_COLOUR = 0xDF0000
MISSION_EMBED_COLOUR = 0x2E86C1

ISO_8601_FORMAT = "%Y-%m-%d"

#def get_google_credentials(bot: blueonblue.BlueOnBlueBot):
def get_google_credentials():
	#accountFile = bot.config.get("GOOGLE", "api_file", fallback="data/google_api.json")
	accountFile = "data/google_api.json"
	scopes = ["https://spreadsheets.google.com/feeds"]
	creds = Credentials.from_service_account_file(accountFile, scopes = scopes)
	return creds

class Missions(slash_util.Cog, name = "Missions"):
	"""Commands and functions used to view and schedule missions"""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		self.agcm = gspread_asyncio.AsyncioGspreadClientManager(get_google_credentials) # Authorization maneger for gspread

	@slash_util.slash_command(guild_id = blueonblue.debugServerID)
	async def missions(self, ctx: slash_util.Context):
		"""Displays a list of scheduled missions"""
		# Immediately defer this action, since this can take some time.
		await ctx.defer()

		# Authorize our connection to google sheets
		googleClient = await self.agcm.authorize()
		# Read some config values
		missionKey = self.bot.serverConfig.get(str(ctx.guild.id), "mission_sheet_key")
		missionWorksheetName = self.bot.serverConfig.get(str(ctx.guild.id), "mission_worksheet", fallback="Schedule")

		if missionKey is None:
			await ctx.send("Could not find the URL for the mission sheet in the config file. Please contact the bot owner.")

		# Get the actual mission document
		missionDoc = await googleClient.open_by_key(missionKey)
		missionSheet = await missionDoc.worksheet(missionWorksheetName)

		# Get our spreadsheet contents
		sheetData = await missionSheet.get_all_records(default_blank = None)

		# Get our wiki URL
		wikiURL = self.bot.serverConfig.get(str(ctx.guild.id), "mission_wiki_url", fallback = None)

		# Get our current data
		missionEmbeds = []
		for row in sheetData:
			# Try to get a datetime object for the date
			try:
				dateVar = datetime.strptime(row["Date"], ISO_8601_FORMAT)
			except:
				# Could not convert the date object
				dateVar = None
			# Only continue if we have all of the required information
			if (
				dateVar is not None and # Make sure we have a date object
				row["Mission"] is not None and # Make sure that the "mission" value is not none
				dateVar.date() > (datetime.now() + timedelta(days=-1)).date() # Date is today, or in the future
			):
				# Get our data, and create our embed
				embedTitle = dateVar.date().strftime(f"%A: {ISO_8601_FORMAT}")
				missionName: str = row["Mission"]
				missionMap: str = row["Map"] if row["Map"] is not None else "Unknown"
				missionAuthor: str = row["Author(s)"] if row["Author(s)"] is not None else "Unknown"
				missionNotes: str = row["Notes"]

				missionWS = True if (("Western Sahara" in row.keys()) and ((row["Western Sahara"] == "TRUE") or (missionMap == "Sefrou-Ramal"))) else False
				missionAdvMed = True if row["Medical"] == "Advanced" else False

				if wikiURL is not None:
					# Wiki exists
					embedURL = wikiURL + missionName.replace(" ","_")
				else:
					embedURL = None

				# Select our embed colour
				if missionWS:
					embedColour = MISSION_EMBED_WS_COLOUR # Western Sahara CDLC
				elif missionAdvMed:
					embedColour = MISSION_EMBED_ADVMED_COLOUR # Advanced medical
				else:
					embedColour = MISSION_EMBED_COLOUR # Default blue

				# Adjust the embed title for CDLC or Adv Medical missions
				if missionWS:
					embedTitle += ", Western Sahara CDLC"
				if missionAdvMed:
					embedTitle += ", Advanced Medical"

				# Create our embed
				missionEmbed = discord.Embed(
					title = embedTitle,
					colour = embedColour
				)
				# See if we can get the mission image
				async with self.bot.http_session.get("https://wiki.tmtm.gg/api.php", params = {
					"action": "query",
					"format": "json",
					"prop": "pageimages",
					"titles": missionName,
					"pithumbsize": "150"
				}) as response:
					if response.status == 200: # Request successful
						responsePages: dict = (await response.json())["query"]["pages"]
						responsePageData = responsePages[list(responsePages)[0]]
						if "thumbnail" in responsePageData:
							# We have a thumbnail to use
							missionImageURL = responsePageData["thumbnail"]["source"]
						else:
							# No thumbnail for the mission
							missionImageURL = None
					else:
						missionImageURL = None

				if missionImageURL is not None:
					missionEmbed.set_image(url = missionImageURL)

				# Start adding our fields
				# Mission name
				if embedURL is not None:
					# URL exists
					missionEmbed.add_field(name="Mission", value=f"[{missionName}]({embedURL})", inline=True)
				else:
					missionEmbed.add_field(name="Mission", value=missionName, inline=True)
				# Map
				missionEmbed.add_field(name="Map", value=missionMap, inline=True)
				missionEmbed.add_field(name="Author", value=missionAuthor, inline=True)
				if missionNotes is not None:
					missionEmbed.add_field(name="Notes", value=missionNotes, inline=False)
				# Append our embed to our missionEmbeds array
				missionEmbeds.append(missionEmbed)

		# Now that we have our embeds, get ready to send them
		if len(missionEmbeds) > 5:
			# We can only send five embeds at once
			missionEmbeds = missionEmbeds[:5]
			message = "The next five scheduled missions are:"
		elif len(missionEmbeds) == 0:
			message = "There aren't any missions scheduled right now. Why don't you schedule one?"
		else:
			message = None
		# Send our response
		await ctx.send(message, embeds=missionEmbeds)


def setup(bot: blueonblue.BlueOnBlueBot):
	bot.add_cog(Missions(bot))
