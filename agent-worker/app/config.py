from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path


class WorkerSettings(BaseSettings):
    app_env: str = Field(default="development")

    # GitHub App
    github_app_id: str = Field(...)
    github_private_key_path: str = Field(default="./private-key.pem")

    # Database
    database_url: str = Field(...)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379")

    # AI
    anthropic_api_key: str = Field(...)

    # Worker
    concurrency: int = Field(default=2)
    mock_llm: bool = Field(default=False)

    # Encryption
    encryption_key: str = Field(...)

    @property
    def github_private_key(self) -> str:
        import os
        key_from_env = os.environ.get("GITHUB_PRIVATE_KEY")
        if key_from_env:
            return key_from_env.replace("\\n", "\n")
        key_path = Path(self.github_private_key_path)
        if not key_path.exists():
            raise FileNotFoundError(
            f"Private key not found at {key_path}"
        )
        return key_path.read_text()

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> WorkerSettings:
    return WorkerSettings()
