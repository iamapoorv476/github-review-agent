from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path


class Settings(BaseSettings):
    # Application
    app_env: str = Field(default="development")
    app_port: int = Field(default=8000)
    secret_key: str = Field(...)

    # GitHub App
    github_app_id: str = Field(...)
    github_app_client_id: str = Field(...)
    github_app_client_secret: str = Field(...)
    github_webhook_secret: str = Field(...)
    github_private_key_path: str = Field(default="./private-key.pem")

    # Database
    database_url: str = Field(...)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379")

    # AI
    anthropic_api_key: str = Field(...)

    # Feature flags
    mock_llm: bool = Field(default=True)
    mock_github: bool = Field(default=False)

    # Encryption
    encryption_key: str = Field(...)

    @property
    def github_private_key(self) -> str:
        key_path = Path(self.github_private_key_path)
        if not key_path.exists():
            raise FileNotFoundError(
                f"GitHub private key not found at {key_path}. "
                f"Copy your .pem file to {key_path}"
            )
        return key_path.read_text()

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()