import datetime
import logging
from zoneinfo import ZoneInfo

import aiohttp
import blueonblue
import discord
from blueonblue.defines import ARMASTATS_EMBED_COLOUR, TIMEZONE
from discord import app_commands
from discord.ext import commands, tasks

_log = logging.getLogger(__name__)


@app_commands.guild_only()
class ArmaStats(commands.GroupCog, group_name="armastats"):
	"""Arma Stats commands."""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	async def cog_load(self):
		self.stats_loop.start()

	async def cog_unload(self):
		self.stats_loop.stop()

	@app_commands.command(name="me")
	@app_commands.guild_only()
	async def me(self, interaction: discord.Interaction):
		"""Displays your Arma 3 mission stats

		Parameters
		----------
		interaction : discord.Interaction
			The Discord interaction
		"""
		assert interaction.guild is not None

		mission_min_duration = await self.bot.serverConfig.arma_stats_min_duration.get(interaction.guild)
		mission_min_players = await self.bot.serverConfig.arma_stats_min_players.get(interaction.guild)
		mission_participation_threshold = await self.bot.serverConfig.arma_stats_participation_threshold.get(
			interaction.guild
		)

		async with self.bot.pool.acquire() as conn:
			async with conn.cursor() as cursor:
				# First, we need to check if we have a linked steam account
				# Get the user's data from the DB
				await cursor.execute(
					"SELECT steam64_id FROM verify WHERE discord_id = :id AND steam64_id NOT NULL",
					{"id": interaction.user.id},
				)
				userData = await cursor.fetchone()  # This will only return users that are verified
				if userData is None:
					await interaction.response.send_message(
						"It doesn't look like you have a Steam account verified with the bot.\n\
						Please use the `/verify steam` command to verify your steam account before using this command.",
						ephemeral=True,
					)
					return

				# The user has a linked steam account, count how many missions they have attended

				# Query the database
				# This will return the number of missions in the database that the user has participated in
				# It will only count them if they were longer than the duration threshold,
				await cursor.execute(
					"SELECT count(*) as mission_count\
					FROM mission_attendance_view\
					WHERE\
						discord_id = :userid AND\
						server_id = :serverid AND\
						player_session >= :duration AND\
						(main_op IS NOT NULL OR\
						(mission_duration >= :min_time AND\
						user_attendance >= :min_players));",
					{
						"userid": interaction.user.id,
						"serverid": interaction.guild.id,
						"duration": mission_participation_threshold,
						"min_time": mission_min_duration,
						"min_players": mission_min_players,
					},
				)
				data = await cursor.fetchone()
				mission_count: int = data["mission_count"]

				# Get our "position" in the leaderboard
				await cursor.execute(
					"SELECT	COUNT(*) as position\
					FROM\
						(SELECT\
							COUNT(steam64_id) as mission_count\
						FROM\
							mission_attendance_view\
						WHERE\
							server_id = :serverid AND\
							player_session >= :duration AND\
							(main_op IS NOT NULL OR\
							(mission_duration >= :min_time AND\
							user_attendance >= :min_players))\
						GROUP BY\
							steam64_id)\
					WHERE\
						mission_count > :missioncount",
					{
						"serverid": interaction.guild.id,
						"duration": mission_participation_threshold,
						"min_time": mission_min_duration,
						"min_players": mission_min_players,
						"missioncount": mission_count,
					},
				)
				# This will give us the number of users that are ahead of us on the leaderboard
				position: int = (await cursor.fetchone())["position"]
				# Increment the position by one to get our correct position.
				position += 1

				# Start generating our embed
				embed = discord.Embed(
					title="Mission Leaderboard",
					color=ARMASTATS_EMBED_COLOUR,
					description=f"{mission_count} missions",
				)
				embed.set_author(
					name=f"{interaction.user.display_name} - Rank {position}",
					icon_url=interaction.user.display_avatar.url,
				)

				await interaction.response.send_message(embed=embed)

	@app_commands.command()
	@app_commands.guild_only()
	@app_commands.choices(
		board=[
			app_commands.Choice(name="Recent", value=1),
			app_commands.Choice(name="All-Time", value=0),
		]
	)
	async def leaderboard(self, interaction: discord.Interaction, board: app_commands.Choice[int]):
		"""Displays the Arma stats leaderboard

		Parameters
		----------
		interaction : discord.Interaction
			The Discord interaction
		"""
		assert interaction.guild is not None
		leaderboard_count = 5

		mission_min_duration = await self.bot.serverConfig.arma_stats_min_duration.get(interaction.guild)
		mission_min_players = await self.bot.serverConfig.arma_stats_min_players.get(interaction.guild)
		mission_participation_threshold = await self.bot.serverConfig.arma_stats_participation_threshold.get(
			interaction.guild
		)
		leaderboard_recent_days = await self.bot.serverConfig.arma_stats_leaderboard_recent_days.get(interaction.guild)

		embedType: str

		# Start the DB block
		async with self.bot.pool.acquire() as conn:
			async with conn.cursor() as cursor:
				# Read config values

				# Query the database to get our leaderboard
				if board.value == 0:
					embedType = "All-Time"
					await cursor.execute(
						"SELECT\
							discord_id,\
							steam64_id,\
							COUNT(steam64_id) as mission_count\
						FROM\
							mission_attendance_view\
						WHERE\
							server_id = :serverid AND\
							player_session >= :duration AND\
							(main_op IS NOT NULL OR\
							(mission_duration >= :min_time AND\
							user_attendance >= :min_players))\
						GROUP BY\
							steam64_id\
						ORDER BY\
							mission_count DESC",
						{
							"serverid": interaction.guild.id,
							"duration": mission_participation_threshold,
							"min_time": mission_min_duration,
							"min_players": mission_min_players,
						},
					)
				else:
					embedType = f"Recent ({leaderboard_recent_days} days)"
					await cursor.execute(
						"SELECT\
							discord_id,\
							steam64_id,\
							COUNT(steam64_id) as mission_count\
						FROM\
							mission_attendance_view\
						WHERE\
							server_id = :serverid AND\
							player_session >= :duration AND\
							(main_op IS NOT NULL OR\
							(mission_duration >= :min_time AND\
							user_attendance >= :min_players)) AND\
							start_time >= :start_time\
						GROUP BY\
							steam64_id\
						ORDER BY\
							mission_count DESC",
						{
							"serverid": interaction.guild.id,
							"duration": mission_participation_threshold,
							"min_time": mission_min_duration,
							"min_players": mission_min_players,
							"start_time": (
								discord.utils.utcnow() - datetime.timedelta(days=leaderboard_recent_days)
							).isoformat(),
						},
					)
				data = await cursor.fetchmany(leaderboard_count)

		# We no longer need the database connection, so we can close the context manager
		embed = discord.Embed(title=f"Mission Leaderboard - {embedType}", color=ARMASTATS_EMBED_COLOUR)

		# Create our message text
		for count, row in enumerate(data):
			# If the user is not in the guild, return their stored display name instead of using a mention
			user = interaction.client.get_user(row["discord_id"]) or (await interaction.client.fetch_user(row["discord_id"]))
			if user is not None:
				userText: str = user.mention
			else:
				userText: str = "Unknown"
			embed.add_field(
				name=f"Rank {count + 1}",
				value=f"{userText} - {row['mission_count']} missions",
				inline=False,
			)

		if len(embed.fields) == 0:
			embed.description = "No users on leaderboard yet"

		await interaction.response.send_message(embed=embed)

	@tasks.loop(hours=1)
	async def stats_loop(self):
		"""Loop to periodically grab arma stats from the API server, and add them to the local database"""
		# The "end time" value gets constantly updated whenever the API server hears from the game server
		# We need to throw out missions that have extremely recent end times in case they are still running.
		_log.debug("Starting Arma stats update loop")
		start_id: int

		# Get our DB connection
		# Start our DB block
		async with self.bot.db.connect() as db:
			async with db.connection.cursor() as cursor:
				# Iterate once through each discord server that we're in
				for guild in self.bot.guilds:
					api_url = await self.bot.serverConfig.arma_stats_url.get(guild)
					api_key = await self.bot.serverConfig.arma_stats_key.get(guild)

					mission_participation_threshold = await self.bot.serverConfig.arma_stats_participation_threshold.get(
						guild.id
					)
					raffleweight_increase = await self.bot.serverConfig.raffleweight_increase.get(guild.id)
					raffleweight_max = await self.bot.serverConfig.raffleweight_max.get(guild.id)

					# Only proceed if we have a valid URL and key for the API
					if api_url is not None and api_key is not None:
						_log.info(f"Updating Arma stats for guild: [{guild.name}|{guild.id}]")
						# Get the latest mission ID from this guild
						await cursor.execute(
							"SELECT max(api_id) as max_id \
							FROM arma_stats_missions \
							WHERE server_id = :guild_id",
							{"guild_id": guild.id},
						)
						max_id_row = await cursor.fetchone()
						if max_id_row["max_id"] is None:
							start_id = 0
						else:
							start_id = max_id_row["max_id"] + 1
						_log.debug(f"Requesting information on missions starting at ID: {start_id}")

						# Now that we have the ID that we want to start from, we can make our web request
						try:
							async with self.bot.httpSession.get(
								f"{api_url}/missions",
								headers={"X-Api-Token": api_key},
								params={"start_id": str(start_id)},
							) as response:
								# Get our response data
								missionData: list = await response.json()
						except aiohttp.ClientResponseError as error:
							_log.warning(
								f"Received HTTP error {error.status} when "
								"connecting to Arma stats API for guild: "
								f"[{guild.name}|{guild.id}]"
							)
							continue

						# Assume by this point that we have our successfully decoded JSON
						for mission in missionData:
							name: str = mission["file_name"]
							mission_id: int = mission["id"]
							# API should provide dates in UTC format
							start_time = datetime.datetime.fromisoformat(mission["start_time"])
							end_time = datetime.datetime.fromisoformat(mission["end_time"])
							mission_pings: int = mission["pings"]
							players: list = mission["players"]

							# Check to make sure that our end time was at least 15 minutes ago
							if (discord.utils.utcnow() - datetime.timedelta(minutes=15)) < end_time:
								_log.debug(f"Mission {name} is still in progress. Skipping")
								continue

							# Check to see if our mission is a main op
							main_op_time = datetime.datetime.combine(
								start_time.astimezone(ZoneInfo(TIMEZONE)).date(),
								datetime.time(hour=21, minute=30),
								tzinfo=ZoneInfo(TIMEZONE),
							)

							if (
								(start_time.astimezone(ZoneInfo(TIMEZONE)).weekday() in [3, 5, 6])
								and (start_time < main_op_time)
								and (end_time > main_op_time)
							):
								main_op = True
							else:
								main_op = None

							# Mission end time is at least 15 minutes ago, process the mission
							# Create the mission entry, and get its database ID
							await cursor.execute(
								"INSERT INTO arma_stats_missions\
								(server_id, api_id, file_name, start_time, end_time, main_op)\
								VALUES (\
									:server_id, :api_id, :name, :start, :end_time, :main_op)",
								{
									"server_id": guild.id,
									"api_id": mission_id,
									"name": name,
									"start": start_time.isoformat(),
									"end_time": end_time.isoformat(),
									"main_op": main_op,
								},
							)

							await cursor.execute("SELECT last_insert_rowid() as db_id")
							db_id: int = (await cursor.fetchone())["db_id"]

							# Now that the mission is in the DB, iterate through our players list
							for player in players:
								player_id: str = player["steam_id"]
								player_pings: int = player["pings"]
								player_duration = player_pings / mission_pings

								# Only proceed if we have a valid playerID
								if str(player_id).isnumeric():
									# Insert the player details into the database
									await cursor.execute(
										"INSERT INTO arma_stats_players\
										(mission_id, steam_id, duration)\
										VALUES (:mission_id, :steam_id, :duration)",
										{
											"mission_id": db_id,
											"steam_id": player_id,
											"duration": player_duration,
										},
									)

									# Update the user's mission raffle weight if they played for long enough on a main op
									if (player_duration >= mission_participation_threshold) and main_op:
										# Get the player's discord ID from the verify DB
										await cursor.execute(
											"SELECT discord_id FROM verify WHERE steam64_id = :id",
											{"id": player_id},
										)
										data = await cursor.fetchone()
										if data is not None:
											discord_id: int = data["discord_id"]
											_log.debug(f"Increasing raffle weight for user: ({discord_id})")
											await db.raffleWeight.increaseWeight(
												guild.id,
												discord_id,
												raffleweight_increase,
												raffleweight_max,
											)

						_log.info(f"Finished updating Arma stats for guild: [{guild.name}|{guild.id}]")

					else:
						_log.debug(f"Missing Arma stats API information for guild: [{guild.name}|{guild.id}]. Skipping.")

				# Commit db changes
				await db.commit()

	@stats_loop.before_loop
	async def before_gold_loop(self):
		await self.bot.wait_until_ready()  # Wait until the bot is ready


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(ArmaStats(bot))
