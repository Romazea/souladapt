import sqlite3
import time


class SQLiteBackend:
    """Storage backend for SoulAdapt (standard library only, no deps)"""

    def __init__(self, db_path: str = "souladapt.db"):
        self.db_path = db_path
        self.db = sqlite3.connect(db_path)
        self._create_tables()

    def _create_tables(self):
        """Create tables if they don't exist"""
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                weight REAL DEFAULT 1.0,
                created_at INTEGER,
                last_seen INTEGER,
                times_seen INTEGER DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_obs_category
                ON observations(category);
        """)
        self.db.commit()

    def add_observation(self, content, category="general", weight=1.0):
        """
        Register an observation about the user.

        If the same observation (content + category) already exists,
        reinforce it instead of duplicating: the more it is seen,
        the stronger it gets (max weight 2.0).

        Args:
            content: What was learned (e.g. "prefiere respuestas cortas")
            category: 'style', 'sensitive', 'interests' or 'general'
            weight: Initial strength of the observation

        Returns:
            The observation ID
        """
        now = int(time.time())
        existing = self.db.execute(
            "SELECT id FROM observations "
            "WHERE content = ? AND category = ?",
            (content, category)
        ).fetchone()

        if existing:
            # Reinforce: seen again → slightly stronger (max 2.0)
            self.db.execute(
                "UPDATE observations "
                "SET times_seen = times_seen + 1, "
                "    last_seen = ?, "
                "    weight = MIN(weight + 0.1, 2.0) "
                "WHERE id = ?",
                (now, existing[0])
            )
            self.db.commit()
            return existing[0]

        cursor = self.db.execute(
            "INSERT INTO observations "
            "(content, category, weight, created_at, last_seen) "
            "VALUES (?, ?, ?, ?, ?)",
            (content, category, weight, now, now)
        )
        self.db.commit()
        return cursor.lastrowid

    def get_observations(self, category=None):
        """
        Get observations, strongest first.
        Optionally filtered by category.
        """
        if category is None:
            rows = self.db.execute(
                "SELECT id, content, category, weight, times_seen, "
                "last_seen FROM observations ORDER BY weight DESC"
            ).fetchall()
        else:
            rows = self.db.execute(
                "SELECT id, content, category, weight, times_seen, "
                "last_seen FROM observations WHERE category = ? "
                "ORDER BY weight DESC",
                (category,)
            ).fetchall()
        return [
            {
                "id": r[0],
                "content": r[1],
                "category": r[2],
                "weight": r[3],
                "times_seen": r[4],
                "last_seen": r[5]
            }
            for r in rows
        ]

    def delete_observation(self, observation_id):
        """Delete an observation by id"""
        self.db.execute(
            "DELETE FROM observations WHERE id = ?", (observation_id,)
        )
        self.db.commit()

    def update_weight(self, observation_id, new_weight):
        """Set a new weight for an observation"""
        self.db.execute(
            "UPDATE observations SET weight = ? WHERE id = ?",
            (new_weight, observation_id)
        )
        self.db.commit()

    def clear(self):
        """Delete ALL observations (fresh start)"""
        self.db.execute("DELETE FROM observations")
        self.db.commit()

    def close(self):
        """Close the database connection"""
        self.db.close()