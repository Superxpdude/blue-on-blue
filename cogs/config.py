import discord
from discord import app_commands
from discord.ext import commands

import inspect

import blueonblue

import logging
_log = logging.getLogger(__name__)

@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
class Config(commands.GroupCog, group_name = "config"):
	"""Server configuration commands"""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot


	async def config_autocmplete(self, interaction: discord.Interaction, current: str):
		"""Function to handle autocompletion of config elements present in the serverconfig"""
		if (interaction.guild is None):
			# If the guild doesn't exist, or the cache doesn't exist return nothing
			return []
		else:
			# Command called in guild, and cache exists for that guild
			return[app_commands.Choice(name=mission, value=mission) for mission in self.bot.serverConfNew.options.keys() if current.lower() in mission.lower()][:25]


	@app_commands.command(name = "list")
	@app_commands.guild_only()
	async def list(self, interaction: discord.Interaction):
		"""Lists all server config values for the server

		Parameters
		----------
		interaction : discord.Interaction
			The Discord interaction
		"""
		assert interaction.guild is not None

		options = self.bot.serverConfNew.options
		cfgOptions: list[str] = []

		for cfg in options.keys():
			option = self.bot.serverConfNew.options[cfg]
			if isinstance(option, blueonblue.config.ServerConfigString):
				value = f"`{await option.get(interaction.guild)}`"
			elif isinstance(option, blueonblue.config.ServerConfigInteger):
				value = f"`{await option.get(interaction.guild)}`"
			elif isinstance(option, (blueonblue.config.ServerConfigRole, blueonblue.config.ServerConfigChannel)):
				data = await option.get(interaction.guild)
				value = data.mention if data is not None else None
			else:
				value = None
			if value is not None and option.protected:
				value = "`*****`"
			if value is not None and (not value.startswith("<@")) and len(value) > 28:
				value = f"{value:.25}...`"
			cfgOptions.append(f"`{option.name:30.30}`: {value if value is not None else '`None`'}")

		optionText = "\n".join(cfgOptions)

		# Create embed
		embed = discord.Embed(
			title = f"Server configuration for {interaction.guild.name}",
			description = f"{optionText}",
		)

		await interaction.response.send_message(embed=embed)


	@app_commands.command(name = "search")
	@app_commands.guild_only()
	@app_commands.autocomplete(option = config_autocmplete)
	async def search(self, interaction: discord.Interaction, option: str):
		"""Displays config values for server config options

		Parameters
		----------
		interaction : discord.Interaction
			Discord Interaction
		option : str
			Config option to search for
		"""
		assert interaction.guild is not None
		# String searching is case-sensiive
		option = option.casefold()

		# Fix this type-hint later
		matches: list[blueonblue.config.ServerConfigString] = []

		# Find our matches
		for k in self.bot.serverConfNew.options.keys():
			o = self.bot.serverConfNew.options[k]
			if option in o.name:
				matches.append(o) #type: ignore

		if len(matches) > 0:
			embed = discord.Embed(
				title = f"Server configuration for {interaction.guild.name}",
			)
			for o in matches:
				embed.add_field(name = o.name, value = await o.get(interaction.guild), inline = False)
			await interaction.response.send_message(embed = embed)
		else:
			await interaction.response.send_message(f"Could not find any config values that matches the search term: {option}", ephemeral=True)


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Config(bot))
