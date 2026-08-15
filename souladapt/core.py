import time
from collections import Counter

from .backend import SQLiteBackend
from .sincerity import SincerityEngine


class SoulAdapt:
    """
    Adaptation & sincerity layer for AI companions.

    SoulAdapt learns HOW to treat a user (style, sensitive topics,
    interests) and, when connected to a SoulMemory-like object,
    calibrates how honest the AI should sound AND which tone
    fits the user's current mood.

    It never imports SoulMemory: any object with a
    .recall(query, limit) method satisfies the contract (duck typing).
    """

    # Mood (dominant emotion) → recommended tone for the AI
    TONE_BY_MOOD = {
        "sadness": "gentle",       # sad user → soft, warm tone
        "fear": "gentle",          # scared user → reassuring tone
        "anger": "careful",        # angry user → calm, careful tone
        "disgust": "careful",      # disgusted user → careful tone
        "joy": "energetic",        # happy user → match the energy
        "surprise": "energetic",   # surprised user → engaged tone
    }

    # Rule-based extraction patterns (Spanish + English)
    LEARN_RULES = [
        # Checked first: things the user wants to avoid
        ("sensitive", [
            "no me hables", "no me menciones", "odio", "detesto",
            "don't talk", "dont talk", "don't mention", "hate",
        ]),
        # How the user wants to be treated
        ("style", [
            "prefiero", "prefer", "me gusta que", "tratame",
            "trátame", "call me", "respondeme", "respóndeme",
        ]),
        # What the user likes
        ("interests", [
            "me gusta", "me encanta", "me encantan", "amo",
            "i like", "i love", "enjoy",
        ]),
    ]

    # Simple stopwords for topic extraction (EN + ES)
    STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "i", "me",
        "my", "we", "our", "you", "your", "he", "she", "it",
        "they", "them", "and", "or", "but", "in", "on", "at",
        "to", "of", "for", "with", "about", "hoy", "ayer",
        "mañana", "el", "la", "los", "las", "un", "una", "y",
        "o", "pero", "de", "del", "en", "con", "mi", "su"
    }

    # Weekday names indexed like time.localtime().tm_wday
    DAY_NAMES = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday"
    ]

    def __init__(self, db_path="souladapt.db", memory=None, lang="en"):
        """
        Args:
            db_path: Path to the adaptation database
            memory: Optional SoulMemory-like object (duck typing).
                If provided, its recall() distances calibrate
                sincerity and its emotional_timeline() sets the tone.
            lang: 'en' or 'es' — language for sincerity phrases
        """
        self.backend = SQLiteBackend(db_path)
        self.memory = memory
        self.sincerity = SincerityEngine(lang=lang)

    # ------------------------------------------------------------------
    # Learning: what the companion knows about the user
    # ------------------------------------------------------------------
    def observe(self, content, category="general"):
        """
        Register something learned about the user.

        Args:
            content: What was learned ("prefiere respuestas cortas")
            category: 'style', 'sensitive', 'interests' or 'general'

        Returns:
            The observation ID
        """
        return self.backend.add_observation(content, category)

    def learn_from(self, text):
        """
        Auto-extract an observation from user text (ES/EN rules).
        The companion learns by itself, no babysitting needed.

        Returns:
            The observation ID, or None if nothing was detected.
        """
        lower = text.lower()
        for category, triggers in self.LEARN_RULES:
            if any(t in lower for t in triggers):
                return self.backend.add_observation(text, category)
        return None

    def observations(self, category=None):
        """Get learned observations, strongest first."""
        return self.backend.get_observations(category)

    def forget_observation(self, observation_id):
        """Delete an observation: the companion unlearns it."""
        self.backend.delete_observation(observation_id)

    # ------------------------------------------------------------------
    # Deciding: how the AI should respond
    # ------------------------------------------------------------------
    def decide(self, query, limit=3):
        """
        Decide HOW the AI should respond to a query.

        Returns:
            dict with style, avoid, interests, memories, confidence,
            honesty, mood and tone.
        """
        decision = {
            "style": [
                o["content"]
                for o in self.backend.get_observations("style")
            ],
            "avoid": [
                o["content"]
                for o in self.backend.get_observations("sensitive")
            ],
            "interests": [
                o["content"]
                for o in self.backend.get_observations("interests")
            ],
            "memories": [],
            "confidence": None,
            "honesty": "neutral",
            "mood": None,
            "tone": "neutral"
        }

        # If connected to a memory, calibrate sincerity + tone
        if self.memory is not None:
            results = self.memory.recall(query, limit=limit)
            evaluated = self.sincerity.evaluate(results)
            decision["memories"] = evaluated
            if evaluated:
                # The strongest memory sets the tone of certainty
                best = max(evaluated, key=lambda m: m["confidence"])
                decision["confidence"] = best["confidence"]
                decision["honesty"] = best["honesty"]

            # Tone calibrated to the user's current mood
            mood = self._detect_mood()
            if mood:
                decision["mood"] = mood
                decision["tone"] = self.TONE_BY_MOOD.get(
                    mood, "neutral"
                )

        return decision

    def prompt_context(self, query, limit=3):
        """
        Build a ready-to-paste context string for an LLM
        system prompt: adaptation + sincerity in one line.
        """
        d = self.decide(query, limit=limit)
        parts = []
        if d["style"]:
            parts.append("Style: " + "; ".join(d["style"]))
        if d["avoid"]:
            parts.append("Avoid topics: " + "; ".join(d["avoid"]))
        if d["interests"]:
            parts.append("Interests: " + "; ".join(d["interests"]))
        if d["tone"] != "neutral":
            parts.append(f"Tone: {d['tone']} (mood: {d['mood']})")
        # Only include memories the AI is confident (or almost) about
        for m in d["memories"]:
            if m["honesty"] == "assertive":
                parts.append(f"Fact: {m['content']}")
            elif m["honesty"] == "hedged":
                parts.append(f"Uncertain: {m['content']}")
        habits = self.habits()
        if habits:
            routine = ", ".join(
                f"{h['topic']} on {h['day']}s" for h in habits[:2]
            )
            parts.append("Routine: " + routine)

        if not parts:
            return "No adaptation data yet."
        return " | ".join(parts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _detect_mood(self):
        """
        Read the user's dominant emotion this week from the memory.
        Duck typing: uses emotional_timeline() if the memory has it.

        Returns:
            The dominant emotion string, or None if unavailable.
        """
        if self.memory is None:
            return None
        if not hasattr(self.memory, "emotional_timeline"):
            return None
        timeline = self.memory.emotional_timeline(weeks=1)
        if not timeline:
            return None
        # Last entry is the current week
        return timeline[-1]["dominant_emotion"]

    # ------------------------------------------------------------------
    # Insights: habits, proactivity & maintenance
    # ------------------------------------------------------------------
    def habits(self, min_count=2):
        """
        Detect routines from the connected memory.
        Duck typing: uses timeline() if the memory provides it.

        Returns:
            List of dicts with day, topic and count, e.g.
            [{'day': 'Monday', 'topic': 'gym', 'count': 3}]
        """
        if self.memory is None:
            return []
        if not hasattr(self.memory, "timeline"):
            return []
        memories = self.memory.timeline(limit=200)
        pairs = Counter()
        for m in memories:
            day = self.DAY_NAMES[
                time.localtime(m["created_at"]).tm_wday
            ]
            for topic in self._topics(m["content"]):
                pairs[(day, topic)] += 1
        return [
            {"day": day, "topic": topic, "count": count}
            for (day, topic), count in pairs.most_common(5)
            if count >= min_count
        ]

    def bring_up(self, limit=2):
        """
        Suggest topics the companion could mention proactively:
        strong interests + detected routines. A friend who
        remembers what you love.
        """
        suggestions = [
            o["content"]
            for o in self.backend.get_observations("interests")
        ][:limit]
        for habit in self.habits():
            if len(suggestions) >= limit:
                break
            suggestions.append(
                f"{habit['topic']} (usually on {habit['day']}s)"
            )
        return suggestions[:limit]

    def decay_observations(self, max_age_days=30, fade=0.2,
                           min_weight=0.3):
        """
        Fade observations not reinforced recently: what the
        companion "assumes" must be re-validated, like humans.

        Returns:
            Number of deleted observations
        """
        now = int(time.time())
        max_age = max_age_days * 86400
        removed = 0
        for o in self.backend.get_observations():
            if now - o["last_seen"] > max_age:
                new_weight = o["weight"] - fade
                if new_weight < min_weight:
                    self.backend.delete_observation(o["id"])
                    removed += 1
                else:
                    self.backend.update_weight(o["id"], new_weight)
        return removed

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _topics(self, text):
        """Extract meaningful lowercase topics from a text."""
        return [
            word.strip(".,!?;:")
            for word in text.lower().split()
            if (word.strip(".,!?;:") not in self.STOP_WORDS
                and len(word.strip(".,!?;:")) > 3)
        ]

    def close(self):
        """Close the adaptation database connection."""
        self.backend.close()