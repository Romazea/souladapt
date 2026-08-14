import pytest
from souladapt import SoulAdapt


@pytest.fixture
def adapt(tmp_path):
    """
    Create a fresh SoulAdapt instance with a temporary database.
    Each test gets its own isolated database.
    """
    db_path = tmp_path / "test_adapt.db"
    adapter = SoulAdapt(str(db_path))
    yield adapter
    adapter.close()