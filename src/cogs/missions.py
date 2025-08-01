import logging
import re
from datetime import datetime, timedelta, time
from typing import TypedDict
from zoneinfo import ZoneInfo

import aiohttp
import blueonblue
import discord
import pbokit
from blueonblue.defines import (
	SCONF_MISSION_DURATION,
	SCONF_MISSION_TIME,
	SCONF_MISSION_UPLOAD_URL,
	SCONF_MISSION_UPLOAD_USERNAME,
	SCONF_MISSION_UPLOAD_PASSWORD,
)
from discord import app_commands
from discord.ext import commands

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


class Missions(commands.Cog, name="Missions"):
	"""Commands and functions used to view and schedule missions"""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

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
	@app_commands.guild_only()
	@blueonblue.checks.has_configs(
		SCONF_MISSION_DURATION,
		SCONF_MISSION_TIME,
	)
	async def schedule(
		self,
		interaction: discord.Interaction,
		date: str,
		missionname: str,
		notes: str | None = None,
	):
		"""Schedules a mission to be played. Missions must be present on the audit list."""
		assert interaction.guild is not None

		startTimeStr = await self.bot.serverConfig.mission_time.get(interaction.guild)
		assert startTimeStr is not None
		durationInt = await self.bot.serverConfig.mission_duration.get(interaction.guild)
		assert durationInt is not None

		# For now this is hardcoded
		timezoneStr = "Canada/Central"
		tz = ZoneInfo(timezoneStr)

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

		# Generate the event start and end times
		startTime = datetime.combine(dateVar.date(), time.fromisoformat(startTimeStr), tzinfo=tz)
		endTime = startTime + timedelta(hours=durationInt)

		description = (
			f"{notes}\n\nScheduled by {interaction.user.mention}"
			if notes is not None
			else f"Scheduled by {interaction.user.mention}"
		)

		# Create the scheduled event
		await interaction.guild.create_scheduled_event(
			name=f"Arma 3 Ops: {missionname}",
			description=description,
			start_time=startTime,
			end_time=endTime,
			privacy_level=discord.PrivacyLevel.guild_only,
			entity_type=discord.EntityType.external,
			location="Teamspeak",
			reason=f"Mission scheduled by {interaction.user.name}",
		)

		await interaction.response.send_message(
			f"The mission `{missionname}` has been successfully scheduled for {dateVar.strftime(ISO_8601_FORMAT)}`"
		)


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Missions(bot))
