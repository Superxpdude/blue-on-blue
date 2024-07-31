import logging

import blueonblue
import discord
from discord import app_commands
from discord.ext import commands

_log = logging.getLogger(__name__)


@app_commands.guild_only()
@app_commands.default_permissions(administrator=True)
class Config(commands.GroupCog, group_name="config"):
	"""Server configuration commands"""

	def __init__(self, bot, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.bot: blueonblue.BlueOnBlueBot = bot

	async def config_autocomplete(self, interaction: discord.Interaction, current: str):
		"""Function to handle autocompletion of config elements present in the serverconfig"""
		if interaction.guild is None:
			# If the guild doesn't existreturn nothing
			return []
		else:
			# Command called in guild
			return [
				app_commands.Choice(name=option, value=option)
				for option in self.bot.serverConfig.options.keys()
				if current.lower() in option.lower()
			][:25]

	async def config_autocomplete_basic(
		self, interaction: discord.Interaction, current: str
	):
		"""Autocomplete function that only returns role config options"""
		if interaction.guild is None:
			# If the guild doesn't exist return nothing
			return []
		else:
			# Command called in guild
			return [
				app_commands.Choice(name=option, value=option)
				for option in self.bot.serverConfig.options.keys()
				if (current.lower() in option.lower())
				and not (
					isinstance(
						self.bot.serverConfig.options[option],
						(
							blueonblue.config.ServerConfigRole,
							blueonblue.config.ServerConfigChannel,
						),
					)
				)
			][:25]

	async def config_autocomplete_role(
		self, interaction: discord.Interaction, current: str
	):
		"""Autocomplete function that only returns role config options"""
		if interaction.guild is None:
			# If the guild doesn't exist return nothing
			return []
		else:
			# Command called in guild
			return [
				app_commands.Choice(name=option, value=option)
				for option in self.bot.serverConfig.options.keys()
				if (current.lower() in option.lower())
				and (
					isinstance(
						self.bot.serverConfig.options[option],
						blueonblue.config.ServerConfigRole,
					)
				)
			][:25]

	async def config_autocomplete_channel(
		self, interaction: discord.Interaction, current: str
	):
		"""Autocomplete function that only returns channel config options"""
		if interaction.guild is None:
			# If the guild doesn't exist return nothing
			return []
		else:
			# Command called in guild
			return [
				app_commands.Choice(name=option, value=option)
				for option in self.bot.serverConfig.options.keys()
				if (current.lower() in option.lower())
				and (
					isinstance(
						self.bot.serverConfig.options[option],
						blueonblue.config.ServerConfigChannel,
					)
				)
			][:25]

	@app_commands.command(name="list")
	@app_commands.guild_only()
	async def list(self, interaction: discord.Interaction):
		"""Lists all server config values for the server

		Parameters
		----------
		interaction : discord.Interaction
			The Discord interaction
		"""
		assert interaction.guild is not None

		options = self.bot.serverConfig.options
		cfgOptions: list[str] = []

		for cfg in options.keys():
			option = self.bot.serverConfig.options[cfg]
			if isinstance(
				option,
				(
					blueonblue.config.ServerConfigString,
					blueonblue.config.ServerConfigInteger,
					blueonblue.config.ServerConfigFloat,
				),
			):
				data = await option.get(interaction.guild)
				value = f"`{data}`" if data is not None else None
			elif isinstance(
				option,
				(
					blueonblue.config.ServerConfigRole,
					blueonblue.config.ServerConfigChannel,
				),
			):
				data = await option.get(interaction.guild)
				value = data.mention if data is not None else None
			else:
				value = None
			if value is not None and option.protected:
				value = "`*****`"
			if value is not None and (not value.startswith("<@")) and len(value) > 28:
				value = f"{value:.25}...`"
			cfgOptions.append(
				f"`{option.name:30.30}`: {value if value is not None else '`None`'}"
			)

		optionText = "\n".join(cfgOptions)

		# Create embed
		embed = discord.Embed(
			title=f"Server configuration for {interaction.guild.name}",
			description=f"{optionText}",
		)

		await interaction.response.send_message(embed=embed)

	@app_commands.command(name="search")
	@app_commands.guild_only()
	@app_commands.autocomplete(option=config_autocomplete)
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
		for k in self.bot.serverConfig.options.keys():
			o = self.bot.serverConfig.options[k]
			if option in o.name:
				matches.append(o)  # type: ignore

		if len(matches) > 0:
			embed = discord.Embed(
				title=f"Server configuration for {interaction.guild.name}",
			)
			for o in matches:
				data = await o.get(interaction.guild)
				value = "`*****`" if data is not None and o.protected else data
				embed.add_field(name=o.name, value=value, inline=False)
			await interaction.response.send_message(embed=embed)
		else:
			await interaction.response.send_message(
				f"Could not find any config values that matches the search term: {option}",
				ephemeral=True,
			)

	@app_commands.command(name="set")
	@app_commands.guild_only()
	@app_commands.autocomplete(option=config_autocomplete_basic)
	async def set(self, interaction: discord.Interaction, option: str, value: str):
		"""Sets a server config value for all values other than roles or channels

		Parameters
		----------
		interaction : discord.Interaction
			The Discord interaction
		option : str
			The name of the option to set.
		value : str
			The value to set.
		"""
		assert interaction.guild is not None

		# Check if the option exists
		if option not in self.bot.serverConfig.options.keys():
			await interaction.response.send_message(
				f"`{option}` is not a valid server config option!", ephemeral=True
			)
			return

		# Get the type of the option
		serverOpt = self.bot.serverConfig.options[option]

		# Set some default values
		responseMessage = "Default config response"
		ephemeral = False

		if isinstance(serverOpt, blueonblue.config.ServerConfigString):
			await serverOpt.set(interaction.guild, value)
			responseMessage = f"Setting option `{option}` to value `{value}`."
			_log.info(
				f"Setting server config [{option}|{value}] for guild: [{interaction.guild.name}|{interaction.guild.id}]"
			)

		elif isinstance(serverOpt, blueonblue.config.ServerConfigInteger):
			if value.isnumeric():
				await serverOpt.set(interaction.guild, int(value))
				responseMessage = f"Setting option `{option}` to value `{value}`."
				_log.info(
					f"Setting server config [{option}|{value}] for guild: [{interaction.guild.name}|{interaction.guild.id}]"
				)
			else:
				responseMessage = f"Could not convert the value `{value}` to an integer for option `{option}`."
				ephemeral = True

		elif isinstance(serverOpt, blueonblue.config.ServerConfigFloat):
			try:
				await serverOpt.set(interaction.guild, float(value))
				responseMessage = f"Setting option `{option}` to value `{value}`."
				_log.info(
					f"Setting server config [{option}|{value}] for guild: [{interaction.guild.name}|{interaction.guild.id}]"
				)
			except ValueError:
				responseMessage = f"Could not convert the value `{value}` to a float for option `{option}`."
				ephemeral = True

		elif isinstance(serverOpt, blueonblue.config.ServerConfigRole):
			responseMessage = "Role server configs cannot be set using this command! Please use `/config setrole` instead!"
			ephemeral = True

		elif isinstance(serverOpt, blueonblue.config.ServerConfigChannel):
			responseMessage = "Channel server configs cannot be set using this command! Please use `/config setchannel` instead!"
			ephemeral = True

		else:
			responseMessage = f"Could not determine the option type for option `{option}`. Unable to set value."
			_log.error(f"Unable to identify type for serverconfig option: {option}")

		embed = discord.Embed(title="Server Config", description=responseMessage)

		await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

	@app_commands.command(name="setrole")
	@app_commands.guild_only()
	@app_commands.autocomplete(option=config_autocomplete_role)
	async def set_role(
		self, interaction: discord.Interaction, option: str, role: discord.Role
	):
		"""Sets a server config role value

		Parameters
		----------
		interaction : discord.Interaction
			The Discord interaction
		option : str
			The name of the option to set.
		role : discord.Role
			The role to set.
		"""
		assert interaction.guild is not None

		# Check if the option exists
		if option not in self.bot.serverConfig.options.keys():
			await interaction.response.send_message(
				f"`{option} is not a valid server config option!", ephemeral=True
			)
			return

		# Get the type of the option
		serverOpt = self.bot.serverConfig.options[option]

		# Set some default values
		responseMessage = "Default config response"
		ephemeral = False

		if isinstance(serverOpt, blueonblue.config.ServerConfigRole):
			await serverOpt.set(interaction.guild, role)
			responseMessage = f"Setting option `{option}` to value {role.mention}."
			_log.info(
				f"Setting server config [{option}|{role.id}] for guild: [{interaction.guild.name}|{interaction.guild.id}]"
			)

		else:
			responseMessage = (
				"This command can only be used to set values for role configs!"
			)
			ephemeral = True

		embed = discord.Embed(title="Server Config", description=responseMessage)

		await interaction.response.send_message(embed=embed, ephemeral=ephemeral)

	@app_commands.command(name="setchannel")
	@app_commands.guild_only()
	@app_commands.autocomplete(option=config_autocomplete_channel)
	async def set_channel(
		self,
		interaction: discord.Interaction,
		option: str,
		channel: discord.TextChannel | discord.VoiceChannel,
	):
		"""Sets a server config channel value

		Parameters
		----------
		interaction : discord.Interaction
			The Discord interaction
		option : str
			The name of the option to set.
		channel : discord.abc.GuildChannel
			The channel to set.
		"""
		assert interaction.guild is not None

		# Check if the option exists
		if option not in self.bot.serverConfig.options.keys():
			await interaction.response.send_message(
				f"`{option} is not a valid server config option!", ephemeral=True
			)
			return

		# Get the type of the option
		serverOpt = self.bot.serverConfig.options[option]

		# Set some default values
		responseMessage = "Default config response"
		ephemeral = False

		if isinstance(serverOpt, blueonblue.config.ServerConfigChannel):
			await serverOpt.set(interaction.guild, channel)
			responseMessage = f"Setting option `{option}` to value {channel.mention}."
			_log.info(
				f"Setting server config [{option}|{channel.id}] for guild: [{interaction.guild.name}|{interaction.guild.id}]"
			)

		else:
			responseMessage = (
				"This command can only be used to set values for channel configs!"
			)
			ephemeral = True

		embed = discord.Embed(title="Server Config", description=responseMessage)

		await interaction.response.send_message(embed=embed, ephemeral=ephemeral)


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Config(bot))
