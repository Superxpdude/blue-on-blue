import logging
import re
from datetime import datetime, timedelta
from typing import TypedDict

import aiohttp
import blueonblue
import discord
import gspread_asyncio
import pbokit
from blueonblue.defines import (
	GOOGLE_API_FILE,
	MISSION_EMBED_ADVMED_COLOUR,
	MISSION_EMBED_COLOUR,
	MISSION_EMBED_WS_COLOUR,
	SCONF_CHANNEL_MISSION_AUDIT,
	SCONF_MISSION_SHEET_KEY,
	SCONF_MISSION_WIKI_URL,
	SCONF_MISSION_WORKSHEET,
	SCONF_MISSION_UPLOAD_URL,
	SCONF_MISSION_UPLOAD_USERNAME,
	SCONF_MISSION_UPLOAD_PASSWORD,
)
from discord import app_commands
from discord.ext import commands, tasks
from google.oauth2.service_account import Credentials
from gspread.utils import ValueInputOption

_log = logging.getLogger(__name__)


ISO_8601_FORMAT = "%Y-%m-%d"

VALID_GAMETYPES = ["coop", "tvt", "cotvt", "rptvt", "zeus", "zgm", "rpg"]


class MissionFileNameInfo(TypedDict):
	gameType: str
	map: str
	playerCount: int


def _decode_file_name(filename: str) -> MissionFileNameInfo:
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

	if len(nameList) == 0:
		raise Exception("File name appears to be missing the gametype and playercount")

	# Check the mission type
	gameType = nameList[0].casefold()
	if gameType not in VALID_GAMETYPES:
		raise Exception(f"`{gameType}` is not a valid mission type!")

	# Grab the player count
	try:
		playerCount = int(nameList[1])
	except ValueError:
		raise Exception("I could not determine the player count in your mission.")

	missionInfo: MissionFileNameInfo = {
		"gameType": gameType,
		"map": mapName,
		"playerCount": playerCount,
	}
	return missionInfo


class MissionAuditView(blueonblue.views.AuthorResponseViewBase):
	"""View for mission audits
	Used to hold the button to trigger the audit modal upon the audit checks succeeding"""

	message: discord.WebhookMessage

	def __init__(
		self,
		bot: blueonblue.BlueOnBlueBot,
		author: discord.User | discord.Member,
		auditFile: discord.Attachment,
		*args,
		modpackFile: discord.Attachment | None,
		timeout: float = 600.0,
		**kwargs,
	):
		self.bot = bot
		self.auditFile = auditFile
		self.modpackFile = modpackFile
		super().__init__(author, *args, timeout=timeout, **kwargs)
		self.add_item(MissionAuditButton())


class MissionAuditButton(discord.ui.Button):
	"""Button to trigger the audit modal to appear"""

	view: MissionAuditView

	def __init__(
		self,
		*args,
		label: str = "Submit Audit",
		style: discord.ButtonStyle = discord.ButtonStyle.primary,
		**kwargs,
	):
		super().__init__(*args, label=label, style=style, **kwargs)

	async def callback(self, interaction: discord.Interaction):
		# Send the modal response
		auditModal = MissionAuditModal(self.view, self.view.auditFile, modpackFile=self.view.modpackFile)
		await interaction.response.send_modal(auditModal)


class MissionAuditModal(discord.ui.Modal, title="Mission Audit Notes"):
	def __init__(
		self,
		originalView: MissionAuditView,
		auditFile: discord.Attachment,
		*args,
		modpackFile: discord.Attachment | None,
		timeout=1200,
		**kwargs,
	):
		self.originalView = originalView
		self.auditFile = auditFile
		self.modpackFile = modpackFile
		super().__init__(*args, timeout=timeout, **kwargs)

	audit_notes = discord.ui.TextInput(
		label="Please enter your audit notes here",
		style=discord.TextStyle.long,
		placeholder="Ex. Added more tasks, removed some vehicles, etc.",
		required=True,
		max_length=1500,
	)

	async def on_submit(self, interaction: discord.Interaction):
		# This modal should only ever appear in a guild context
		assert interaction.guild is not None

		await self.originalView.terminate()  # Terminate the original view when the modal is submitted
		# We need to respond to the modal so that it doesn't error out
		await interaction.response.send_message("Audit received. Beginning upload.", ephemeral=True)

		# Old code below
		auditChannel = await self.originalView.bot.serverConfig.channel_mission_audit.get(interaction.guild)

		if auditChannel is None:
			# This should never trigger since this check is also done in the originl audit command
			# But we're going to keep it here anyways
			await interaction.followup.send(
				"I could not locate the audit channel to submit this mission for auditing. Please contact the bot owner."
			)
			return

		assert isinstance(auditChannel, discord.TextChannel)

		# Start creating our audit message
		if self.modpackFile is None:
			auditMessage = f"Mission submitted for audit by {interaction.user.mention}."
		else:
			auditMessage = f"Modnight mission submitted for audit by {interaction.user.mention}."

		# The audit message is required now, so we can append it to the end.
		auditMessage += f" Notes from the mission maker below \n```\n{self.audit_notes.value}```"

		missionFileObject = await self.auditFile.to_file()
		auditFiles = [missionFileObject]
		if self.modpackFile is not None:
			auditFiles.append(await self.modpackFile.to_file())

		# Send our message to the audit channel
		auditMessageObject = await auditChannel.send(auditMessage, files=auditFiles)

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
		await interaction.followup.send(
			f"{interaction.user.mention}, your mission `{self.auditFile.filename}` has been submitted for audit."
		)


class Missions(commands.Cog, name="Missions"):
	"""Commands and functions used to view and schedule missions"""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot
		self.agcm = gspread_asyncio.AsyncioGspreadClientManager(
			self._get_google_credentials
		)  # Authorization manager for gspread
		# Initialize our mission cache
		self.missionCache = {}

	async def cog_load(self):
		self.mission_cache_update_loop.start()

	async def cog_unload(self):
		self.mission_cache_update_loop.stop()

	def _get_google_credentials(self):
		scopes = ["https://spreadsheets.google.com/feeds"]
		creds = Credentials.from_service_account_file(GOOGLE_API_FILE, scopes=scopes)
		return creds

	@tasks.loop(hours=1, reconnect=True)
	async def mission_cache_update_loop(self):
		"""Periodically updates the mission cache"""
		_log.debug("Updating mission cache")
		await self._update_all_caches()
		_log.debug("Mission cache update complete")

	@mission_cache_update_loop.before_loop
	async def before_mission_cache_loop(self):
		# Wait until the bot is ready
		await self.bot.wait_until_ready()

	async def _update_all_caches(self):
		"""Updates all guild caches present on the bot.
		Purges the existing cache before updating."""
		self.missionCache = {}
		for guild in self.bot.guilds:
			await self._update_guild_cache(guild)

	async def _update_guild_cache(self, guild: discord.Guild):
		"""Updates the mission cache for a single guild"""
		wikiURL = await self.bot.serverConfig.mission_wiki_url.get(guild)
		if wikiURL is not None:
			# Guild has a wiki URL defined
			async with self.bot.httpSession.get(
				f"{wikiURL}/api.php",
				params={
					"action": "parse",
					"page": "Audited Mission List",
					"prop": "wikitext",
					"section": "1",
					"format": "json",
				},
			) as response:
				if response.status != 200:  # Request failed
					return
				# Get the data from our request
				responseData: dict = await response.json()
				if "parse" not in responseData:  # Invalid response from wiki
					return

			responseText: str = responseData["parse"]["wikitext"]["*"]
			responseLines = responseText.split("\n")
			missionList: list[str] = []
			for line in responseLines:
				if not line.startswith("{{"):
					# We only care if the line starts with {{
					continue
				# Remove the leading and trailing braces
				line = line.replace("{", "").replace("}", "")
				# Split the line by pipe
				line = line.split("|")
				# Delete the first value, this ends up being the wiki template name
				del line[0]
				# Append the mission name to the mission list
				missionList.append(line[0])

			# Set the cache from our mission list
			self.missionCache[guild.id] = missionList

		else:
			# Guild has no wiki URL defined
			self.missionCache[guild.id] = []

	async def mission_autocomplete(self, interaction: discord.Interaction, current: str):
		"""Function to handle autocompletion of missions present on the audit list"""
		if (interaction.guild is None) or (interaction.guild.id not in self.missionCache):
			# If the guild doesn't exist, or the cache doesn't exist return nothing
			return []
		else:
			# Command called in guild, and cache exists for that guild
			return [
				app_commands.Choice(name=mission, value=mission)
				for mission in self.missionCache[interaction.guild.id]
				if current.lower() in mission.lower()
			][:25]

	@app_commands.command(name="missions")
	@app_commands.guild_only()
	@blueonblue.checks.has_configs(SCONF_MISSION_SHEET_KEY, SCONF_MISSION_WORKSHEET, SCONF_MISSION_WIKI_URL)
	async def missions(self, interaction: discord.Interaction):
		"""Displays a list of scheduled missions"""

		# Guild-only command. Guild will always be defined
		assert interaction.guild is not None

		missionKey = await self.bot.serverConfig.mission_sheet_key.get(interaction.guild)
		assert missionKey is not None
		missionWorksheetName = await self.bot.serverConfig.mission_worksheet.get(interaction.guild)
		assert missionWorksheetName is not None
		wikiURL = await self.bot.serverConfig.mission_wiki_url.get(interaction.guild)
		assert wikiURL is not None

		# Immediately defer this action, since this can take some time.
		await interaction.response.defer()

		# Authorize our connection to google sheets
		googleClient = await self.agcm.authorize()

		# Get the actual mission document
		missionDoc = await googleClient.open_by_key(missionKey)
		missionSheet = await missionDoc.worksheet(missionWorksheetName)

		# Get our spreadsheet contents
		# TODO: Change this to no longer require type ignore
		sheetData = await missionSheet.get_all_records(default_blank=None)  # type: ignore

		# Get our current data
		missionEmbeds = []
		for row in sheetData:
			# Try to get a datetime object for the date
			try:
				dateVar = datetime.strptime(row["Date"], ISO_8601_FORMAT)
			except ValueError:
				# Could not convert the date object
				dateVar = None
			# Only continue if we have all of the required information
			if (
				dateVar is not None  # Make sure we have a date object
				and row["Mission"] is not None  # Make sure that the "mission" value is not none
				and dateVar.date() > (datetime.now() + timedelta(days=-1)).date()  # Date is today, or in the future
			):
				# Get our data, and create our embed
				embedTitle = dateVar.date().strftime(f"%A: {ISO_8601_FORMAT}")
				missionName: str = row["Mission"]
				missionMap: str = row["Map"] if row["Map"] is not None else "Unknown"
				missionAuthor: str = row["Author(s)"] if row["Author(s)"] is not None else "Unknown"
				missionNotes: str = row["Notes"]

				missionWS = (
					True
					if (
						("Western Sahara" in row.keys())
						and ((row["Western Sahara"] == "TRUE") or (missionMap == "Sefrou-Ramal"))
					)
					else False
				)
				missionAdvMed = True if row["Medical"] == "Advanced" else False

				if wikiURL is not None:
					# Wiki exists
					embedURL = f"{wikiURL}/wiki/" + missionName.replace(" ", "_")
				else:
					embedURL = None

				# Select our embed colour
				if missionWS:
					embedColour = MISSION_EMBED_WS_COLOUR  # Western Sahara CDLC
				elif missionAdvMed:
					embedColour = MISSION_EMBED_ADVMED_COLOUR  # Advanced medical
				else:
					embedColour = MISSION_EMBED_COLOUR  # Default blue

				# Adjust the embed title for CDLC or Adv Medical missions
				if missionWS:
					embedTitle += ", Western Sahara CDLC"
				if missionAdvMed:
					embedTitle += ", Advanced Medical"

				# Create our embed
				missionEmbed = discord.Embed(title=embedTitle, colour=embedColour)
				# See if we can get the mission image
				try:
					async with self.bot.httpSession.get(
						f"{wikiURL}/api.php",
						params={
							"action": "query",
							"format": "json",
							"prop": "pageimages",
							"titles": missionName,
							"pithumbsize": "250",
						},
					) as response:
						responsePages: dict = (await response.json())["query"]["pages"]
						responsePageData = responsePages[list(responsePages)[0]]
						if "thumbnail" in responsePageData:
							# Check to make sure that we don't exceed any height limits
							if responsePageData["thumbnail"]["height"] <= 141:  # 2:1 is ideal, but 16:9 is acceptable
								# We have a thumbnail to use
								missionImageURL = responsePageData["thumbnail"]["source"]
							else:
								missionImageURL = None
						else:
							# No thumbnail for the mission
							missionImageURL = None

					if missionImageURL is not None:
						missionEmbed.set_image(url=missionImageURL)
				except aiohttp.ClientResponseError as error:
					if error.status not in [404]:
						_log.warning(
							f"Received HTTP error {error.status} from wiki when retrieving mission image for: {missionName}"
						)
					pass
				except aiohttp.ClientConnectorError:
					_log.warning(f"Unable to connect to mission wiki at {wikiURL} to retrieve mission images")
				except:
					raise

				# Start adding our fields
				# Mission name
				if embedURL is not None:
					# URL exists
					missionEmbed.add_field(
						name="Mission",
						value=f"[{missionName}]({embedURL})",
						inline=True,
					)
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
		if message is not None:
			await interaction.followup.send(message, embeds=missionEmbeds)
		else:
			await interaction.followup.send(embeds=missionEmbeds)

	@app_commands.command(name="audit")
	@app_commands.describe(
		missionfile="Mission file to audit. Must follow mission naming scheme",
		modpreset="Mod preset .html file",
	)
	@app_commands.guild_only()
	@blueonblue.checks.has_configs(SCONF_CHANNEL_MISSION_AUDIT)
	async def audit(
		self,
		interaction: discord.Interaction,
		missionfile: discord.Attachment,
		modpreset: discord.Attachment | None = None,
	):
		"""Submits a mission for auditing"""
		assert interaction.guild is not None

		auditChannel = await self.bot.serverConfig.channel_mission_audit.get(interaction.guild)
		assert auditChannel is not None

		# Immediately defer the response
		await interaction.response.defer()

		# Check to see if we have a mod preset
		if modpreset is not None:
			# Check if the mod preset has an .html extension
			if modpreset.filename.split(".")[-1].casefold() != "html":
				await interaction.followup.send("Mod preset files must have a `.html` extension!")
				return
			else:
				# Since we have a mod preset, our mission file needs to be prefixed with "MODNIGHT"
				if missionfile.filename.split("_", 1)[0].casefold() != "modnight":
					await interaction.followup.send("Modnight missions must be prefixed with `modnight`!")
					return
				else:
					# Mission file is prefixed with modnight
					# Store our file name with the "modnight" removed for validation
					missionFilename = missionfile.filename.split("_", 1)[-1]
		else:
			# No mod preset
			# Check to make sure that we don't have a modnight mission
			if missionfile.filename.split("_", 1)[0].casefold() == "modnight":
				await interaction.followup.send("Modnight missions must be submitted with a mod preset `.html` file!")
				return
			else:
				missionFilename = missionfile.filename

		# Validate the mission name
		try:
			missionInfo = _decode_file_name(missionFilename)
		except Exception as exception:
			await interaction.followup.send(
				f"{exception.args[0]}"
				f"\n{interaction.user.mention}, I encountered some errors when submitting your mission `{missionfile.filename}` for auditing. "
				"Please ensure that your mission file name follows the correct naming format."
				"\nExample: `coop_52_daybreak_v1_6.Altis.pbo`"
			)
			return

		# Start doing some validation on the contents of the mission file
		try:
			missionFileBytes = await missionfile.read()
			# missionPBO = pboutil.PBOFile.from_bytes(missionFileBytes)
			missionPBO = pbokit.PBO.from_bytes(missionFileBytes)
		except Exception:
			await interaction.followup.send(
				"I encountered an error verifying the validity of your mission file."
				"\nPlease ensure that you are submitting a mission in PBO format, exported from the Arma 3 editor."
			)
			return

		# PBO file is good, scan the description.ext
		try:
			if missionPBO.has_file("description.ext"):
				descriptionFile = missionPBO["description.ext"].as_str()
			else:
				raise Exception
		except Exception:
			await interaction.followup.send(
				"I encountered an issue reading your mission's `description.ext` file."
				"\nPlease ensure that your mission contains a description.ext file, with a filename in all-lowercase."
			)
			return

		# Use a regex search to find the briefingName in the description.ext file
		briefingMatch = re.search(r"(?<=^briefingName\s=\s[\"\'])[^\"\']*", descriptionFile, re.I | re.M)

		if briefingMatch is None:
			await interaction.followup.send(
				"I could not determine the `briefingName` of your mission from its `description.ext` file."
				"\nPlease ensure that your mission has a `briefingName` defined."
			)
			return

		briefingName = briefingMatch.group()

		# Now that we have the briefingName, we need to validate it.
		# Correct naming structure: COOP 52+2 - Daybreak v1.8
		# Start by setting up a regex match for the briefing name
		briefingRe = re.compile(
			r"^(?P<modnight>modnight )?(?:(?P<gametype>[a-zA-Z]+) )?"
			r"(?P<playercount>\d+)?(?:\+(?P<extracount>\d*))? ?(?:\- *)?(?P<name>.*?)"
			r"(?: v?(?P<version>\d+(?:\.\d+)*?))?$",
			re.MULTILINE + re.IGNORECASE,
		)

		# Scan the briefing name to extract information
		briefingNameMatch = briefingRe.fullmatch(briefingName)

		# If the briefingName did not follow the format specified by the regex
		if briefingNameMatch is None:
			await interaction.followup.send(
				"The `briefingName` entry in your `description.ext` file does not appear to follow the mission naming guidelines."
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		bModnight = briefingNameMatch.group("modnight")
		bGametype = briefingNameMatch.group("gametype")
		bPlayerCount = briefingNameMatch.group("playercount")
		bExtraCount = briefingNameMatch.group("extracount")
		bName = briefingNameMatch.group("name")
		bVersion = briefingNameMatch.group("version")

		# briefingName exists, check to make sure that we have detected a gametype, playercont, name, and version
		if (modpreset is not None) and (bModnight is None):
			await interaction.followup.send(
				'Modnight missions must have their `briefingName` entries in `description.ext` prefixed with "MODNIGHT".'
				f"\nDetected `briefingName` was: `{briefingNameMatch.group()}`"
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		if bGametype is None:
			await interaction.followup.send(
				"Could not determine your mission's gametype from the `briefingName` entry in your `description.ext` file."
				f"\nDetected `briefingName` was: `{briefingNameMatch.group()}`"
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		if bPlayerCount is None:
			await interaction.followup.send(
				"Could not determine your mission's player count from the `briefingName` entry in your `description.ext` file."
				f"\nDetected `briefingName` was: `{briefingNameMatch.group()}`"
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		if bName is None:
			await interaction.followup.send(
				"Could not determine your mission's name from the `briefingName` entry in your `description.ext` file."
				f"\nDetected `briefingName` was: `{briefingNameMatch.group()}`"
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		if bVersion is None:
			await interaction.followup.send(
				"Could not determine your mission's version from the `briefingName` entry in your `description.ext` file."
				f"\nDetected `briefingName` was: `{briefingNameMatch.group()}`"
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		if bGametype.casefold() not in VALID_GAMETYPES:
			await interaction.followup.send(
				f"The gametype `{bGametype}` found in the `briefingName` entry in your `description.ext` file is not a valid gametype."
				f"\nDetected `briefingName` was: `{briefingNameMatch.group()}`"
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		# Mission has passed validation checks
		# Create our playercount string
		playerCountString = str(bPlayerCount) if bExtraCount is None else f"{bPlayerCount} + {bExtraCount}"
		# Create our view
		view = MissionAuditView(self.bot, interaction.user, missionfile, modpackFile=modpreset)
		# Send the response
		# Everything else in the audit process is done through callbacks in the view and accompanying modal
		message = await interaction.followup.send(
			f"Audit checks complete for mission `{missionfile.filename}`."
			"\nThe following information has been detected for this mission:"
			"```"
			f"Gametype     : {bGametype}\n"
			f"Mission Name : {bName}\n"
			f"Playercount  : {playerCountString}\n"
			f"Map          : {missionInfo['map']}\n"
			f"Version      : {bVersion}```"
			"If the information above looks correct, click the button below to submit your mission for audit.",
			view=view,
			wait=True,
		)
		view.message = message

	@app_commands.command(name="upload_mission")
	@app_commands.describe(missionfile="Mission file to upload")
	@app_commands.default_permissions(manage_messages=True)
	@app_commands.guild_only()
	@blueonblue.checks.has_configs(
		SCONF_MISSION_UPLOAD_URL,
		SCONF_MISSION_UPLOAD_USERNAME,
		SCONF_MISSION_UPLOAD_PASSWORD,
	)
	async def upload(self, interaction: discord.Interaction, missionfile: discord.Attachment):
		"""Uploads a mission to the Arma server"""
		assert interaction.guild is not None

		# Immediately defer the response
		await interaction.response.defer()

		# Validate the mission name
		try:
			_decode_file_name(missionfile.filename)
		except Exception as exception:
			await interaction.followup.send(
				f"{exception.args[0]}"
				f"\n{interaction.user.mention}, I encountered some errors when uploading your mission `{missionfile.filename}`. "
				"Please ensure that your mission file name follows the correct naming format."
				"\nExample: `coop_52_daybreak_v1_6.Altis.pbo`"
			)
			return

			# Start doing some validation on the contents of the mission file
		try:
			missionFileBytes = await missionfile.read()
			# missionPBO = pboutil.PBOFile.from_bytes(missionFileBytes)
			missionPBO = pbokit.PBO.from_bytes(missionFileBytes)
		except Exception:
			await interaction.followup.send(
				"I encountered an error verifying the validity of your mission file."
				"\nPlease ensure that you are submitting a mission in PBO format, exported from the Arma 3 editor."
			)
			return

		# PBO file is good, scan the description.ext
		try:
			if missionPBO.has_file("description.ext"):
				descriptionFile = missionPBO["description.ext"].as_str()
			else:
				raise Exception
		except Exception:
			await interaction.followup.send(
				"I encountered an issue reading your mission's `description.ext` file."
				"\nPlease ensure that your mission contains a description.ext file, with a filename in all-lowercase."
			)
			return

		# Use a regex search to find the briefingName in the description.ext file
		briefingMatch = re.search(r"(?<=^briefingName\s=\s[\"\'])[^\"\']*", descriptionFile, re.I | re.M)

		if briefingMatch is None:
			await interaction.followup.send(
				"I could not determine the `briefingName` of your mission from its `description.ext` file."
				"\nPlease ensure that your mission has a `briefingName` defined."
			)
			return

		briefingName = briefingMatch.group()

		# Now that we have the briefingName, we need to validate it.
		# Correct naming structure: COOP 52+2 - Daybreak v1.8
		# Start by setting up a regex match for the briefing name
		briefingRe = re.compile(
			r"^(?:test )?(?:(?P<gametype>[a-zA-Z]+) )?"
			r"(?P<playercount>\d+)?(?:\+(?P<extracount>\d*))? ?(?:\- *)?(?P<name>.*?)"
			r"(?: v?(?P<version>\d+(?:\.\d+)*?))?$",
			re.MULTILINE + re.IGNORECASE,
		)

		# Scan the briefing name to extract information
		briefingNameMatch = briefingRe.fullmatch(briefingName)

		# If the briefingName did not follow the format specified by the regex
		if briefingNameMatch is None:
			await interaction.followup.send(
				"The `briefingName` entry in your `description.ext` file does not appear to follow the mission naming guidelines."
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		bGametype = briefingNameMatch.group("gametype")
		bPlayerCount = briefingNameMatch.group("playercount")
		bName = briefingNameMatch.group("name")
		bVersion = briefingNameMatch.group("version")

		# briefingName exists, check to make sure that we have detected a gametype, playercont, name, and version
		if bGametype is None:
			await interaction.followup.send(
				"Could not determine your mission's gametype from the `briefingName` entry in your `description.ext` file."
				f"\nDetected `briefingName` was: `{briefingNameMatch.group()}`"
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		if bPlayerCount is None:
			await interaction.followup.send(
				"Could not determine your mission's player count from the `briefingName` entry in your `description.ext` file."
				f"\nDetected `briefingName` was: `{briefingNameMatch.group()}`"
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		if bName is None:
			await interaction.followup.send(
				"Could not determine your mission's name from the `briefingName` entry in your `description.ext` file."
				f"\nDetected `briefingName` was: `{briefingNameMatch.group()}`"
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		if bVersion is None:
			await interaction.followup.send(
				"Could not determine your mission's version from the `briefingName` entry in your `description.ext` file."
				f"\nDetected `briefingName` was: `{briefingNameMatch.group()}`"
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		if bGametype.casefold() not in VALID_GAMETYPES:
			await interaction.followup.send(
				f"The gametype `{bGametype}` found in the `briefingName` entry in your `description.ext` file is not a valid gametype."
				f"\nDetected `briefingName` was: `{briefingNameMatch.group()}`"
				"\nPlease ensure that your mission is named according to the mission naming guidelines. Example: `COOP 52+1 - Daybreak v1.8`.",
				ephemeral=True,
			)
			return

		# Mission is ready to upload
		uploadURL = await self.bot.serverConfig.mission_upload_url.get(interaction.guild)
		uploadUsername = await self.bot.serverConfig.mission_upload_username.get(interaction.guild)
		uploadPassword = await self.bot.serverConfig.mission_upload_password.get(interaction.guild)

		assert uploadURL is not None
		assert uploadUsername is not None
		assert uploadPassword is not None

		# Append a slash to the end of the upload URL if needed
		if uploadURL[-1] != "/":
			uploadURL += "/"

		# Create basic authentication object
		authObj = aiohttp.BasicAuth(login=uploadUsername, password=uploadPassword)

		async with self.bot.httpSession.head(
			url=f"{uploadURL}{missionfile.filename}", auth=authObj, raise_for_status=False
		) as response:
			if response.status != 404:
				await interaction.followup.send(
					f"Unable to upload mission `{missionfile.filename}`. File already exists on server."
				)
				return

		async with self.bot.httpSession.put(
			url=f"{uploadURL}{missionfile.filename}", auth=authObj, raise_for_status=False, data=missionFileBytes
		) as response:
			if response.status == 201:
				await interaction.followup.send(
					f"Mission `{missionfile.filename}` uploaded successfully.", files=[await missionfile.to_file()]
				)
				return
			else:
				await interaction.followup.send(f"Error `{response.status}` uploading mission `{missionfile.filename}`.")
				return

	@app_commands.command(name="schedule")
	@app_commands.describe(
		date="ISO 8601 formatted date (YYYY-MM-DD)",
		missionname="Name of the mission to schedule",
		notes="Optional notes to display on the schedule",
	)
	@app_commands.autocomplete(missionname=mission_autocomplete)
	@app_commands.guild_only()
	@blueonblue.checks.has_configs(SCONF_MISSION_SHEET_KEY, SCONF_MISSION_WORKSHEET, SCONF_MISSION_WIKI_URL)
	async def schedule(
		self,
		interaction: discord.Interaction,
		date: str,
		missionname: str,
		notes: str | None = None,
	):
		"""Schedules a mission to be played. Missions must be present on the audit list."""
		assert interaction.guild is not None

		missionKey = await self.bot.serverConfig.mission_sheet_key.get(interaction.guild)
		assert missionKey is not None
		missionWorksheetName = await self.bot.serverConfig.mission_worksheet.get(interaction.guild)
		assert missionWorksheetName is not None
		wikiURL = await self.bot.serverConfig.mission_wiki_url.get(interaction.guild)
		assert wikiURL is not None

		# See if we can convert out date string to a datetime object
		try:
			dateVar = datetime.strptime(date, ISO_8601_FORMAT)
		except ValueError:
			await interaction.response.send_message("Dates need to be sent in ISO 8601 format! (YYYY-MM-DD)", ephemeral=True)
			return

		# Check to make sure that the mission isn't being scheduled too far in advance
		if (dateVar - datetime.now()) > timedelta(365):
			await interaction.response.send_message(
				"You cannot schedule missions more than one year in advance!",
				ephemeral=True,
			)
			return

		# If we've passed our preliminary checks, defer the response
		# This gives us time to communicate with the wiki and google sheets
		await interaction.response.defer()

		# Start our HTTP request block
		try:
			async with self.bot.httpSession.get(
				f"{wikiURL}/api.php",
				params={
					"action": "parse",
					"page": "Audited Mission List",
					"prop": "wikitext",
					"section": "1",
					"format": "json",
				},
			) as response:
				responseData: dict = await response.json()
				responseText: str = responseData["parse"]["wikitext"]["*"]
		except aiohttp.ClientResponseError as error:
			await interaction.followup.send(
				f"Could not contact the wiki to search for the audit list (Error: {error.status}). Please contact the bot owner."
			)
			_log.warning(f"Received HTTP error {error.status} when trying to read the audit list from the wiki.")
			return
		except:
			await interaction.followup.send("Error reading audit list from wiki. Please contact the bot owner.")
			raise

		# Now that we have our text, split it up and parse it.
		responseLines = responseText.split("\n")
		missionData: list[list[str]] = []
		for line in responseLines:
			if not line.startswith("{{"):
				# We only care about lines that start with {{
				continue
			# Remove the leading and trailing braces
			line = line.replace("{", "").replace("}", "")
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
			await interaction.followup.send(f"I could not find the mission `{missionname}` on the audit list.")
			return

		# Put a placeholder if the map name is missing
		if mission[1] == "":
			mission[1] = "Unknown"

		# Mission row is in format:
		# Mission, Map, Author

		# Convert the date back to a string format so that we can find it on the schedule sheet
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
		except Exception:
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

			cellMission = await missionSheet.cell(datecell.row, colMission)
			if cellMission.value is None:
				# Only continue if we don't already have a mission for that date
				cellMission.value = mission[0]
				cellList = [cellMission]

				cellMap = await missionSheet.cell(datecell.row, colMap)
				cellMap.value = mission[1]
				cellList.append(cellMap)

				cellAuthor = await missionSheet.cell(datecell.row, colAuthor)
				cellAuthor.value = mission[2]
				cellList.append(cellAuthor)

				cellMedical = await missionSheet.cell(datecell.row, colMedical)
				cellMedical.value = "Basic"
				cellList.append(cellMedical)

				if mission[1] == "Sefrou-Ramal":
					cellWS = await missionSheet.cell(datecell.row, colWS)
					cellWS.value = "True"
					cellList.append(cellWS)

				if notes is not None:
					cellNotes = await missionSheet.cell(datecell.row, colNotes)
					cellNotes.value = notes
					cellList.append(cellNotes)
				# With our data set, write it back to the spreadsheet
				await missionSheet.update_cells(cellList, value_input_option=ValueInputOption.user_entered)
				# await missionSheet.update(f"{datecell.address}:{secondAddr}", [rowData])
				await interaction.followup.send(f"The mission `{mission[0]}` has been successfully scheduled for {dateStr}`")
			else:
				# Mission already scheduled
				await interaction.followup.send(f"A mission has already been scheduled for {dateStr}")
		else:
			# Date not found. Send an error
			await interaction.followup.send(
				"Missions can not be scheduled that far in advance at this time. "
				"Please contact the mission master if you need to schedule a mission that far in advance."
			)

	@app_commands.command(name="schedule_cancel")
	@app_commands.describe(date="ISO 8601 formatted date (YYYY-MM-DD)")
	@app_commands.guild_only()
	@app_commands.default_permissions(manage_messages=True)
	@blueonblue.checks.has_configs(SCONF_MISSION_SHEET_KEY, SCONF_MISSION_WORKSHEET, SCONF_MISSION_WIKI_URL)
	async def schedule_cancel(self, interaction: discord.Interaction, date: str):
		"""Removes a previously scheduled mission from the mission schedule"""
		assert interaction.guild is not None

		missionKey = await self.bot.serverConfig.mission_sheet_key.get(interaction.guild)
		assert missionKey is not None
		missionWorksheetName = await self.bot.serverConfig.mission_worksheet.get(interaction.guild)
		assert missionWorksheetName is not None

		# See if we can convert out date string to a datetime object
		try:
			dateVar = datetime.strptime(date, ISO_8601_FORMAT)
		except ValueError:
			await interaction.response.send_message("Dates need to be sent in ISO 8601 format! (YYYY-MM-DD)", ephemeral=True)
			return

		# If we've passed our preliminary checks, defer the response
		# This gives us time to communicate with the google sheets
		await interaction.response.defer()

		# Convert the date back to a string format so that we can find it on the schedule sheet
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
		except Exception:
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

			cellMission = await missionSheet.cell(datecell.row, colMission)
			if cellMission.value is not None:
				# Only continue if we don't already have a mission for that date
				missionName = cellMission.value
				cellMission.value = ""
				cellList = [cellMission]

				cellMap = await missionSheet.cell(datecell.row, colMap)
				cellMap.value = ""
				cellList.append(cellMap)

				cellAuthor = await missionSheet.cell(datecell.row, colAuthor)
				cellAuthor.value = ""
				cellList.append(cellAuthor)

				cellMedical = await missionSheet.cell(datecell.row, colMedical)
				cellMedical.value = ""
				cellList.append(cellMedical)

				cellWS = await missionSheet.cell(datecell.row, colWS)
				cellWS.value = "False"
				cellList.append(cellWS)

				cellNotes = await missionSheet.cell(datecell.row, colNotes)
				cellNotes.value = ""
				cellList.append(cellNotes)
				# With our data set, write it back to the spreadsheet
				await missionSheet.update_cells(cellList, value_input_option=ValueInputOption.user_entered)
				await interaction.followup.send(
					f"The mission `{missionName}` has been removed as the scheduled mission for {dateStr}."
				)
			else:
				# Mission already scheduled
				await interaction.followup.send(f"I could not find a mission scheduled for {dateStr}.")
		else:
			# Date not found. Send an error
			await interaction.followup.send(f"I could not find a mission scheduled for {dateStr}.")


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Missions(bot))
