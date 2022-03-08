import discord
from discord.ext import commands
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

def _decode_file_name(filename: str) -> dict:
	"""Decodes the file name for a mission to collect information about it.
	Returns a dict of parameters if successful, otherwise raises an error."""

	fileList = filename.split(".")

	# Check if the file name ends with ".pbo"
	if fileList[-1:][0].casefold() != "pbo":
		raise Exception("Missions can only be submitted in .pbo format.")

	# Check if there are any erroneuous periods in the file name
	if len(fileList) > 3:
		raise Exception("File names can only have periods to denote the map and file extension.")
	if len(fileList) < 3:
		raise Exception("File name appears to be missing the map definition.")

	# Get our map extension
	mapName = fileList[-2:][0].casefold()

	# Split up our map name
	nameList = fileList[0].split("_")

	# Check if the mission is a test mission
	if nameList[0].casefold() == "test":
		del nameList[0]

	# Check the mission type
	gameType = nameList[0].casefold()
	if not (gameType in ["coop", "tvt", "cotvt", "zeus", "zgm", "rpg"]):
		raise Exception(f"`{gameType}` is not a valid mission type!")

	# Grab the player count
	try:
		playerCount = int(nameList[1])
	except:
		raise Exception("I could not determine the player count in your mission.")

	return {"gameType": gameType, "map": mapName, "playerCount": playerCount}

class Missions(slash_util.Cog, name = "Missions"):
	"""Commands and functions used to view and schedule missions"""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		self.agcm = gspread_asyncio.AsyncioGspreadClientManager(self._get_google_credentials) # Authorization manager for gspread

	async def slash_command_error(self, ctx, error: Exception) -> None:
		"""Redirect slash command errors to the main bot"""
		return await self.bot.slash_command_error(ctx, error)

	def _get_google_credentials(self):
		accountFile = self.bot.config.get("GOOGLE", "api_file", fallback="config/google_api.json")
		scopes = ["https://spreadsheets.google.com/feeds"]
		creds = Credentials.from_service_account_file(accountFile, scopes = scopes)
		return creds

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
					embedURL = f"{wikiURL}/wiki/" + missionName.replace(" ","_")
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
				async with self.bot.http_session.get(f"{wikiURL}/api.php", params = {
					"action": "query",
					"format": "json",
					"prop": "pageimages",
					"titles": missionName,
					"pithumbsize": "250"
				}) as response:
					if response.status == 200: # Request successful
						responsePages: dict = (await response.json())["query"]["pages"]
						responsePageData = responsePages[list(responsePages)[0]]
						if "thumbnail" in responsePageData:
							# Check to make sure that we don't exceed any height limits
							if responsePageData["thumbnail"]["height"] <= 141: # 2:1 is ideal, but 16:9 is acceptable
								# We have a thumbnail to use
								missionImageURL = responsePageData["thumbnail"]["source"]
							else:
								missionImageURL = None
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

	@slash_util.slash_command(guild_id = blueonblue.debugServerID)
	@slash_util.describe(missionfile = "Mission file to audit. Must follow mission naming scheme.")
	@slash_util.describe(message = "Optional message. Will be submitted with your mission.")
	@slash_util.describe(modpreset = "Mod preset .html file")
	async def audit(self, ctx: slash_util.Context, missionfile: discord.Attachment, message: str = None, modpreset: discord.Attachment = None):
		"""Submits a mission for auditing"""
		# Immediately defer this action, since this can take some time.
		await ctx.defer()

		# Check to see if we have a mod preset
		if modpreset is not None:
			# Check if the mod preset has an .html extension
			if modpreset.filename.split(".")[-1].casefold() != "html":
				await ctx.send("Mod preset files must have a `.html` extension!")
				return
			else:
				# Since we have a mod preset, our mission file needs to be prefixed with "MODNIGHT"
				if missionfile.filename.split("_",1)[0].casefold() != "modnight":
					await ctx.send("Modnight missions must be prefixed with `modnight`!")
					return
				else:
					# Mission file is prefixed with modnight
					# Store our file name with the "modnight" removed for validation
					missionFilename = missionfile.filename.split("_",1)[-1]
		else:
			# No mod preset
			# Check to make sure that we don't have a modnight mission
			if missionfile.filename.split("_",1)[0].casefold() == "modnight":
				await ctx.send("Modnight missions must be submitted with a mod preset `.html` file!")
				return
			else:
				missionFilename = missionfile.filename

		# Validate the mission name
		try:
			missionInfo = _decode_file_name(missionFilename)
		except Exception as exception:
			await ctx.send(f"{exception.args[0]}"
				f"\n{ctx.author.mention}, I encountered some errors when submitting your mission `{missionfile.filename}` for auditing. "
				"Please ensure that your mission file name follows the correct naming format."
				"\nExample: `coop_52_daybreak_v1_6.Altis.pbo`")
			return

		# Mission has passed validation checks
		auditChannel: discord.TextChannel = ctx.guild.get_channel(self.bot.serverConfig.getint(str(ctx.guild.id),"channel_mission_audit", fallback = -1))

		if auditChannel is None:
			await ctx.send("I could not locate the audit channel to submit this mission for auditing. Please contact the bot owner.")
			return

		# Start creating our audit message
		if modpreset is None:
			auditMessage = f"Mission submitted for audit by {ctx.author.mention}."
		else:
			auditMessage = f"Modnight mission submitted for audit by {ctx.author.mention}."
		if message is not None:
			auditMessage += f" Notes from the audit below \n```{message}```"

		missionFileObject = await missionfile.to_file()
		auditFiles = [missionFileObject]
		if modpreset is not None:
			auditFiles.append(await modpreset.to_file())

		# Send our message to the audit channel
		auditMessageObject = await auditChannel.send(auditMessage, files = auditFiles)

		# Try to pin our message
		try:
			await auditMessageObject.pin()
		except discord.Forbidden:
			await auditChannel.send("I do not have permissions to pin this audit.")
		except discord.NotFound:
			await auditChannel.send("I ran into an issue pinning an audit message.")
		except discord.HTTPException:
			await auditChannel.send("Pinning the audit message failed. The pin list might be full!")

		# Let the user know that their mission is being submitted for audit.
		await ctx.send(f"{ctx.author.mention}, your mission `{missionfile.filename}` has been submitted for audit.")

	@slash_util.slash_command(guild_id = blueonblue.debugServerID)
	@slash_util.describe(date = "ISO 8601 formatted date (YYYY-MM-DD)")
	@slash_util.describe(missionname = "Name of the mission to schedule")
	@slash_util.describe(notes = "Optional notes to display on the schedule")
	@blueonblue.checks.in_channel_bot()
	async def schedule(self, ctx: slash_util.Context, date: str, missionname: str, notes: str = None):
		"""Schedules a mission to be played. Missions must be present on the audit list."""
		# See if we can convert out date string to a datetime object
		try:
			dateVar = datetime.strptime(date, ISO_8601_FORMAT)
		except:
			await ctx.send("Dates need to be sent in ISO 8601 format! (YYYY-MM-DD)", ephemeral=True)
			return

		# Check to make sure that the mission isn't being scheduled too far in advance
		if (dateVar - datetime.now()) > timedelta(365):
			await ctx.send("You cannot schedule missions more than one year in advance!", ephemeral=True)
			return

		# If we've passed our preliminary checks, defer the response
		# This gives us time to communicate with the wiki and google sheets
		await ctx.defer()

		# Read some config values
		missionKey = self.bot.serverConfig.get(str(ctx.guild.id), "mission_sheet_key")
		missionWorksheetName = self.bot.serverConfig.get(str(ctx.guild.id), "mission_worksheet", fallback="Schedule")

		if missionKey is None:
			await ctx.send("Could not find the URL for the mission sheet in the config file. Please contact the bot owner.")

		# Get our wiki URL
		wikiURL = self.bot.serverConfig.get(str(ctx.guild.id), "mission_wiki_url", fallback = None)

		# Start our HTTP request block
		async with self.bot.http_session.get(f"{wikiURL}/api.php", params = {
			"action": "parse",
			"page": "Audited Mission List",
			"prop": "wikitext",
			"section": 1,
			"format": "json"
		}) as response:
			if response.status == 200: # Request successful
				responseData: dict = await response.json()
				if "parse" in responseData:
					responseText: str = responseData["parse"]["wikitext"]["*"]
				else:
					await ctx.send("Could not locate the audit list on the wiki. Please contact the bot owner.")
					return
			else:
				await ctx.send(f"Could not contact the wiki to search for the audit list (Error: {response.status}). Please contact the bot owner.")

		# Now that we have our text, split it up and parse it.
		responseLines = responseText.split("\n")
		missionData = []
		for line in responseLines:
			if not line.startswith("{{"):
				# We only care about lines that start with {{
				continue
			# Remove the leading and trailing braces
			line = line.replace("{","").replace("}","")
			# Split the line by pipe
			line = line.split("|")
			# Delete the first value, this ends up being the wiki template name
			del line[0]
			# Append our line to our missionData
			missionData.append(line)

		# Now that we have our list, find the row that contains the mission in question
		mission = None
		for row in missionData:
			if row[0].casefold() == missionname.casefold():
				mission = row
				break

		# If we did not find a matching row, return an error
		if mission is None:
			await ctx.send(f"I could not find the mission `{missionname}` on the audit list.")
			return

		# Put a placeholder if the map name is missing
		if mission[1] == "":
			mission[1] = "Unknown"

		# Mission row is in format:
		# Mission, Map, Author

		#Convert the date back to a string format so that we can find it on the schedule sheet
		dateStr = dateVar.strftime(ISO_8601_FORMAT)

		# Start our spreadsheet block
		# Authorize our connection to google sheets
		googleClient = await self.agcm.authorize()

		# Get the actual mission document
		missionDoc = await googleClient.open_by_key(missionKey)
		missionSheet = await missionDoc.worksheet(missionWorksheetName)

		# See if we can find the cell with the matching date
		try:
			datecell = await missionSheet.find(dateStr)
		except:
			datecell = None



		# If we found the date cell, start writing our data
		if datecell is not None:

			# Find the mission column
			firstRow = await missionSheet.row_values(1)
			colMission = firstRow.index("Mission") + 1
			colMap = firstRow.index("Map") + 1
			colAuthor = firstRow.index("Author(s)") + 1
			colMedical = firstRow.index("Medical") + 1
			colWS = firstRow.index("Western Sahara") + 1
			colNotes = firstRow.index("Notes") + 1

			cellMission = await missionSheet.cell(datecell.row,colMission)
			if cellMission.value == None:
				# Only continue if we don't already have a mission for that date
				cellMission.value = mission[0]
				cellList = [cellMission]

				cellMap = await missionSheet.cell(datecell.row,colMap)
				cellMap.value = mission[1]
				cellList.append(cellMap)

				cellAuthor = await missionSheet.cell(datecell.row,colAuthor)
				cellAuthor.value = mission[2]
				cellList.append(cellAuthor)

				cellMedical = await missionSheet.cell(datecell.row,colMedical)
				cellMedical.value = "Basic"
				cellList.append(cellMedical)

				if mission[1] == "Sefrou-Ramal":
					cellWS = await missionSheet.cell(datecell.row,colWS)
					cellWS.value = True
					cellList.append(cellWS)

				if notes is not None:
					cellNotes = await missionSheet.cell(datecell.row,colNotes)
					cellNotes.value = notes
					cellList.append(cellNotes)
				# With our data set, write it back to the spreadsheet
				await missionSheet.update_cells(cellList)
				#await missionSheet.update(f"{datecell.address}:{secondAddr}", [rowData])
				await ctx.send(f"The mission `{mission[0]}` has been successfully scheduled for {dateStr}`")
			else:
				# Mission already scheduled
				await ctx.send(f"A mission has already been scheduled for {dateStr}")
		else:
			# Date not found. Send an error
			await ctx.send("Missions can not be scheduled that far in advance at this time. "
				"Please contact the mission master if you need to schedule a mission that far in advnace.")

	@slash_util.slash_command(guild_id = blueonblue.debugServerID)
	@slash_util.describe(date = "ISO 8601 formatted date (YYYY-MM-DD)")
	@blueonblue.checks.is_moderator()
	async def schedule_cancel(self, ctx: slash_util.Context, date: str):
		"""Removes a previously scheduled mission from the mission schedule"""
		# See if we can convert out date string to a datetime object
		try:
			dateVar = datetime.strptime(date, ISO_8601_FORMAT)
		except:
			await ctx.send("Dates need to be sent in ISO 8601 format! (YYYY-MM-DD)", ephemeral=True)
			return

		# If we've passed our preliminary checks, defer the response
		# This gives us time to communicate with the google sheets
		await ctx.defer()

		#Convert the date back to a string format so that we can find it on the schedule sheet
		dateStr = dateVar.strftime(ISO_8601_FORMAT)

		# Read some config values
		missionKey = self.bot.serverConfig.get(str(ctx.guild.id), "mission_sheet_key")
		missionWorksheetName = self.bot.serverConfig.get(str(ctx.guild.id), "mission_worksheet", fallback="Schedule")

		# Start our spreadsheet block
		# Authorize our connection to google sheets
		googleClient = await self.agcm.authorize()

		# Get the actual mission document
		missionDoc = await googleClient.open_by_key(missionKey)
		missionSheet = await missionDoc.worksheet(missionWorksheetName)

		# See if we can find the cell with the matching date
		try:
			datecell = await missionSheet.find(dateStr)
		except:
			datecell = None

		# If we found the date cell, start writing our data
		if datecell is not None:
			# Find the mission column
			firstRow = await missionSheet.row_values(1)
			colMission = firstRow.index("Mission") + 1
			colMap = firstRow.index("Map") + 1
			colAuthor = firstRow.index("Author(s)") + 1
			colMedical = firstRow.index("Medical") + 1
			colWS = firstRow.index("Western Sahara") + 1
			colNotes = firstRow.index("Notes") + 1

			cellMission = await missionSheet.cell(datecell.row,colMission)
			if cellMission.value != None:
				# Only continue if we don't already have a mission for that date
				missionName = cellMission.value
				cellMission.value = ""
				cellList = [cellMission]

				cellMap = await missionSheet.cell(datecell.row,colMap)
				cellMap.value = ""
				cellList.append(cellMap)

				cellAuthor = await missionSheet.cell(datecell.row,colAuthor)
				cellAuthor.value = ""
				cellList.append(cellAuthor)

				cellMedical = await missionSheet.cell(datecell.row,colMedical)
				cellMedical.value = ""
				cellList.append(cellMedical)

				cellWS = await missionSheet.cell(datecell.row,colWS)
				cellWS.value = False
				cellList.append(cellWS)

				cellNotes = await missionSheet.cell(datecell.row,colNotes)
				cellNotes.value = ""
				cellList.append(cellNotes)
				# With our data set, write it back to the spreadsheet
				await missionSheet.update_cells(cellList)
				await ctx.send(f"The mission `{missionName}` has been removed as the scheduled mission for {dateStr}.")
			else:
				# Mission already scheduled
				await ctx.send(f"I could not find a mission scheduled for {dateStr}.")
		else:
			# Date not found. Send an error
			await ctx.send(f"I could not find a mission scheduled for {dateStr}.")


def setup(bot: blueonblue.BlueOnBlueBot):
	bot.add_cog(Missions(bot))
