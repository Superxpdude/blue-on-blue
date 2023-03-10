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


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Config(bot))
