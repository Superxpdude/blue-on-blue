import discord
from discord import app_commands
from discord.ext import commands, tasks

import asyncio
import datetime
import random

import blueonblue

import logging
_log = logging.getLogger(__name__)

RAFFLE_EMBED_COLOUR = 0x00ff00


class RaffleObject():
	def __init__(self, name: str, *args, winners: int = 1, **kwargs):
		self.name = name
		self.participants: list[discord.User|discord.Member] = []
		self.winners = winners


	def addUser(self, user: discord.User|discord.Member):
		"""Adds a participant to the raffle

		Does nothing if the participant is already in the list

		Parameters
		----------
		participant : discord.User | discord.Member
			The participant to add
		"""
		if user not in self.participants:
			self.participants.append(user)


	def removeUser(self, user: discord.User|discord.Member):
		"""Removes a participant from the raffle

		Does nothing if the user is not in the list

		Parameters
		----------
		user : discord.User | discord.Member
			The participant to remove
		"""
		if user in self.participants:
			self.participants.remove(user)


	def userInRaffle(self, user: discord.User|discord.Member) -> bool:
		"""Check if a user is in the raffle or not

		Parameters
		----------
		user : discord.User | discord.Member
			The user to check

		Returns
		-------
		bool
			If the user is in the raffle
		"""
		if user in self.participants:
			return True
		else:
			return False


	def participantCount(self) -> int:
		"""Returns the current number of participants in the raffle

		Returns
		-------
		int
			Current number of participants
		"""
		return len(self.participants)


	def selectWinners(self, winnerCount: int | None = None) -> tuple[discord.User|discord.Member]:
		"""Selects a number of winners for the raffle

		Parameters
		----------
		winnerCount : int, optional
			How many winners to select, by default 1

		Returns
		-------
		tuple[discord.User|discord.Member]
			The list of raffle winners
		"""
		if winnerCount is None:
			winnerCount = self.winners
		return tuple(random.choices(self.participants, k = winnerCount))


	def endRaffleEmbed(self) -> discord.Embed:
		"""Creates an embed with the raffle details
		Automatically selects a number of winners based on the the stored winners value

		Returns
		-------
		discord.Embed
			Generated embed
		"""
		winners = self.selectWinners()
		embed = discord.Embed(
			title = f"🎉 Raffle: {self.name}",
			color = RAFFLE_EMBED_COLOUR
		)
		if len(winners) < 1:
			embed.description = "No entrants for this raffle"
		else:
			embed.add_field(name = "Winners", value = ", ".join(map(lambda x: x.mention ,winners)), inline = False)
			embed.add_field(name = "Participants", value = ", ".join(map(lambda x: x.mention ,self.participants)), inline = False)

		return embed


class RaffleJoinButton(discord.ui.Button):
	def __init__(self,
	    raffle: RaffleObject,
	    *args,
		label: str | None = None,
		style: discord.ButtonStyle = discord.ButtonStyle.primary,
		**kwargs
	):
		self.raffle = raffle
		if label is None:
			label = self.raffle.name
		super().__init__(*args, label = label, style = style, **kwargs)


	async def callback(self, interaction: discord.Interaction):
		assert isinstance(self.view, RaffleView)

		# Check if the user is already in the raffle
		if self.raffle.userInRaffle(interaction.user):
			# User already in, send them the leave prompt
			await interaction.response.send_message(
				f"You are already in the raffle for {self.raffle.name}",
				ephemeral=True,
				delete_after=30
			)
		else:
			# User not in, add them to the raffle
			self.raffle.addUser(interaction.user)
			await interaction.response.send_message(
				f"You have joined the raffle for {self.raffle.name}",
				ephemeral=True,
				delete_after=30
			)
			await self.view.update_embed()


class RaffleView(discord.ui.View):
	message: discord.InteractionMessage
	def __init__(self,
	    bot: blueonblue.BlueOnBlueBot,
		*args,
		timeout: float = 600.0,
		raffles: tuple[str | tuple[str,int],...],
		endTime: datetime.datetime,
		**kwargs,
	):
		self.bot = bot
		super().__init__(*args, timeout=timeout, **kwargs)
		#self.add_item(MissionAuditButton())
		self.raffles: list[RaffleObject] = []
		# Set up our raffles
		for r in raffles:
			if isinstance(r,tuple):
				raffle = RaffleObject(r[0])
				raffle.winners = r[1]
			else:
				raffle = RaffleObject(r)
			self.raffles.append(raffle)
			self.add_item(RaffleJoinButton(raffle))
		# Set the "last updated time"
		self.lastUpdateTime: datetime.datetime | None = None
		self.updating: bool = False
		self.endTime = endTime


	def build_embed(self) -> discord.Embed:
		"""Builds the embed for the raffle message

		Returns
		-------
		discord.Embed
			The generated embed
		"""
		embed = discord.Embed(
			title = f"🎉 Raffle (ends {discord.utils.format_dt(self.endTime,'R')})",
			description = "Click the corresponding button below to enter the raffle!",
			color = RAFFLE_EMBED_COLOUR
		)
		embed.set_footer(text = "Numbers above represent number of entrants in the raffle")
		for r in self.raffles:
			if r.winners > 1:
				embed.add_field(name = f"{r.name} ({r.winners} winners)", value = r.participantCount(), inline = True)
			else:
				embed.add_field(name = f"{r.name}", value = r.participantCount(), inline = True)

		return embed


	async def update_embed(self) -> None:
		"""Updates the embed with new raffle counts"""
		# Only continue if not in the process of updating
		if (not self.updating):
			# If we're getting updates too frequently, we should wait to update the view to avoid rate limits
			if ((self.lastUpdateTime is not None) and ((discord.utils.utcnow() - self.lastUpdateTime).total_seconds() < 10)):
				# Mark that we're updating the view
				self.updating = True
				# Wait for five seconds
				await asyncio.sleep(5)
				# Disable the updating flag
				self.updating = False

			# Update the embed
			await self.message.edit(embed = self.build_embed())


	async def stop(self) -> None:
		for child in self.children:
			assert isinstance(child, (discord.ui.Button, discord.ui.Select))
			child.disabled = True
		if self.message is not None:
			await self.message.edit(view = self)
		# Stop the view
		super().stop()


class Raffle(commands.Cog, name = "Raffle"):
	"""Raffle commands"""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot


	@app_commands.command(name = "raffle")
	@app_commands.guild_only() # No point in running raffles in DMs
	async def raffle(self,
		  interaction: discord.Interaction,
		  raffle_name: str,
		  duration: app_commands.Range[int, 15, 600],
		  winners: app_commands.Range[int, 1, None] = 1,
	):
		"""Creates a raffle

		Parameters
		----------
		interaction : discord.Interaction
			The discord interaction
		raffle_name : str
			Name of the raffle to start
		duration: str
			Duration of the raffle in seconds
		winners : app_commands.Range[int, 0, None] | None, optional
			How many winners should be selected
		"""
		# Guild-only command
		assert interaction.guild is not None

		# Determine the end time
		dt = discord.utils.utcnow() + datetime.timedelta(seconds = duration)

		# Create the view
		view = RaffleView(self.bot, raffles = ((raffle_name,winners),), endTime = dt)

		# Generate an embed
		embed = view.build_embed()

		# Send the message
		await interaction.response.send_message(embed = embed, view=view)
		view.message = await interaction.original_response()

		# Wait for our timeout
		# This will wait for shorter and shorter times to ensure that the raffle ends
		# at the correct time with long durations
		while discord.utils.utcnow() < dt:
			sleep = max((dt - discord.utils.utcnow()).total_seconds() / 2,1)
			await asyncio.sleep(sleep)

		# Stop the view
		await view.stop()

		# Choose winners.
		for r in view.raffles:
			await interaction.followup.send(embed = r.endRaffleEmbed())


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Raffle(bot))
