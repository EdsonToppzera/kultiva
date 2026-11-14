import os


class Settings:
    """Configurações básicas e de banco de dados da aplicação."""

    PROJECT_NAME: str = "Kultiva API"
    VERSION: str = "0.1.0"
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@db:5432/kultiva_db",
    )


settings = Settings()
