class FakeMemory:
    """
    A fake SoulMemory-like object.

    SoulAdapt must work with ANY object that has
    .recall(query, limit) — that's the duck-typing contract.
    No SoulMemory import needed.
    """

    def __init__(self, results=None):
        self.results = results or []

    def recall(self, query, limit=5):
        return self.results[:limit]


class TestObservations:
    """Tests for the learning (observations) layer."""

    def test_observe_returns_id(self, adapt):
        """observe() should return a valid observation ID."""
        obs_id = adapt.observe("prefiere respuestas cortas", "style")
        assert obs_id is not None
        assert obs_id > 0

    def test_observe_and_list(self, adapt):
        """observations() should return what was learned."""
        adapt.observe("prefiere respuestas cortas", "style")
        adapt.observe("le gustan los gatos", "interests")
        assert len(adapt.observations()) == 2

    def test_reinforce_not_duplicate(self, adapt):
        """Same observation twice → reinforced, not duplicated."""
        id1 = adapt.observe("prefiere respuestas cortas", "style")
        id2 = adapt.observe("prefiere respuestas cortas", "style")

        assert id1 == id2
        obs = adapt.observations("style")
        assert len(obs) == 1
        assert obs[0]["times_seen"] == 2
        assert obs[0]["weight"] > 1.0

    def test_filter_by_category(self, adapt):
        """observations(category) should filter correctly."""
        adapt.observe("prefiere respuestas cortas", "style")
        adapt.observe("ruptura con Ana", "sensitive")

        sensitive = adapt.observations("sensitive")
        assert len(sensitive) == 1
        assert sensitive[0]["content"] == "ruptura con Ana"

    def test_forget_observation(self, adapt):
        """forget_observation() should delete what was learned."""
        obs_id = adapt.observe("dato temporal", "general")
        adapt.forget_observation(obs_id)
        assert adapt.observations() == []


class TestSincerity:
    """Tests for the honesty layer."""

    def test_confidence_from_distance(self, adapt):
        """Distance 0 → confidence 1; distance 2+ → confidence 0."""
        s = adapt.sincerity
        assert s.confidence_from_distance(0.0) == 1.0
        assert s.confidence_from_distance(2.0) == 0.0
        assert s.confidence_from_distance(3.0) == 0.0  # clamped

    def test_honesty_levels(self, adapt):
        """The three honesty levels by confidence."""
        s = adapt.sincerity
        assert s.honesty_level(0.9) == "assertive"
        assert s.honesty_level(0.6) == "hedged"
        assert s.honesty_level(0.2) == "admit"

    def test_phrase_calibrates(self, adapt):
        """phrase() should wrap memories honestly."""
        s = adapt.sincerity
        assert s.phrase("X", 0.9) == "X"
        assert s.phrase("X", 0.6).startswith("If I remember correctly")
        assert s.phrase("X", 0.2).startswith("I don't have a clear memory")


class TestDecide:
    """Tests for decide(): the adaptation + sincerity combo."""

    def test_decide_without_memory(self, adapt):
        """Without memory: neutral honesty, None confidence."""
        adapt.observe("prefiere respuestas cortas", "style")
        d = adapt.decide("hola")

        assert d["honesty"] == "neutral"
        assert d["confidence"] is None
        assert d["style"] == ["prefiere respuestas cortas"]
        assert d["memories"] == []

    def test_decide_with_strong_memory(self, adapt):
        """Strong match → assertive."""
        adapt.memory = FakeMemory([
            {"content": "You had coffee with Ana", "distance": 0.2}
        ])
        d = adapt.decide("qué sabes de Ana?")

        assert d["honesty"] == "assertive"
        assert d["confidence"] == 0.9
        assert len(d["memories"]) == 1

    def test_decide_with_weak_memory(self, adapt):
        """Weak match → admit uncertainty instead of inventing."""
        adapt.memory = FakeMemory([
            {"content": "Algo de Ana quizás", "distance": 1.6}
        ])
        d = adapt.decide("qué sabes de Ana?")

        assert d["honesty"] == "admit"
        assert d["confidence"] == 0.2

    def test_decide_includes_avoid_topics(self, adapt):
        """Sensitive observations should appear in 'avoid'."""
        adapt.observe("ruptura con Ana", "sensitive")
        d = adapt.decide("hola")

        assert d["avoid"] == ["ruptura con Ana"]

    def test_duck_typing_contract(self, adapt):
        """SoulAdapt works with ANY object with .recall() — no SoulMemory."""
        adapt.memory = FakeMemory([
            {"content": "Fui al gimnasio", "distance": 0.4}
        ])
        d = adapt.decide("gimnasio")

        # distance 0.4 → confidence 0.8 → assertive
        assert d["honesty"] == "assertive"