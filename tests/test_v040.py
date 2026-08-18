import sqlite3


class TestMultiUser:
    """Tests for multi-user isolation in SoulAdapt."""

    def test_user_isolation(self, adapt):
        """Observations of one user must not leak to another."""
        roman = adapt.user("roman")
        ana = adapt.user("ana")
        roman.observe("prefiere respuestas cortas", "style")
        ana.observe("prefiere tono cálido", "style")

        assert len(roman.observations("style")) == 1
        assert len(ana.observations("style")) == 1
        d_roman = roman.decide("hola")
        d_ana = ana.decide("hola")
        assert d_roman["style"] == ["prefiere respuestas cortas"]
        assert d_ana["style"] == ["prefiere tono cálido"]

    def test_learn_from_respects_user(self, adapt):
        """learn_from() stores the observation in the right user."""
        adapt.user("roman").learn_from("Prefiero respuestas cortas")
        assert len(adapt.user("roman").observations("style")) == 1
        assert len(adapt.user("ana").observations("style")) == 0

    def test_list_users(self, adapt):
        """list_users() returns all users with observations."""
        adapt.user("roman").observe("x", "style")
        adapt.user("ana").observe("y", "style")
        users = adapt.list_users()
        assert "roman" in users
        assert "ana" in users

    def test_delete_user(self, adapt):
        """delete_user() removes all observations of that user."""
        adapt.user("roman").observe("x", "style")
        adapt.user("ana").observe("y", "style")
        deleted = adapt.delete_user("ana")
        assert deleted == 1
        assert "ana" not in adapt.list_users()
        assert len(adapt.user("ana").observations()) == 0

    def test_default_user_unchanged(self, adapt):
        """Old API (no user_id) still works as before."""
        adapt.observe("prefiere respuestas cortas", "style")
        assert len(adapt.observations("style")) == 1
        assert adapt.decide("hola")["style"] == [
            "prefiere respuestas cortas"
        ]
        assert "default" in adapt.list_users()

    def test_migration_old_db(self, tmp_path):
        """A v0.3.0 database (without user_id) still opens fine."""
        db_path = str(tmp_path / "old.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE observations ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "content TEXT NOT NULL, "
            "category TEXT DEFAULT 'general', "
            "weight REAL DEFAULT 1.0, "
            "created_at INTEGER, "
            "last_seen INTEGER, "
            "times_seen INTEGER DEFAULT 1)"
        )
        conn.execute(
            "INSERT INTO observations "
            "(content, category, created_at, last_seen) "
            "VALUES ('dato viejo', 'general', 0, 0)"
        )
        conn.commit()
        conn.close()

        from souladapt import SoulAdapt
        a = SoulAdapt(db_path)
        # Old observations land in the 'default' user
        assert len(a.observations()) == 1
        assert "default" in a.list_users()
        a.close()