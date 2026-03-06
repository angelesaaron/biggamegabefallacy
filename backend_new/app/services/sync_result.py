from dataclasses import dataclass, field


@dataclass
class SyncResult:
    """
    Uniform return type for all pipeline services.

    n_written  — new rows inserted
    n_updated  — existing rows updated (UPSERT hit a conflict)
    n_skipped  — rows intentionally ignored (e.g. player not in DB)
    n_failed   — rows where an error occurred
    events     — human-readable strings for data quality issues
    """
    n_written: int = 0
    n_updated: int = 0
    n_skipped: int = 0
    n_failed: int = 0
    events: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.n_written + self.n_updated + self.n_skipped + self.n_failed

    def add_event(self, msg: str) -> None:
        self.events.append(msg)

    def merge(self, other: "SyncResult") -> None:
        """Accumulate another result into this one (for batch loops)."""
        self.n_written += other.n_written
        self.n_updated += other.n_updated
        self.n_skipped += other.n_skipped
        self.n_failed += other.n_failed
        self.events.extend(other.events)
