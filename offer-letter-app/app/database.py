from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def migrate_sqlite_schema(engine):
    if engine.dialect.name != "sqlite":
        return
    with engine.begin() as connection:
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("offer_letters")
        }
        if "candidate_email" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE offer_letters "
                    "ADD COLUMN candidate_email VARCHAR(254) NOT NULL DEFAULT ''"
                )
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
