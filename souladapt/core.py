from .backend import SQLiteBackend
from .sincerity import SincerityEngine


class SoulAdapt:
    """
    Adaptation & sincerity layer for AI companions.

    SoulAdapt learns HOW to treat a user (style, sensitive topics,
    interests) and, when connected to a SoulMemory-like object,
    calibrates how honest and confident the AI should sound.

    It never imports SoulMemory: any object with a
    .recall(query, limit) method satisfies the contract (duck typing).
    """

    def __init__(self, db_path="souladapt.db", memory=None):
        """
        Args:
            db_path: Path to the adaptation database
            memory: Optional SoulMemory-like object (duck typing).
                If provided, its recall() distances are used to
                calibrate sincerity.
        """
        self.backend = SQLiteBackend(db_path)
        self.memory = memory
        self.sincerity = SincerityEngine()

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

        Combines the learned observations with sincerity calibrated
        from the connected memory (if any).

        Args:
            query: What the user just said
            limit: How many memories to evaluate for sincerity

        Returns:
            dict with:
                style      → how to talk to the user (list of hints)
                avoid      → sensitive topics to handle with care
                interests  → things the user likes
                memories   → evaluated memories (content, confidence,
                             honesty)
                confidence → best confidence score (None if no memory)
                honesty    → 'assertive' / 'hedged' / 'admit' / 'neutral'
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
            "honesty": "neutral"
        }

        # If connected to a memory, calibrate sincerity from it
        if self.memory is not None:
            results = self.memory.recall(query, limit=limit)
            evaluated = self.sincerity.evaluate(results)
            decision["memories"] = evaluated
            if evaluated:
                # The strongest memory sets the tone of certainty
                best = max(evaluated, key=lambda m: m["confidence"])
                decision["confidence"] = best["confidence"]
                decision["honesty"] = best["honesty"]

        return decision

    def close(self):
        """Close the adaptation database connection."""
        self.backend.close()