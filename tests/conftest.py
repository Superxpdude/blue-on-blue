import asyncio
import pytest
import pytest_asyncio

import blueonblue.db


@pytest.fixture(scope = "session")
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope = "session")
async def init_db(tmp_path_factory: pytest.TempPathFactory) -> blueonblue.db.DB:
	dir = tmp_path_factory.mktemp("db")
	db = blueonblue.db.DB(f"{dir}/blueonblue-test.sqlite3")
	await db.migrate_version()
	return db


@pytest_asyncio.fixture(scope = "module")
async def db(init_db: blueonblue.db.DB):
	async with init_db.connect() as db:
		yield db
