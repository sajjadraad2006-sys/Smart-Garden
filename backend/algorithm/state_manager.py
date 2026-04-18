"""Algorithm state manager — persistent memory across 30-second decision cycles.

B-02 FIX: Without this, the algorithm has no memory between cycles. pH pumps
could fire every 30 seconds, misting could trigger on boot, etc.
"""
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("agrimaster.state")


@dataclass
class ActionRecord:
    """Record of a single actuator action."""
    target: str
    fired_at: float    # unix timestamp
    duration_sec: int = 0


class AlgorithmStateManager:
    """Thread-safe in-memory state for algorithm decisions.
    Tracks cooldowns, overrides, and daily counters."""

    def __init__(self):
        self._last_actions: dict[str, ActionRecord] = {}
        self._overrides: dict[str, float] = {}  # target → expiry unix ts
        self._daily_counters: dict[str, int] = {}
        self._daily_reset_day: int = 0

    def record_action(self, target: str, duration_sec: int = 0):
        """Record that an action was taken now."""
        self._last_actions[target] = ActionRecord(
            target=target,
            fired_at=time.time(),
            duration_sec=duration_sec
        )
        # Increment daily counter
        self._check_daily_reset()
        self._daily_counters[target] = self._daily_counters.get(target, 0) + 1

    def seconds_since_last(self, target: str) -> float:
        """Seconds since last action on target. Returns inf if never fired."""
        if target not in self._last_actions:
            return float('inf')
        return time.time() - self._last_actions[target].fired_at

    def hours_since_last(self, target: str) -> float:
        """Hours since last action on target."""
        return self.seconds_since_last(target) / 3600.0

    def is_overridden(self, target: str) -> bool:
        """Check if a manual override is active for target."""
        expiry = self._overrides.get(target, 0)
        return time.time() < expiry

    def set_override(self, target: str, duration_minutes: int):
        """Set a manual override for target (suppresses algorithm actions)."""
        self._overrides[target] = time.time() + (duration_minutes * 60)
        logger.info(f"[STATE] Override set for {target}: {duration_minutes} min")

    def clear_override(self, target: str):
        """Clear manual override for target."""
        self._overrides.pop(target, None)

    def get_daily_count(self, target: str) -> int:
        """Get how many times target has been activated today."""
        self._check_daily_reset()
        return self._daily_counters.get(target, 0)

    def _check_daily_reset(self):
        """Reset daily counters at midnight."""
        today = time.localtime().tm_yday
        if today != self._daily_reset_day:
            self._daily_counters.clear()
            self._daily_reset_day = today

    def persist_to_db(self, db):
        """Backup state to DB so it survives backend restart."""
        for target, record in self._last_actions.items():
            db.upsert_algorithm_state(target, record.fired_at)

    def restore_from_db(self, db):
        """Restore state after restart."""
        try:
            states = db.get_algorithm_states()
            for row in states:
                self._last_actions[row["target"]] = ActionRecord(
                    target=row["target"],
                    fired_at=row["last_fired_at"],
                    duration_sec=0
                )
            logger.info(f"[STATE] Restored {len(states)} action records from DB")
        except Exception as e:
            logger.warning(f"[STATE] Could not restore from DB: {e}")

    def get_summary(self) -> dict:
        """Return human-readable state summary."""
        return {
            target: {
                "last_fired": record.fired_at,
                "seconds_ago": round(time.time() - record.fired_at, 0),
                "duration": record.duration_sec
            }
            for target, record in self._last_actions.items()
        }
