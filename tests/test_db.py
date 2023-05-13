import blueonblue.db
import pytest


@pytest.mark.asyncio
async def test_db_version(init_db: blueonblue.db.DB):
	print(init_db)
	async with init_db.connect() as db:
		async with db.connection.cursor() as cursor:
			schema_version = (await (await cursor.execute("PRAGMA user_version")).fetchone())["user_version"]
	assert schema_version == blueonblue.db.DBVERSION
