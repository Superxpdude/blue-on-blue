import logging

import aiohttp
import blueonblue
import discord
from blueonblue.defines import VERIFY_EMBED_COLOUR
from blueonblue.lib import steam
from discord import app_commands
from discord.ext import commands

_log = logging.getLogger(__name__)


# Discord views
class VerifySteamView(blueonblue.views.AuthorResponseViewBase):
	message: discord.WebhookMessage
	"""View for steam verification"""

	def __init__(
		self,
		bot: blueonblue.BlueOnBlueBot,
		author: discord.User | discord.Member,
		steamID: str,
		*args,
		timeout: float = 1800.0,
		**kwargs,
	):
		self.bot = bot
		self.steamID = steamID
		super().__init__(author, *args, timeout=timeout, **kwargs)
		self.add_item(VerifyButton())


class CheckInView(blueonblue.views.AuthorResponseViewBase):
	message: discord.Message
	"""View for steam verification"""

	def __init__(
		self,
		bot: blueonblue.BlueOnBlueBot,
		author: discord.User | discord.Member,
		steamID: str,
		*args,
		timeout: float = 1800.0,
		**kwargs,
	):
		self.bot = bot
		self.steamID = steamID
		super().__init__(author, *args, timeout=timeout, **kwargs)
		self.add_item(CheckInButton())


# Discord buttons
class VerifyButton(discord.ui.Button):
	"""Button to verify a user"""

	view: VerifySteamView

	def __init__(
		self,
		*args,
		label: str = "Verify",
		style: discord.ButtonStyle = discord.ButtonStyle.primary,
		**kwargs,
	):
		super().__init__(*args, label=label, style=style, **kwargs)

	async def callback(self, interaction: discord.Interaction):
		# Immediately defer the interaction response so that we can make web requests
		await interaction.response.defer(ephemeral=True)
		# Check the steam profile to see if it has the token set
		try:
			verified = await steam.check_guild_token(self.view.bot, self.view.steamID, str(interaction.user.id))
		except aiohttp.ClientResponseError as error:
			_log.warning(f"Received response code [{error.status}] from the Steam API when checking steam URL")
			await interaction.followup.send(steam_return_error_text(error.status))
			return
		except Exception:
			_log.exception("Error checking Steam profile")
			await interaction.followup.send(
				"Error encountered checking Steam profile. Please contact an administrator for assistance."
			)
			return

		if not verified:
			await interaction.followup.send(
				"I was unable to validate the token in your Steam profile. Please ensure that your Steam profile visibility is set to **public**, "
				'and that you have the following token in your Steam profile\'s "real name" field:\n'
				f"```{interaction.user.id}```",
				ephemeral=True,
			)
			return

		# User is now confirmed to be verified, set the data in the DB
		async with self.view.bot.pool.acquire() as conn:
			# Clean up any other matching steamID entries
			await conn.execute(
				"UPDATE verify SET steam64_id = NULL WHERE steam64_id = :steamID",
				{"steamID": int(self.view.steamID)},
			)
			await conn.execute(
				"INSERT OR REPLACE INTO verify (discord_id, steam64_id) VALUES\
				(:userID, :steamID)",
				{"userID": interaction.user.id, "steamID": int(self.view.steamID)},
			)
			await conn.commit()  # Commit changes

		# Disable the buttons in the view, and clean up the view since we won't need it anymore
		await self.view.terminate()

		# If we're in a guild, check if the user is in the associated steam group
		if interaction.guild is not None:
			# If we're in a guild, the user *must* be a member
			assert isinstance(interaction.user, discord.Member)
			try:
				groupMembership = await steam.in_guild_group(self.view.bot, interaction.guild.id, self.view.steamID)
				if not groupMembership:
					# User not in group
					applyUrl = await self.view.bot.serverConfig.group_apply_url.get(interaction.guild)
					msg = "Your account has been verified, but it doesn't look like you're a part of this group."
					if applyUrl is not None:
						msg += f" You're free to apply at {applyUrl}."
					await interaction.followup.send(msg, ephemeral=True)
					return
			except aiohttp.ClientResponseError as error:
				_log.warning(f"Received response code [{error.status}] from the Steam API when checking steam URL")
				await interaction.followup.send(steam_return_error_text(error.status))
				return
			except Exception:
				_log.exception("Error checking Steam group membership")
				await interaction.followup.send(
					"Error encountered checking Steam group membership. Please contact an administrator for assistance."
				)
				return

			# User is in the steam group, only proceed if they don't have the member role already
			memberRole = await self.view.bot.serverConfig.role_verify.get(interaction.guild)
			if (memberRole in interaction.user.roles) or memberRole is None:
				await interaction.followup.send(
					"Verification complete, your Steam ID has been successfully linked",
					ephemeral=True,
				)
			else:
				if await assign_roles(self.view.bot, interaction.guild, interaction.user):
					await interaction.user.send(f"Verification complete, welcome to {interaction.guild.name}.")

				else:
					await interaction.followup.send(
						f"{interaction.user.mention} your verification is complete, but I encountered an error "
						"when assigning your roles. Please ping an admin for your roles."
					)
				# Send a verification message to the check in channel
				checkInChannel = await self.view.bot.serverConfig.channel_check_in.get(interaction.guild)
				if isinstance(checkInChannel, discord.TextChannel):
					await checkInChannel.send(
						f"Member {interaction.user.mention} verified with steam account: http://steamcommunity.com/profiles/{self.view.steamID}"
					)

		else:
			# Not in a guild, don't check group membership
			# Let the user know that they're verified now
			await interaction.followup.send("Verification complete, your Steam ID has been successfully linked")


class CheckInButton(discord.ui.Button):
	"""Button to check in an already verified user"""

	view: CheckInView

	def __init__(
		self,
		*args,
		label: str = "Check In",
		style: discord.ButtonStyle = discord.ButtonStyle.primary,
		**kwargs,
	):
		super().__init__(*args, label=label, style=style, **kwargs)

	async def callback(self, interaction: discord.Interaction):
		# This should never be displayed outside of a guild context
		assert interaction.guild is not None
		assert isinstance(interaction.user, discord.Member)

		# Immediately defer the interaction response so that we can make web requests
		await interaction.response.defer()

		try:
			groupMembership = await steam.in_guild_group(self.view.bot, interaction.guild.id, self.view.steamID)
			if not groupMembership:
				# User not in group
				applyUrl = await self.view.bot.serverConfig.group_apply_url.get(interaction.guild)
				msg = "Your account has been verified, but it doesn't look like you're a part of this group."
				if applyUrl is not None:
					msg += f" You're free to apply at {applyUrl}."
				await interaction.followup.send(msg, ephemeral=True)
				return
		except aiohttp.ClientResponseError as error:
			_log.warning(f"Received response code [{error.status}] from the Steam API when checking steam URL")
			await interaction.followup.send(steam_return_error_text(error.status))
			return
		except Exception:
			_log.exception("Error checking Steam group membership")
			await interaction.followup.send(
				"Error encountered checking Steam group membership. Please contact an administrator for assistance."
			)
			return

		# User is in the steam group, only proceed if they don't have the member role already
		memberRole = await self.view.bot.serverConfig.role_verify.get(interaction.guild)
		if (memberRole in interaction.user.roles) or memberRole is None:
			await interaction.followup.send("Verification complete.", ephemeral=True)
		else:
			if await assign_roles(self.view.bot, interaction.guild, interaction.user):
				await interaction.user.send(f"Verification complete, welcome to {interaction.guild.name}.")

			else:
				await interaction.followup.send(
					f"{interaction.user.mention} your verification is complete, but I encountered an error "
					"when assigning your roles. Please ping an admin for your roles."
				)
			# Send a verification message to the check in channel
			checkInChannel = await self.view.bot.serverConfig.channel_check_in.get(interaction.guild)
			if isinstance(checkInChannel, discord.TextChannel):
				await checkInChannel.send(
					f"Member {interaction.user.mention} verified with steam account: http://steamcommunity.com/profiles/{self.view.steamID}"
				)


async def assign_roles(bot: blueonblue.BlueOnBlueBot, guild: discord.Guild, user: discord.Member) -> bool:
	"""|coro|

	Assigns Discord roles to a member upon being verified.

	Parameters
	----------
	bot : blueonblue.BlueOnBlueBot
		The bot object.
	guild : discord.Guild
		Guild to assign roles in.
	user : discord.Member
		Member to assign roles to.

	Returns
	-------
	bool
		True/False if the roles were assigned successfully.
	"""
	# Start by querying the database to see if the user has any roles stored.
	async with bot.pool.acquire() as conn:
		roleData = await conn.fetchall(
			"SELECT server_id, user_id, role_id FROM user_roles WHERE server_id = :server_id AND user_id = :user_id",
			{"server_id": guild.id, "user_id": user.id},
		)

	# This needs a check if the user is jailed.
	userRoles: list[discord.Role] = []
	# Get a list of our user roles
	for r in roleData:
		role = guild.get_role(r["role_id"])
		if role is not None:  # Verify that the role actually exists
			userRoles.append(role)

	# Check if we have roles stored
	if len(userRoles) > 0:
		# Roles stored in DB
		try:
			await user.add_roles(*userRoles, reason="User verified")
			return True
		except Exception:
			return False
	else:
		# No user roles stored
		memberRole = await bot.serverConfig.role_verify.get(guild)
		try:
			assert memberRole is not None
			await user.add_roles(memberRole, reason="User verified")
			return True
		except Exception:
			return False


def steam_return_error_text(status_code: int) -> str:
	"""Returns error text from an HTTP error code from Steam API requests.

	Provided errors are also logged to the bot log.

	Parameters
	----------
	status_code : int
		HTTP error status code.

	Returns
	-------
	str
		Error text to be sent to the user.
	"""
	if status_code == 400:  # Bad request
		return "That doesn't seem to be a valid steam profile. Please provide a link similar to this: <https://steamcommunity.com/profiles/76561198329777700>"
	elif status_code == 403:  # Unauthorized
		return (
			"I ran into an issue getting data from Steam. Please verify that your Steam profile visibility is set to 'Public'. "
			"If it is, please ping an admin for a role. Error `403`"
		)
	elif status_code == 429:  # Rate limited
		_log.warning("Received code 429 from Steam.")
		return "I appear to be rate-limited by Steam. Please ping an admin for a role. Error `429`"
	elif status_code == 500:  # Server error
		_log.warning("Received code 500 from Steam.")
		return "Steam appears to be having some issues. Please ping an admin for a role. Error `500`"
	elif status_code == 503:
		_log.warning("Received code 503 from Steam.")
		return "Steam appears to be having some issues. Please ping an admin for a role. Error `503`"
	else:
		_log.warning(f"Received code {status_code} from Steam.")
		return f"Something has gone wrong. Please ping an admin for a role. Error `{status_code}`"


@app_commands.guild_only()
class Verify(commands.GroupCog, group_name="verify"):
	"""Verify that users are part of a steam group."""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	@app_commands.command(name="steam")
	async def verify_steam(self, interaction: discord.Interaction, steam_url: str):
		"""Establishes a link between a Discord account and a Steam account

		Parameters
		----------
		interaction : discord.Interaction
			Discord interaction
		steam_url : str
			Your Steam profile URL
		"""
		# Immediately defer the interaction, since we need to make web requests.
		await interaction.response.defer(ephemeral=True)

		# Get the user's SteamID64
		try:
			steamID = await steam.getID64(self.bot, steam_url)
		except aiohttp.ClientResponseError as error:
			if error.status not in [400, 403]:
				_log.warning(f"Received response code [{error.status}] from the Steam API when checking steam URL")
			await interaction.followup.send(steam_return_error_text(error.status))
			return
		except steam.InvalidSteamURL:
			await interaction.followup.send("Invalid Steam URL format. Please use the *full* URL to your Steam profile.")
			return
		except Exception:
			_log.exception("Error getting Steam64ID")
			await interaction.followup.send(
				"Error encountered checking steam ID. Please contact an administrator for assistance."
			)
			return

		# If the command is used in a guild, check that the user is in the provided steam group
		if interaction.guild is not None:
			try:
				groupMembership = await steam.in_guild_group(self.bot, interaction.guild.id, steamID)
				if not groupMembership:
					# User not in group
					applyUrl = await self.bot.serverConfig.group_apply_url.get(interaction.guild)
					msg = "Sorry, it doesn't look like you're a part of this group."
					if applyUrl is not None:
						msg += f" You're free to apply at {applyUrl}."
					await interaction.followup.send(msg)
					return
			except aiohttp.ClientResponseError as error:
				_log.warning(f"Received response code [{error.status}] from the Steam API when checking steam URL")
				await interaction.followup.send(steam_return_error_text(error.status))
				return
			except Exception:
				_log.exception("Error checking Steam group membership")
				await interaction.followup.send(
					"Error encountered checking Steam group membership. Please contact an administrator for assistance."
				)
				return

		view = VerifySteamView(self.bot, interaction.user, steamID)

		view.message = await interaction.followup.send(
			"To complete your verification, ensure that your steam profile visibility is set to **public**, "
			'then put the following token into the "real name" section of your steam profile.\n'
			f"```{interaction.user.id}```"
			"Once you have done so, click the button below to verify your account.",
			view=view,
			wait=True,
		)

	@app_commands.command()
	async def status(self, interaction: discord.Interaction):
		"""Displays accounts linked through the bot

		Parameters
		----------
		interaction : discord.Interaction
			Discord interaction
		"""
		# Immediately defer the response, since we need to make web requests
		await interaction.response.defer(ephemeral=True)

		# Initialize some variables
		steamInfo: tuple[str, int] | None = None

		# Check to see if we can get the user's Steam64ID from the database
		async with self.bot.pool.acquire() as conn:
			# Get the user's data from the DB
			userData = await conn.fetchone(
				"SELECT steam64_id FROM verify WHERE discord_id = :id AND steam64_id NOT NULL",
				{"id": interaction.user.id},
			)  # This will only return users that are verified
			if userData is not None:
				steamID: int = userData["steam64_id"]
				# Get the user's steam display name
				try:
					steamInfo = (
						await steam.get_display_name(self.bot, str(steamID)),
						steamID,
					)
				except Exception:
					_log.exception("Error retrieving profile name from steam")
					pass

		# Start generating our embed
		embed = discord.Embed(title="Accounts", color=VERIFY_EMBED_COLOUR)
		embed.set_author(
			name=interaction.user.display_name,
			icon_url=interaction.user.display_avatar.url,
		)
		if steamInfo is not None:
			embed.add_field(
				name="Steam",
				# Discord strips duplicate whitespace characters here, no way to align things nicely
				value=f"{steamInfo[0]} | <http://steamcommunity.com/profiles/{steamInfo[1]}>",
				inline=False,
			)
		else:
			embed.add_field(name="Steam", value="Not found", inline=False)

		await interaction.followup.send(embed=embed)

	# @commands.Cog.listener()
	# async def on_member_join(self, member: discord.Member):
	# 	guildSteamGroupID = await self.bot.serverConfig.steam_group_id.get(member.guild)
	# 	channel = await self.bot.serverConfig.channel_check_in.get(member.guild)
	# 	assert isinstance(channel, discord.TextChannel)
	# 	if (
	# 		(guildSteamGroupID is not None)
	# 		and (guildSteamGroupID > 0)
	# 		and (channel is not None)
	# 	):
	# 		# Only continue if we have a valid steam group ID and check in channel
	# 		# Start our DB block
	# 		async with self.bot.db.connect() as db:
	# 			async with db.connection.cursor() as cursor:
	# 				# Get the user data from the DB
	# 				await cursor.execute(
	# 					"SELECT steam64_id FROM verify WHERE discord_id = :id AND steam64_id NOT NULL",
	# 					{"id": member.id},
	# 				)
	# 				userData = (
	# 					await cursor.fetchone()
	# 				)  # This will only return users that are verified
	# 				# Check if we have any data in the DB
	# 				if userData is not None:
	# 					# User is already verified
	# 					view = CheckInView(
	# 						self.bot, member, str(userData["steam64_id"])
	# 					)
	# 					view.message = await channel.send(
	# 						f"Welcome to {member.guild.name} {member.mention}. It looks like you have been here before. "
	# 						f"Use the button below to gain access to the server, or `/verify steam` if you need to use a "
	# 						"different steam account.",
	# 						view=view,
	# 					)

	# 				else:
	# 					# User not already verified
	# 					await channel.send(
	# 						f"Welcome to {member.guild.name} {member.mention}. To gain access to this server, "
	# 						f"please type `/verify steam <link-to-your-steam-profile>`. If you are not in {member.guild.name} "
	# 						"at the moment, please go through the regular application process to join."
	# 					)


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Verify(bot))
