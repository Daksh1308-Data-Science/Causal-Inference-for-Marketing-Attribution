"""MySQL connection helper — credentials always come from .env (never hardcoded)."""
from __future__ import annotations

import pymysql
from sqlalchemy import create_engine

from src.config import load_env


def connect(autocommit: bool = False, client_flag: int = 0) -> pymysql.Connection:
    """Open a pymysql connection to the olist database using .env credentials.

    Defaults to autocommit=False so callers can wrap bulk loads in a single
    transaction (much faster for multi-thousand-row inserts). Pass
    ``client_flag`` (e.g. CLIENT.MULTI_STATEMENTS) when executing multi-statement
    SQL files.
    """
    env = load_env()
    return pymysql.connect(
        host=env.get("DB_HOST", "localhost"),
        port=int(env.get("DB_PORT", "3306")),
        user=env["DB_USER"],
        password=env["DB_PASSWORD"],
        database=env["DB_NAME"],
        charset="utf8mb4",
        autocommit=autocommit,
        connect_timeout=10,
        client_flag=client_flag,
    )


def engine():
    """SQLAlchemy engine (mysql+pymysql) for pandas.read_sql etc."""
    env = load_env()
    return create_engine(
        "mysql+pymysql://{user}:{password}@{host}:{port}/{db}?charset=utf8mb4".format(
            user=env["DB_USER"],
            password=env["DB_PASSWORD"],
            host=env.get("DB_HOST", "localhost"),
            port=int(env.get("DB_PORT", "3306")),
            db=env["DB_NAME"],
        ),
        pool_pre_ping=True,
    )