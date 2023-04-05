import blueonblue.db
import asyncio
import pytest
import pytest_asyncio


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="module")
async def init_db(tmp_path_factory: pytest.TempPathFactory) -> blueonblue.db.DB:
	dir = tmp_path_factory.mktemp("db")
	db = blueonblue.db.DB(f"{dir}/blueonblue-test.sqlite3")
	await db.migrate_version()
	return db


@pytest.mark.asyncio
async def test_db_version(init_db: blueonblue.db.DB):
	async with init_db.connect() as db:
		async with db.connection.cursor() as cursor:
			schema_version = (await (await cursor.execute("PRAGMA user_version")).fetchone())["user_version"]
	assert schema_version == blueonblue.db.DBVERSION
