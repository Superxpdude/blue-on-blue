import discord
from discord.ext import commands, tasks
import blueonblue
from blueonblue.config import config
from datetime import datetime, timedelta
import gspread
import asyncio
import json
import requests
import os
from oauth2client.service_account import ServiceAccountCredentials


class Events(commands.Cog, name='Events'):

    def __init__(self, bot):
        self.bot = bot
        self.event_sheets = 'events.json'
        self.event_channel = config['SERVER']['CHANNELS']['EVENT_ANNOUNCEMENTS']

    @commands.command(name='register_event')
    async def register_event(self, context, text_blob: str=""):