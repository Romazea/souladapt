class SincerityEngine:
    """
    The honesty layer of SoulAdapt.

    Converts memory retrieval distances (from SoulMemory.recall)
    into confidence scores, and decides how the AI should phrase
    what it "remembers".

    The golden rule: the AI NEVER invents.
    It calibrates its certainty to the real memory signal.
    Now bilingual: honest in English AND Spanish.
    """

    # Thresholds for the three honesty levels
    ASSERTIVE_THRESHOLD = 0.75      # strong match -> state it as fact
    HEDGED_THRESHOLD = 0.45         # weak match -> soften the phrase

    # Honest phrase templates per language
    PHRASES = {
        "en": {
            "hedged": "If I remember correctly: {content}",
            "admit": (
                "I don't have a clear memory of that, "
                "but it might be: {content}"
            ),
        },
        "es": {
            "hedged": "Si mal no recuerdo: {content}",
            "admit": "No recuerdo bien eso, pero quizás: {content}",
        },
    }

    def __init__(self, lang="en"):
        """
        Args:
            lang: 'en' or 'es' — language used by phrase().
                  Falls back to 'en' if unknown.
        """
        self.lang = lang if lang in self.PHRASES else "en"

    def confidence_from_distance(self, distance):
        """
        Convert a vector distance into a confidence score (0.0–1.0).

        Args:
            distance: The 'distance' value from SoulMemory.recall()
                      (0 = perfect match, ~2 = totally unrelated)

        Returns:
            float: confidence, clamped between 0.0 and 1.0
        """
        # distance 0 → confidence 1.0; distance >= 2 → confidence 0.0
        confidence = 1.0 - (distance / 2.0)
        return max(0.0, min(1.0, confidence))

    def honesty_level(self, confidence):
        """
        Decide how the AI should express a memory.

        Returns:
            'assertive' → confident:  "You had coffee with Ana."
            'hedged'    → unsure:     "If I remember correctly..."
            'admit'     → weak:       "I don't have a clear memory..."
        """
        if confidence >= self.ASSERTIVE_THRESHOLD:
            return "assertive"
        if confidence >= self.HEDGED_THRESHOLD:
            return "hedged"
        return "admit"

    def phrase(self, memory_content, confidence):
        """
        Wrap a memory in an honest sentence (in the chosen language),
        calibrated to how confident the memory actually is.
        """
        level = self.honesty_level(confidence)

        # Strong memory → say it as a fact, no wrapping
        if level == "assertive":
            return memory_content

        # Weaker memories → use the honest template for this language
        return self.PHRASES[self.lang][level].format(
            content=memory_content
        )

    def evaluate(self, recall_results):
        """
        Attach confidence + honesty level to SoulMemory recall results.

        Returns:
            List of dicts with content, confidence and honesty.
            If a result has no 'distance', it defaults to 2.0
            (confidence 0 → 'admit'): honest by default.
        """
        evaluated = []
        for r in recall_results:
            confidence = self.confidence_from_distance(
                r.get("distance", 2.0)
            )
            evaluated.append({
                "content": r["content"],
                "confidence": round(confidence, 2),
                "honesty": self.honesty_level(confidence)
            })
        return evaluated