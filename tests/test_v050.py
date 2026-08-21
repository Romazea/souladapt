class TestPresets:
    """Tests for personality presets."""

    def test_default_preset(self, adapt):
        """Default preset is casual and appears in decide()."""
        d = adapt.decide("hola")
        assert d["preset"] == "casual"
        assert d["preset_hint"] == "relaxed, friendly, informal"

    def test_custom_preset_at_init(self, tmp_path):
        """preset can be set at initialization."""
        from souladapt import SoulAdapt
        a = SoulAdapt(str(tmp_path / "warm.db"), preset="warm")
        assert a.preset == "warm"
        assert a.decide("hola")["preset_hint"] == (
            "affectionate, supportive, close"
        )
        a.close()

    def test_set_preset(self, adapt):
        """set_preset() changes the personality; unknown → False."""
        assert adapt.set_preset("direct") is True
        assert adapt.preset == "direct"
        assert adapt.set_preset("bogus") is False
        assert adapt.preset == "direct"

    def test_unknown_preset_fallback(self, tmp_path):
        """Unknown preset at init → falls back to casual."""
        from souladapt import SoulAdapt
        a = SoulAdapt(str(tmp_path / "x.db"), preset="xyz")
        assert a.preset == "casual"
        a.close()


class TestProfile:
    """Tests for the adaptation profile."""

    def test_profile_empty(self, adapt):
        """profile() with no observations → stranger summary."""
        p = adapt.profile()
        assert p["observation_count"] == 0
        assert "stranger" in p["summary"]

    def test_profile_summary(self, adapt):
        """profile() summarizes style, interests and sensitive."""
        adapt.observe("Prefiere respuestas cortas", "style")
        adapt.observe("Le gustan los gatos", "interests")
        adapt.observe("Ruptura con Ana", "sensitive")
        p = adapt.profile()
        assert p["observation_count"] == 3
        assert "Prefiere respuestas cortas" in p["style"]
        assert "Le gustan los gatos" in p["interests"]
        assert "Ruptura con Ana" in p["sensitive"]
        assert "Knows you:" in p["summary"]


class TestBackups:
    """Tests for JSON export/import of observations."""

    def test_export_import_roundtrip(self, adapt, tmp_path):
        """export_json + import_json restore observations."""
        from souladapt import SoulAdapt
        adapt.observe("Prefiere respuestas cortas", "style")
        adapt.observe("Le gustan los gatos", "interests")
        backup = str(tmp_path / "backup.json")
        exported = adapt.export_json(backup)
        assert exported == 2

        restored = SoulAdapt(str(tmp_path / "restored.db"))
        assert restored.import_json(backup) == 2
        assert len(restored.observations()) == 2
        contents = [o["content"] for o in restored.observations()]
        assert "Prefiere respuestas cortas" in contents
        restored.close()

    def test_export_per_user(self, adapt, tmp_path):
        """export_json(user_id) exports only that user."""
        adapt.user("roman").observe("dato roman", "style")
        adapt.user("ana").observe("dato ana", "style")
        backup = str(tmp_path / "roman.json")
        exported = adapt.export_json(backup, user_id="roman")
        assert exported == 1