from sqlalchemy import Column, String, Integer, DateTime, Text, func, Index
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class JobRun(Base):
    __tablename__ = "job_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(50), nullable=False, index=True)  # 'odds_fetch', 'model_run', 'results_sync'
    season_year = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default='running')  # 'running', 'completed', 'failed'

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))

    error_message = Column(Text)
    job_metadata = Column(JSONB)  # Store additional context (renamed from 'metadata' to avoid SQLAlchemy conflict)

    __table_args__ = (
        Index('ix_job_runs_type_week', 'job_type', 'season_year', 'week'),
    )

    def __repr__(self):
        return f"<JobRun {self.job_type} {self.season_year}-W{self.week} [{self.status}]>"
