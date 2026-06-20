from datetime import datetime, timezone
from sqlalchemy import DateTime, TypeDecorator

class UTCDateTime(TypeDecorator):
    """
    Ensures datetimes are always timezone-aware (UTC) when entering or 
    leaving the database, regardless of the underlying dialect (e.g., SQLite).
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                # SQLite returns naive datetimes; we explicitly tag them as UTC
                value = value.replace(tzinfo=timezone.utc)
            else:
                value = value.astimezone(timezone.utc)
        return value