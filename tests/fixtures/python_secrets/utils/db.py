"""Database connection helper for the fixture app."""
DB_USER = "admin"
DB_PASSWORD = "SuperSecretP@ssw0rd123"


def get_connection_string() -> str:
    return f"postgresql://{DB_USER}:{DB_PASSWORD}@localhost:5432/fixture_db"
