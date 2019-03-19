import discord
from discord.ext import commands
from datetime import datetime
from datetime import timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials

g_sheets_scope = ['https://spreadsheets.google.com/feeds']
g_sheets_creds = ServiceAccountCredentials.from_json_keyfile_name('google_api.json', g_sheets_scope)
g_sheets_client = gspread.authorize(g_sheets_creds)
g_sheets_doc = g_sheets_client.open_by_url("https://docs.google.com/spreadsheets/d/1sZv6aia_jq3DXfIrTz5TB-9mxIFW3RrV-AWX_drlZLM")


class Missions(commands.Cog, name="Missions"):
	def __init__(self, bot):
		self.bot = bot

	@commands.command(
		name="ops",
		brief="Grabs a list of upcoming missions",
		aliases=['missions']
	)
	async def missions(self, ctx):
		# Google docs info
		scope = ['https://spreadsheets.google.com/feeds']
		creds = ServiceAccountCredentials.from_json_keyfile_name('google_api.json', scope)
		client = gspread.authorize(creds)
		doc = client.open_by_url("https://docs.google.com/spreadsheets/d/1sZv6aia_jq3DXfIrTz5TB-9mxIFW3RrV-AWX_drlZLM")
		mission_sheet = doc.worksheet("Current Month")
		# Embed settings
		
		for i in mission_sheet.get_all_values():
			missionDate = datetime.date(datetime.strptime(i[0],"%m/%d/%y"))
			if (
				i[0] != "" and i[0] != "DATES" and i[1] != "" and 
				missionDate > 
				datetime.date(datetime.now() + timedelta(days=-1))
			):
				missionArr = i[1].split(" - ")
				missionURL = "https://wiki.tmtm.gg/wiki/" + missionArr[0].replace(" ","_")
				embed = discord.Embed(title=missionDate.strftime("%A") + ": " + i[0], color=0x2E86C1)
				embed.add_field(name="Mission", value="[" + missionArr[0] + "](" + missionURL + ")", inline=True)
				embed.add_field(name="Map", value=missionArr[1], inline=True)
				embed.add_field(name="Author", value=i[2], inline=True)
				await ctx.send(embed=embed)

def setup(bot):
	bot.add_cog(Missions(bot))