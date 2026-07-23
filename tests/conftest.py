import os
import asyncio
import pytest

from core.database import DB_PATH


@pytest.fixture(scope="session", autouse=True)
def init_test_database():
    """
    Ensures every table exists before any test runs, by calling the same
    init functions the app calls on startup. Runs once per test session.
    """
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    from core.database import init_db as init_core_db
    from identity.database import init_identity_db
    from agents.database import init_agent_db
    from content.database import init_content_db
    from economic.database import init_economic_db
    from governance.database import init_governance_db

    async def _init_all():
        await init_core_db()
        await init_identity_db()
        await init_agent_db()
        await init_content_db()
        await init_economic_db()
        await init_governance_db()

    asyncio.run(_init_all())

    yield

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
