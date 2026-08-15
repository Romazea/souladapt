import time


class FakeMemory:
    """
    A fake SoulMemory-like object with timeline support.
    Proves habits() works with ANY object providing timeline().
    """

    def __init__(self, timeline=None):
        self.timeline_data = timeline or []

    def recall(self, query, limit=5):
        return []

    def timeline(self, limit=200):
        return self.timeline_data[:limit]


def _two_mondays():
    """Return two timestamps 7 days apart, both on a Monday."""
    day = 86400
    t = int(time.time())
    while time.localtime(t).tm_wday != 0:  # 0 = Monday
        t -= day
    return t, t - 7 * day


class TestHabits:
    """Tests for routine detection from the memory timeline."""

    def test_habits_detect_repeated_topic(self, adapt):
        """A topic repeated on the same weekday becomes a habit."""
        monday1, monday2 = _two_mondays()
        adapt.memory = FakeMemory(timeline=[
            {"content": "Morning running session at the park",
             "created_at": monday1},
            {"content": "Evening running at the park",
             "created_at": monday2},
        ])
        habits = adapt.habits()
        assert any(h["topic"] == "running" for h in habits)
        habit = [h for h in habits if h["topic"] == "running"][0]
        assert habit["day"] == "Monday"
        assert habit["count"] == 2

    def test_habits_empty_without_memory(self, adapt):
        """No memory connected → no habits."""
        assert adapt.habits() == []

    def test_habits_need_repetition(self, adapt):
        """A single mention is not a habit."""
        monday1, _ = _two_mondays()
        adapt.memory = FakeMemory(timeline=[
            {"content": "Morning running session at the park",
             "created_at": monday1},
        ])
        assert adapt.habits() == []


class TestBringUp:
    """Tests for proactive topic suggestions."""

    def test_bring_up_interests_first(self, adapt):
        """Interests observations come first in suggestions."""
        adapt.observe("Le gustan los gatos", "interests")
        suggestions = adapt.bring_up()
        assert "Le gustan los gatos" in suggestions

    def test_bring_up_respects_limit(self, adapt):
        """bring_up() never returns more than limit."""
        adapt.observe("Le gustan los gatos", "interests")
        adapt.observe("Le gusta el café", "interests")
        adapt.observe("Le encanta el cine", "interests")
        assert len(adapt.bring_up(limit=2)) == 2


class TestDecayObservations:
    """Tests for fading unvalidated observations."""

    def test_old_weak_observation_deleted(self, adapt):
        """Old + weak observations get deleted."""
        adapt.observe("dato viejo", "general")
        obs = adapt.observations()[0]
        adapt.backend.update_weight(obs["id"], 0.4)
        adapt.backend.db.execute(
            "UPDATE observations "
            "SET last_seen = last_seen - (40 * 86400)"
        )
        adapt.backend.db.commit()
        removed = adapt.decay_observations(max_age_days=30)
        assert removed == 1
        assert adapt.observations() == []

    def test_old_strong_observation_fades(self, adapt):
        """Old but strong observations fade instead of dying."""
        adapt.observe("dato fuerte", "general")
        adapt.observe("dato fuerte", "general")
        adapt.observe("dato fuerte", "general")  # weight ~1.2
        adapt.backend.db.execute(
            "UPDATE observations "
            "SET last_seen = last_seen - (40 * 86400)"
        )
        adapt.backend.db.commit()
        removed = adapt.decay_observations(max_age_days=30)
        assert removed == 0
        obs = adapt.observations()
        assert len(obs) == 1
        assert obs[0]["weight"] < 1.2  # it faded

    def test_recent_observation_untouched(self, adapt):
        """Recent observations are not affected."""
        adapt.observe("dato reciente", "general")
        removed = adapt.decay_observations(max_age_days=30)
        assert removed == 0
        assert len(adapt.observations()) == 1