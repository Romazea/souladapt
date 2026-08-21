import json
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

    Supports multiple users: each user gets an isolated
    adaptation space via adapt.user(user_id).

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

    # Base personality presets: how the companion sounds by default
    TONE_PRESETS = {
        "formal": "polite, structured, respectful",
        "casual": "relaxed, friendly, informal",
        "warm": "affectionate, supportive, close",
        "direct": "brief, honest, to the point",
    }

    def __init__(self, db_path="souladapt.db", memory=None,
                 lang="en", preset="casual"):
        """
        Args:
            db_path: Path to the adaptation database
            memory: Optional SoulMemory-like object (duck typing).
                If provided, its recall() distances calibrate
                sincerity and its emotional_timeline() sets the tone.
            lang: 'en' or 'es' — language for sincerity phrases
            preset: Base personality tone ('formal', 'casual',
                'warm' or 'direct'). Falls back to 'casual'.
        """
        self.backend = SQLiteBackend(db_path)
        self.memory = memory
        self.sincerity = SincerityEngine(lang=lang)
        # Base personality tone (the mood can override the energy)
        self.preset = (
            preset if preset in self.TONE_PRESETS else "casual"
        )

    # ------------------------------------------------------------------
    # Multi-user
    # ------------------------------------------------------------------
    def user(self, user_id):
        """
        Get an isolated adaptation space for a specific user.

        Args:
            user_id: Unique identifier for the user

        Returns:
            A UserAdapt instance scoped to that user
        """
        return UserAdapt(self, user_id)

    def list_users(self):
        """List all user IDs that have observations."""
        return self.backend.list_users()

    def delete_user(self, user_id):
        """
        Delete a user and ALL their observations.

        Returns:
            Number of observations deleted
        """
        return self.backend.delete_user(user_id)

    # ------------------------------------------------------------------
    # Learning: what the companion knows about the user
    # ------------------------------------------------------------------
    def observe(self, content, category="general",
                user_id="default"):
        """
        Register something learned about a user.

        Args:
            content: What was learned ("prefiere respuestas cortas")
            category: 'style', 'sensitive', 'interests' or 'general'
            user_id: Owner of the observation

        Returns:
            The observation ID
        """
        return self.backend.add_observation(
            content, category, user_id=user_id
        )

    def learn_from(self, text, user_id="default"):
        """
        Auto-extract an observation from user text (ES/EN rules).
        The companion learns by itself, no babysitting needed.

        Returns:
            The observation ID, or None if nothing was detected.
        """
        lower = text.lower()
        for category, triggers in self.LEARN_RULES:
            if any(t in lower for t in triggers):
                return self.backend.add_observation(
                    text, category, user_id=user_id
                )
        return None

    def observations(self, category=None, user_id="default"):
        """Get learned observations of a user, strongest first."""
        return self.backend.get_observations(category, user_id)

    def forget_observation(self, observation_id):
        """Delete an observation: the companion unlearns it."""
        self.backend.delete_observation(observation_id)

    # ------------------------------------------------------------------
    # Deciding: how the AI should respond
    # ------------------------------------------------------------------
    def decide(self, query, limit=3, user_id="default"):
        """
        Decide HOW the AI should respond to a query.

        Returns:
            dict with style, avoid, interests, memories, confidence,
            honesty, mood and tone.
        """
        decision = {
            "style": [
                o["content"]
                for o in self.backend.get_observations(
                    "style", user_id
                )
            ],
            "avoid": [
                o["content"]
                for o in self.backend.get_observations(
                    "sensitive", user_id
                )
            ],
            "interests": [
                o["content"]
                for o in self.backend.get_observations(
                    "interests", user_id
                )
            ],
            "memories": [],
            "confidence": None,
            "honesty": "neutral",
            "mood": None,
            "tone": "neutral",
            "preset": self.preset,
            "preset_hint": self.TONE_PRESETS[self.preset]
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

    def prompt_context(self, query, limit=3, user_id="default"):
        """
        Build a ready-to-paste context string for an LLM
        system prompt: adaptation + sincerity in one line.
        """
        d = self.decide(query, limit, user_id=user_id)
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
        if not parts:
            return "No adaptation data yet."
        return " | ".join(parts)

    # ------------------------------------------------------------------
    # Profile, presets & backups
    # ------------------------------------------------------------------
    def set_preset(self, preset):
        """
        Change the companion's base personality tone.

        Returns:
            True if the preset exists, False otherwise
        """
        if preset in self.TONE_PRESETS:
            self.preset = preset
            return True
        return False

    def profile(self, user_id="default"):
        """
        Generate an adaptation summary of the user
        (the SoulAdapt version of SoulMemory.reflect()).

        Returns:
            dict with observation_count, style, sensitive,
            interests and a human-readable summary
        """
        obs = self.backend.get_observations(None, user_id)
        if not obs:
            return {
                "observation_count": 0,
                "style": [],
                "sensitive": [],
                "interests": [],
                "summary": "No observations yet. A stranger."
            }
        style = [
            o["content"] for o in obs if o["category"] == "style"
        ]
        sensitive = [
            o["content"] for o in obs if o["category"] == "sensitive"
        ]
        interests = [
            o["content"] for o in obs if o["category"] == "interests"
        ]
        parts = [f"{len(obs)} observations"]
        if style:
            parts.append(f"style: {', '.join(style[:2])}")
        if interests:
            parts.append(f"loves: {', '.join(interests[:2])}")
        if sensitive:
            parts.append(f"avoids: {', '.join(sensitive[:2])}")
        return {
            "observation_count": len(obs),
            "style": style,
            "sensitive": sensitive,
            "interests": interests,
            "summary": "Knows you: " + " | ".join(parts) + "."
        }

    def export_json(self, path="souladapt_backup.json", user_id=None):
        """
        Export all observations to a JSON backup.

        Returns:
            Number of observations exported
        """
        rows = self.backend.export_rows(user_id)
        observations = [
            {
                "content": r[1],
                "category": r[2],
                "weight": r[3],
                "user_id": r[4],
                "created_at": r[5],
                "last_seen": r[6],
                "times_seen": r[7]
            }
            for r in rows
        ]
        data = {
            "format": "souladapt-backup",
            "version": "0.5.0",
            "exported_at": int(time.time()),
            "observations": observations
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return len(observations)

    def import_json(self, path):
        """
        Restore observations from a JSON backup.

        Returns:
            Number of observations restored
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        restored = 0
        for item in data.get("observations", []):
            self.backend.add_observation(
                item["content"],
                category=item.get("category", "general"),
                weight=item.get("weight", 1.0),
                user_id=item.get("user_id", "default")
            )
            restored += 1
        return restored

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

    def bring_up(self, limit=2, user_id="default"):
        """
        Suggest topics the companion could mention proactively:
        strong interests + detected routines. A friend who
        remembers what you love.
        """
        suggestions = [
            o["content"]
            for o in self.backend.get_observations(
                "interests", user_id
            )
        ][:limit]
        for habit in self.habits():
            if len(suggestions) >= limit:
                break
            suggestions.append(
                f"{habit['topic']} (usually on {habit['day']}s)"
            )
        return suggestions[:limit]

    def decay_observations(self, max_age_days=30, fade=0.2,
                           min_weight=0.3, user_id="default"):
        """
        Fade observations not reinforced recently: what the
        companion "assumes" must be re-validated, like humans.

        Returns:
            Number of deleted observations
        """
        now = int(time.time())
        max_age = max_age_days * 86400
        removed = 0
        for o in self.backend.get_observations(None, user_id):
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


class UserAdapt:
    """
    An isolated adaptation space for a single user.
    Same API as SoulAdapt, scoped to one user_id.
    """

    def __init__(self, parent, user_id):
        self._parent = parent
        self.user_id = user_id

    def observe(self, content, category="general"):
        return self._parent.observe(
            content, category, user_id=self.user_id
        )

    def learn_from(self, text):
        return self._parent.learn_from(text, user_id=self.user_id)

    def observations(self, category=None):
        return self._parent.observations(category, user_id=self.user_id)

    def forget_observation(self, observation_id):
        return self._parent.forget_observation(observation_id)

    def decide(self, query, limit=3):
        return self._parent.decide(
            query, limit, user_id=self.user_id
        )

    def prompt_context(self, query, limit=3):
        return self._parent.prompt_context(
            query, limit, user_id=self.user_id
        )

    def habits(self, min_count=2):
        return self._parent.habits(min_count)

    def bring_up(self, limit=2):
        return self._parent.bring_up(limit, user_id=self.user_id)

    def decay_observations(self, max_age_days=30, fade=0.2,
                           min_weight=0.3):
        return self._parent.decay_observations(
            max_age_days, fade, min_weight, user_id=self.user_id
        )

    def profile(self):
        return self._parent.profile(user_id=self.user_id)

    def export_json(self, path="souladapt_backup.json"):
        return self._parent.export_json(path, user_id=self.user_id)

    def import_json(self, path):
        return self._parent.import_json(path)