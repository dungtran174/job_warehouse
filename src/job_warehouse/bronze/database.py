"""Explicit warehouse connection settings; credentials never enter reports."""

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from job_warehouse.history.contract import HistoryProfileError

RegistryConnection = psycopg.Connection[dict[str, Any]]


def connection_settings(environ: Mapping[str, str] | None = None) -> dict[str, str | int]:
    env = os.environ if environ is None else environ
    keys = {"host": "WAREHOUSE_DB_HOST", "dbname": "WAREHOUSE_DB_NAME", "user": "WAREHOUSE_DB_USER"}
    settings: dict[str, str | int] = {}
    for key, name in keys.items():
        value = env.get(name, "").strip()
        if not value:
            raise HistoryProfileError(f"Missing required setting {name}")
        settings[key] = value
    try:
        port = int(env.get("WAREHOUSE_DB_PORT", "5432"))
    except ValueError:
        raise HistoryProfileError("WAREHOUSE_DB_PORT must be an integer") from None
    if not 1 <= port <= 65535:
        raise HistoryProfileError("WAREHOUSE_DB_PORT must be between 1 and 65535")
    password = env.get("WAREHOUSE_DB_PASSWORD", "")
    password_file = env.get("WAREHOUSE_DB_PASSWORD_FILE", "")
    if password and password_file:
        raise HistoryProfileError("Configure password or password file, not both")
    if password_file:
        try:
            password = Path(password_file).read_text(encoding="utf-8").rstrip("\r\n")
        except OSError:
            raise HistoryProfileError("Cannot read WAREHOUSE_DB_PASSWORD_FILE") from None
    if not password:
        raise HistoryProfileError("Warehouse database password is required")
    settings.update(password=password, port=port, connect_timeout=10)
    return settings


def connect_registry() -> RegistryConnection:
    settings = connection_settings()
    return psycopg.connect(
        host=str(settings["host"]),
        port=int(settings["port"]),
        dbname=str(settings["dbname"]),
        user=str(settings["user"]),
        password=str(settings["password"]),
        connect_timeout=int(settings["connect_timeout"]),
        autocommit=True,
        row_factory=dict_row,
    )
