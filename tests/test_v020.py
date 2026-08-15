class FakeMemory:
    """
    A fake SoulMemory-like object with emotional_timeline support.
    Proves the duck-typing contract: SoulAdapt works with ANY object
    that has .recall() and .emotional_timeline().
    """

    def __init__(self, results=None, timeline=None):
        self.results = results or []
        self.timeline_data = timeline or []

    def recall(self, query, limit=5):
        return self.results[:limit]

    def emotional_timeline(self, weeks=4):
        return self.timeline_data


class TestTone:
    """Tests for mood-based tone adaptation."""

    def test_tone_neutral_without_memory(self, adapt):
        """No memory → neutral tone and no mood."""
        d = adapt.decide("hola")
        assert d["tone"] == "neutral"
        assert d["mood"] is None

    def test_tone_gentle_when_sad(self, adapt):
        """Sad user → gentle tone."""
        adapt.memory = FakeMemory(timeline=[
            {"week": 0, "label": "this week",
             "dominant_emotion": "sadness", "memory_count": 3}
        ])
        d = adapt.decide("hola")
        assert d["mood"] == "sadness"
        assert d["tone"] == "gentle"

    def test_tone_energetic_when_happy(self, adapt):
        """Happy user → energetic tone."""
        adapt.memory = FakeMemory(timeline=[
            {"week": 0, "label": "this week",
             "dominant_emotion": "joy", "memory_count": 5}
        ])
        d = adapt.decide("hola")
        assert d["tone"] == "energetic"


class TestLearnFrom:
    """Tests for auto-learning from user text."""

    def test_learn_style(self, adapt):
        """'Prefiero...' → style observation."""
        adapt.learn_from("Prefiero respuestas cortas")
        assert len(adapt.observations("style")) == 1

    def test_learn_interests(self, adapt):
        """'Me encanta...' → interests observation."""
        adapt.learn_from("Me encanta el gimnasio")
        assert len(adapt.observations("interests")) == 1

    def test_learn_sensitive(self, adapt):
        """'Odio...' → sensitive observation."""
        adapt.learn_from("Odio que me hablen de política")
        assert len(adapt.observations("sensitive")) == 1

    def test_learn_nothing(self, adapt):
        """Plain text → no observation, returns None."""
        result = adapt.learn_from("El cielo es azul")
        assert result is None
        assert adapt.observations() == []


class TestSpanishSincerity:
    """Tests for bilingual sincerity phrases."""

    def test_spanish_hedged(self, tmp_path):
        """lang='es' → hedged phrase in Spanish."""
        from souladapt import SoulAdapt
        a = SoulAdapt(str(tmp_path / "es1.db"), lang="es")
        assert a.sincerity.phrase("X", 0.6).startswith(
            "Si mal no recuerdo"
        )
        a.close()

    def test_spanish_admit(self, tmp_path):
        """lang='es' → admit phrase in Spanish."""
        from souladapt import SoulAdapt
        a = SoulAdapt(str(tmp_path / "es2.db"), lang="es")
        assert a.sincerity.phrase("X", 0.2).startswith(
            "No recuerdo bien eso"
        )
        a.close()

    def test_unknown_lang_fallback(self, tmp_path):
        """Unknown lang → falls back to English."""
        from souladapt import SoulAdapt
        a = SoulAdapt(str(tmp_path / "es3.db"), lang="fr")
        assert a.sincerity.lang == "en"
        a.close()


class TestPromptContext:
    """Tests for the LLM context bridge."""

    def test_prompt_context_basic(self, adapt):
        """Style + avoid observations appear in the context."""
        adapt.observe("Prefiere respuestas cortas", "style")
        adapt.observe("Ruptura con Ana", "sensitive")
        ctx = adapt.prompt_context("hola")
        assert "Style:" in ctx
        assert "Avoid topics:" in ctx

    def test_prompt_context_with_memory(self, adapt):
        """Confident memories appear as facts."""
        adapt.memory = FakeMemory(results=[
            {"content": "You had coffee with Ana", "distance": 0.2}
        ])
        ctx = adapt.prompt_context("Ana")
        assert "Fact: You had coffee with Ana" in ctx

    def test_prompt_context_empty(self, adapt):
        """No data → helpful placeholder."""
        assert adapt.prompt_context("hola") == "No adaptation data yet."