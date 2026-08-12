import importlib.util
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def passthrough_decorator(function=None, **_kwargs):
    if function is not None:
        return function
    return lambda wrapped: wrapped


def load_database_module(relative_path, module_name, environment):
    connect = Mock(return_value=object())

    psycopg2 = ModuleType("psycopg2")
    psycopg2.connect = connect

    streamlit = ModuleType("streamlit")
    streamlit.cache_resource = passthrough_decorator
    streamlit.cache_data = passthrough_decorator

    sqlalchemy = ModuleType("sqlalchemy")
    sqlalchemy.create_engine = Mock()
    sqlalchemy.text = lambda query: query

    dotenv = ModuleType("dotenv")
    dotenv.load_dotenv = Mock()

    spec = importlib.util.spec_from_file_location(module_name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)

    with (
        patch.dict(os.environ, environment, clear=True),
        patch.dict(
            sys.modules,
            {
                "psycopg2": psycopg2,
                "streamlit": streamlit,
                "sqlalchemy": sqlalchemy,
                "dotenv": dotenv,
            },
        ),
    ):
        spec.loader.exec_module(module)
        module.get_conn()

    return connect


class StreamlitDatabaseConnectionTests(unittest.TestCase):
    def test_prefers_neon_database_url(self):
        connect = load_database_module(
            "streamlit-app/db.py",
            "streamlit_db_neon_test",
            {
                "DATABASE_URL": "postgresql://neon.example/value_stream",
                "K_SERVICE": "value-stream",
                "CLOUD_SQL_CONNECTION_NAME": "project:region:instance",
            },
        )

        connect.assert_called_once_with(
            "postgresql://neon.example/value_stream",
            sslmode="require",
        )

    def test_keeps_cloud_sql_socket_as_fallback(self):
        connect = load_database_module(
            "streamlit-app/db.py",
            "streamlit_db_cloud_sql_test",
            {
                "K_SERVICE": "value-stream",
                "CLOUD_SQL_CONNECTION_NAME": "project:region:instance",
                "DB_NAME": "postgres",
                "DB_USER": "postgres",
                "DB_PASSWORD": "secret",
            },
        )

        connect.assert_called_once_with(
            host="/cloudsql/project:region:instance",
            database="postgres",
            user="postgres",
            password="secret",
        )


class ScraperDatabaseConnectionTests(unittest.TestCase):
    def test_prefers_neon_database_url(self):
        connect = load_database_module(
            "scraper/db.py",
            "scraper_db_neon_test",
            {
                "DATABASE_URL": "postgresql://neon.example/value_stream",
                "CLOUD_SQL_CONNECTION_NAME": "project:region:instance",
            },
        )

        connect.assert_called_once_with(
            "postgresql://neon.example/value_stream",
            sslmode="require",
        )

    def test_keeps_cloud_sql_socket_as_fallback(self):
        connect = load_database_module(
            "scraper/db.py",
            "scraper_db_cloud_sql_test",
            {
                "CLOUD_SQL_CONNECTION_NAME": "project:region:instance",
                "DB_NAME": "postgres",
                "DB_USER": "postgres",
                "DB_PASSWORD": "secret",
            },
        )

        connect.assert_called_once_with(
            host="/cloudsql/project:region:instance",
            database="postgres",
            user="postgres",
            password="secret",
        )


if __name__ == "__main__":
    unittest.main()
