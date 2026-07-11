import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://logement:logement@localhost:5432/logement_db",
)

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )

if DATABASE_URL is None:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_engine(
    DATABASE_URL,
    poolclass=NullPool,
    connect_args={
        "connect_timeout": 10,
        # TCP keepalives so a connection that dies silently (WSL2 NAT drop,
        # wifi change, sleep/wake) is detected within ~30s instead of the
        # query hanging forever waiting on a socket that will never answer.
        "keepalives": 1,
        "keepalives_idle": 10,
        "keepalives_interval": 5,
        "keepalives_count": 3,
    },
)


# Supabase's connection pooler (Supavisor) drops the "options" startup
# parameter, so `-c lock_timeout=...` in connect_args is silently ignored.
# Setting these as regular statements right after connecting is what
# actually reaches the backend.
@event.listens_for(engine, "connect")
def _set_session_timeouts(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("SET lock_timeout = '30s'")
    cursor.execute("SET statement_timeout = '60s'")
    # Generous on purpose: pipeline functions hold a session-level advisory
    # lock across multi-minute Playwright scraping with no DB activity in
    # between, which is legitimately "idle in transaction", not dead. TCP
    # keepalives (below) are what catches genuinely dead connections fast;
    # this is only a last-resort net for a truly abandoned session.
    cursor.execute("SET idle_in_transaction_session_timeout = '30min'")
    cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    import src.storage.orm_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
