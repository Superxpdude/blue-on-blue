import discord
from discord import app_commands
from discord.ext import commands, tasks

import asyncio
import datetime
import random

import blueonblue

import logging
_log = logging.getLogger(__name__)


class RaffleObject():
	def __init__(self, name: str, *args, **kwargs):
		self.name = name
		self.participants: list[discord.User|discord.Member] = []


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


	def selectWinners(self, winnerCount: int = 1) -> tuple[discord.User|discord.Member]:
		"""_summary_

		Parameters
		----------
		winnerCount : int, optional
			How many winners to select, by default 1

		Returns
		-------
		tuple[discord.User|discord.Member]
			The list of raffle winners
		"""
		return tuple(random.choices(self.participants, k = winnerCount))


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


class RaffleView(discord.ui.View):
	message: discord.InteractionMessage
	def __init__(self,
	    bot: blueonblue.BlueOnBlueBot,
		*args,
		timeout: float = 600.0,
		raffles: tuple[str],
		**kwargs,
	):
		self.bot = bot
		super().__init__(*args, timeout=timeout, **kwargs)
		#self.add_item(MissionAuditButton())
		self.raffles: list[RaffleObject] = []
		# Set up our raffles
		for r in raffles:
			raffle = RaffleObject(r)
			self.raffles.append(raffle)
			self.add_item(RaffleJoinButton(raffle))

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
		"""_summary_

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

		# Create the message
		message = f"Creating raffle: {raffle_name}\nEnds {discord.utils.format_dt(dt,'R')}"

		# Create the view
		view = RaffleView(self.bot, raffles = (raffle_name,))

		# Send the message
		await interaction.response.send_message(message, view=view)

		# Wait for our timeout
		await asyncio.sleep(duration)

		# Choose winners
		for r in view.raffles:
			if len(r.participants) > 0:
				winner = r.selectWinners(winners)[0]
				await interaction.followup.send(f"Winner of '{r.name}': {winner.mention}")
			else:
				await interaction.followup.send(f"No participants for raffle: {r.name}")
		await view.stop()


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Raffle(bot))
