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


	async def config_autocomplete(self, interaction: discord.Interaction, current: str):
		"""Function to handle autocompletion of config elements present in the serverconfig"""
		if (interaction.guild is None):
			# If the guild doesn't existreturn nothing
			return []
		else:
			# Command called in guild
			return[app_commands.Choice(name=option, value=option) for option in self.bot.serverConfNew.options.keys() if current.lower() in option.lower()][:25]


	async def config_autocomplete_role(self, interaction: discord.Interaction, current: str):
		if (interaction.guild is None):
			# If the guild doesn't exist return nothing
			return []
		else:
			# Command called in guild
			return[app_commands.Choice(name=option, value=option) for option in self.bot.serverConfNew.options.keys() if (current.lower() in option.lower()) and (isinstance(self.bot.serverConfNew.options[option],blueonblue.config.ServerConfigRole))][:25]



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
	@app_commands.autocomplete(option = config_autocomplete)
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
				value = await o.get(interaction.guild) if not o.protected else "`*****`"
				embed.add_field(name = o.name, value = value, inline = False)
			await interaction.response.send_message(embed = embed)
		else:
			await interaction.response.send_message(f"Could not find any config values that matches the search term: {option}", ephemeral=True)


	@app_commands.command(name = "set")
	@app_commands.guild_only()
	@app_commands.autocomplete(option = config_autocomplete)
	async def set(self, interaction: discord.Interaction, option: str, value: str):
		"""Sets a server config value

		Parameters
		----------
		interaction : discord.Interaction
			The Discord interaction
		option : str
			The name of the option to set
		value : str
			The value to set. Roles and channels must be passed in ID form.
		"""
		assert interaction.guild is not None

		# Check if the option exists
		if option not in self.bot.serverConfNew.options.keys():
			await interaction.response.send_message(f"`{option} is not a valid server config option!", ephemeral=True)
			return

		# Get the type of the option
		serverOpt = self.bot.serverConfNew.options[option]

		# Set some default values
		responseMessage = "Default config response"
		ephemeral = False

		if isinstance(serverOpt, blueonblue.config.ServerConfigString):
			await serverOpt.set(interaction.guild, value)
			responseMessage = f"Setting option `{option}` to value `{value}`."
			_log.info(f"Setting server config [{option}|{value}] for guild: [{interaction.guild.name}|{interaction.guild.id}]")

		elif isinstance(serverOpt, blueonblue.config.ServerConfigInteger):
			if value.isnumeric():
				await serverOpt.set(interaction.guild, int(value))
				responseMessage = f"Setting option `{option}` to value `{value}`."
				_log.info(f"Setting server config [{option}|{value}] for guild: [{interaction.guild.name}|{interaction.guild.id}]")
			else:
				responseMessage = f"Could not convert the value `{value}` to an integer for option `{option}`."
				ephemeral = True

		elif isinstance(serverOpt, blueonblue.config.ServerConfigFloat):
			try:
				await serverOpt.set(interaction.guild, float(value))
				responseMessage = f"Setting option `{option}` to value `{value}`."
				_log.info(f"Setting server config [{option}|{value}] for guild: [{interaction.guild.name}|{interaction.guild.id}]")
			except ValueError:
				responseMessage = f"Could not convert the value `{value}` to a float for option `{option}`."
				ephemeral = True

		elif isinstance(serverOpt, blueonblue.config.ServerConfigRole):
			if value.isnumeric():
				role = interaction.guild.get_role(int(value))
				if role is not None:
					await serverOpt.set(interaction.guild, role)
					responseMessage = f"Setting option `{option}` to value {role.mention}."
					_log.info(f"Setting server config [{option}|{role.id}] for guild: [{interaction.guild.name}|{interaction.guild.id}]")
				else:
					responseMessage = f"Could not locate a role with ID `{value}` for option `{option}`."
					ephemeral = True
			else:
				responseMessage = f"Could not locate a role with ID `{value}` for option `{option}`."
				ephemeral = True

		elif isinstance(serverOpt, blueonblue.config.ServerConfigChannel):
			if value.isnumeric():
				channel = interaction.guild.get_channel(int(value))
				if channel is not None:
					await serverOpt.set(interaction.guild, channel)
					responseMessage = f"Setting option `{option}` to value {channel.mention}."
					_log.info(f"Setting server config [{option}|{channel.id}] for guild: [{interaction.guild.name}|{interaction.guild.id}]")
				else:
					responseMessage = f"Could not locate a channel with ID `{value}` for option `{option}`."
					ephemeral = True
			else:
				responseMessage = f"Could not locate a channel with ID `{value}` for option `{option}`."
				ephemeral = True


		else:
			responseMessage = f"Could not determine the option type for option `{option}`. Unable to set value."
			_log.error(f"Unable to identify type for serverconfig option: {option}")

		embed = discord.Embed(
			title = "Server Config",
			description = responseMessage
		)

		await interaction.response.send_message(embed = embed, ephemeral = ephemeral)


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Config(bot))
