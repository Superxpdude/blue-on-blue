# import pytest
# import blueonblue.db
import cogs.pings


def test_checkASCII():
	assert cogs.pings.check_ascii("Hello World")


def test_checkASCII_false():
	assert not cogs.pings.check_ascii("Héllo World")


def test_sanitize_empty():
	assert cogs.pings.sanitize_check("") is not None


def test_sanitize_mention():
	assert cogs.pings.sanitize_check("<@96018174163570688>") is not None


def test_sanitize_long():
	assert cogs.pings.sanitize_check("This is a long string which exceeds twenty characters") is not None


def test_sanitize_emote():
	assert cogs.pings.sanitize_check("Hello :eyes: world") is not None


def test_sanitize_nonASCII():
	assert cogs.pings.sanitize_check("Héllo World") is not None


def test_sanitize_comma():
	assert cogs.pings.sanitize_check("Hello, World") is not None


# @pytest.mark.asyncio
# async def test_ping_init(db: blueonblue.db.DBConnection):
# 	pingName = "pinginit"
# 	serverID = 50
# 	userID = 100

# 	pingID = await db.pings.create(pingName, serverID)
# 	await db.pings.add_user(pingName, serverID, userID)
# 	users = await db.pings.get_user_ids_by_ping_id(pingID)
# 	assert users[0] == userID


# @pytest.mark.asyncio
# async def test_ping_get_id(db: blueonblue.db.DBConnection):
# 	pingName = "pinggetID"
# 	serverID = 50

# 	pingID = await db.pings.create(pingName, serverID)
# 	assert (await db.pings.get_id(pingName, serverID)) == pingID


# @pytest.mark.asyncio
# async def test_ping_count(db: blueonblue.db.DBConnection):
# 	# Keeps the same DB from the last test
# 	pingName = "pingcount"
# 	serverID = 50
# 	userIDs = (100, 101)

# 	pingID = await db.pings.create(pingName, serverID)
# 	for u in userIDs:
# 		await db.pings.add_user(pingName, serverID, u)

# 	userCount = await db.pings.count_users(pingName, serverID)
# 	assert userCount == 2
