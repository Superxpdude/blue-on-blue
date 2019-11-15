import discord
from discord.ext import commands, tasks
import blueonblue
from blueonblue.config import config
from tinydb import TinyDB, Query
from tinydb.operations import delete as tiny_delete
import typing
import logging
log = logging.getLogger("blueonblue")

# Return a user ID from a user object, or pass the value through if already an ID
def get_user_id(usr):
	if type(usr) is discord.member.Member:
		return usr.id
	else:
		return usr

def no_excluded_roles(bot, member, excluded_roles):
	for r in excluded_roles:
		role = bot._guild.get_role(r)
		if role in member.roles:
			return False
	return True

async def update_user_roles(self, *members):
	"""Update the roles for multiple users in the database
	Requires a list of members (not users) for the server"""
	everyone = self.bot._guild.default_role # Get the default role
	bot_role = self.bot._guild.me.top_role # Get the bot's highest role
	ignored_roles = [] # Array of role IDs to be ignored when updating
	excluded_roles = [
		config["SERVER"]["ROLES"]["DEAD"],
		config["SERVER"]["ROLES"]["PUNISH"]
	] # Array of role IDs that exclude the user roles from being updated
	for m in members:
		if type(m) is int: # Make sure that we have the member object
			m = self.bot._guild.get_member(m)
		
		# Do not update roles if the user is a bot, does not have roles, or has any excluded role
		if (m.bot is not True) and (len(m.roles) > 1) and (no_excluded_roles(self.bot, m, excluded_roles)):
			roles = []
			for r in m.roles:
				if (r < bot_role) and (r != everyone): # Only store roles that the bot can add/remove
					roles.append({"name": r.name, "id": r.id})
			self.db.upsert({"user_id": m.id, "roles": roles}, Query().user_id == m.id)

class Users(commands.Cog, name="Users"):
	"""Base cog for user management."""
	def __init__(self,bot):
		self.bot = bot
		self.db = TinyDB('db/users.json', sort_keys=True, indent=4) # Define the database
		self.user_update_loop.start()
	
	def cog_unload(self):
		self.user_update_loop.stop()
	
	async def read_data(self, usr: typing.Union[discord.Member, int], key: str):
		"""Read data from the users database."""
		usr_id = get_user_id(usr) # Make sure that we have the userID
		u = self.db.get(Query().user_id == usr_id) # Get the user information from the database
		try:
			return u[key]
		except:
			return None
	
	async def write_data(self, usr: typing.Union[discord.Member, int], value: dict):
		"""Write data to the users database."""
		usr_id = get_user_id(usr) # Make sure that we have the userID
		value["user_id"] = usr_id # Make sure that we have the user ID present in the data
		self.db.upsert(value, Query().user_id == usr_id) # Write the information
	
	async def remove_data(self, usr: typing.Union[discord.Member, int], key: str):
		"""Remove a key from a user's data."""
		usr_id = get_user_id(usr) # Make sure that we have the userID
		if self.db.contains(Query().user_id == usr_id): # Check if the user exists in the db
			self.db.update(tiny_delete(key), Query().user_id == usr_id)
	
	@tasks.loop(hours=1, reconnect=True)
	async def user_update_loop(self):
		members = self.bot._guild.members # Get a list of members
		for m in members:
			if (m.bot is not True) and (len(m.roles) > 1): # Only look for users that have a role assigned
				self.db.upsert({"user_id": m.id, "name": m.name, "display_name": m.display_name}, Query().user_id == m.id)
		await update_user_roles(self,*members)
	
	@commands.command()
	async def user_update(self, ctx):
		members = self.bot._guild.members # Get a list of members
		for m in members:
			if (m.bot is not True) and (len(m.roles) > 1): # Only look for users that have a role assigned
				self.db.upsert({"user_id": m.id, "name": m.name, "display_name": m.display_name}, Query().user_id == m.id)
		await update_user_roles(self,*members)

def setup(bot):
	bot.add_cog(Users(bot))