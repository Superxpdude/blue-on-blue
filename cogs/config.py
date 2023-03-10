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

		cfgOptions: list[str] = []

		# Get a list of config options
		for m in inspect.getmembers(self.bot.serverConfNew):
			if isinstance(m[1], blueonblue.config.ServerConfigOption):
				# Member is server config option. Create our string
				name = m[0]
				if isinstance(m[1], blueonblue.config.ServerConfigString):
					value = await m[1].get(interaction.guild)
				elif isinstance(m[1], blueonblue.config.ServerConfigInteger):
					value = str(await m[1].get(interaction.guild))
				elif isinstance(m[1], (blueonblue.config.ServerConfigRole, blueonblue.config.ServerConfigChannel)):
					data = await m[1].get(interaction.guild)
					value = data.name if data is not None else None
				else:
					value = None
				if value is not None and m[1].protected:
					value = "*****"
				cfgOptions.append(f"{name:30.30}: {value}")


		optionText = "\n".join(cfgOptions)

		# Create embed
		embed = discord.Embed(
			title = f"Server configuration for {interaction.guild.name}",
			description = f"```{optionText}```",
		)

		await interaction.response.send_message(embed=embed)


async def setup(bot: blueonblue.BlueOnBlueBot):
	await bot.add_cog(Config(bot))
