from discord.ext import commands, tasks
import slash_util

from blueonblue.bot import BlueOnBlueBot

import logging
log = logging.getLogger("bloeonblue")

class Users(slash_util.Cog, name="Users"):
	"""Base cog for user management"""
	def __init__(self, bot, *args, **kwargs):
		super().__init__(bot, *args, **kwargs)
		self.bot: BlueOnBlueBot = bot
		self.db_update_loop.start()

	def cog_unload(self):
		self.db_update_loop.stop()

	@tasks.loop(seconds=10, reconnect = True)
	async def db_update_loop(self):
		"""Periodically updates the user database"""
		log.debug("Starting user update loop.")
		async with self.bot.db_connection.cursor() as cursor:
			for g in self.bot.guilds:
				# Update role info
				# Get a list of currently stored roles from the database to see which ones we need to delete
				removedRoles = []
				await cursor.execute("SELECT role_id FROM roles WHERE server_id = :server_id", {"server_id": g.id})
				serverRoles = await cursor.fetchall()
				for r in serverRoles:
					removedRoles.append(r["role_id"])

				for r in g.roles:
					if (not r.managed) and (r != g.default_role) and (r < g.me.top_role): # Ignore roles that we can't add/remove
						if r.id in removedRoles:
							# If the role already exists, don't update the block_updates column
							await cursor.execute("UPDATE roles SET name = :name WHERE server_id = :server_id AND role_id = :role_id",
								{"server_id": g.id, "role_id": r.id, "name": r.name})
							removedRoles.remove(r.id) # Remove this role from the to-be-deleted list
						else:
							# If the role does not exist, add it to the database
							await cursor.execute("INSERT INTO roles (server_id, role_id, name) VALUES (:server_id, :role_id, :name)",
							{"server_id": g.id, "role_id": r.id, "name": r.name})

				# Remove roles that are no longer present in the server
				await cursor.executemany("DELETE FROM roles WHERE role_id IN (?)", [(i,) for i in removedRoles])

				# Update member info
				for m in g.members:
					if (not m.bot) and (len(m.roles)>1): # Only look for users that are not bots, and have at least one role assigned
						await cursor.execute("INSERT OR REPLACE INTO users (server_id, user_id, display_name, name) VALUES\
							(:server_id, :user_id, :display_name, :name)", {"server_id": g.id, "user_id": m.id, "name": m.name, "display_name": m.display_name})


						# Get a list of role IDs on the user that we can edit
						memberRoles = []
						updatesBlocked = False
						for r in m.roles:
							# Check if the user has any update blocking roles
							await cursor.execute("SELECT * FROM roles WHERE role_id = :id AND block_updates = 1",{"id": r.id})
							if await cursor.fetchone() is not None:
								updatesBlocked = True
							# Add roles we can manage to the list
							if (not r.managed) and (r != g.default_role) and (r < g.me.top_role):
								memberRoles.append(r)

						# Only update the user if they don't have any "update blocked" roles
						if not updatesBlocked:
							# Remove roles that are no longer on the user
							activeRoles = memberRoles.copy()
							# Get our stored list of roles
							await cursor.execute("SELECT server_id, user_id, role_id FROM user_roles WHERE user_id = :user_id", {"user_id": m.id})
							dbRoles = await cursor.fetchall()
							for r in dbRoles:
								if r["role_id"] in activeRoles:
									dbRoles.remove(m)

							# Remove old roles from the database
							await cursor.executemany("DELETE FROM user_roles WHERE (server_id = ? AND user_id = ? AND role_id = ?)", dbRoles)

							# Add new user roles to the database
							userRoles = []
							for r in memberRoles:
								userRoles.append({"server_id": g.id, "user_id": m.id, "role_id": r.id})

							await cursor.executemany("INSERT OR REPLACE INTO user_roles VALUES (:server_id, :user_id, :role_id)", userRoles)

			await self.bot.db_connection.commit()
		log.debug("User update loop complete")

	# Create the DB tables before the loop starts running
	@db_update_loop.before_loop
	async def before_db_update_loop(self):
		await self.bot.wait_until_ready()
		async with self.bot.db_connection.cursor() as cursor:
			# Create the tables if they do not exist
			await cursor.execute("CREATE TABLE if NOT EXISTS users (\
				server_id INTEGER,\
				user_id INTEGER,\
				display_name TEXT,\
				name TEXT,\
				UNIQUE(server_id,user_id))")
			await cursor.execute("CREATE TABLE if NOT EXISTS user_roles (\
				server_id INTEGER,\
				user_id INTEGER,\
				role_id INTEGER,\
				UNIQUE(server_id,user_id,role_id),\
				FOREIGN KEY (role_id) REFERENCES roles (role_id) ON DELETE CASCADE)")
			await cursor.execute("CREATE TABLE if NOT EXISTS roles(\
				server_id INTEGER,\
				role_id INTEGER PRIMARY KEY,\
				name TEXT,\
				block_updates INTEGER NOT NULL DEFAULT 0,\
				UNIQUE(server_id,role_id))")
			await self.bot.db_connection.commit()

def setup(bot: BlueOnBlueBot):
	bot.add_cog(Users(bot))
