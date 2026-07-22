from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from pathlib import Path

class Settings(BaseSettings):

    app_env: str = Field(default="development")
    app_port: int = Field(default=8000)
    secret_key: str = Field(...)

    github_app_id: str = Field(...)
    github_app_client_id: str = Field(...)
    github_app_client_secret: str = Field(...)
    github_webhook_secret: str = Field(...)
    github_private_key_path: str = Field(default="./private-key.pem")

    database_url: str = Field(...)

    frontend_origin: str = Field(default="http://localhost:3000")

    redis_url: str = Field(default="redis://localhost:6379")

    anthropic_api_key: str = Field(...)

    mock_llm: bool = Field(default=True)
    mock_github: bool = Field(default=False)

    # Cost guard: max reviews per installation per UTC day. Every review is
    # real LLM spend, so a public install must not be able to run unbounded.
    # 0 disables the cap (dev/local only — never in production).
    max_reviews_per_installation_per_day: int = Field(default=25)

    encryption_key: str = Field(...)

    @property
    def github_private_key(self) -> str:
        import os
    # Try environment variable first (production/Railway)
        key_from_env = os.environ.get("GITHUB_PRIVATE_KEY")
        if key_from_env:
        # Replace literal \n with actual newlines
           return key_from_env.replace("\\n", "\n")
    # Fall back to file (local development)
        key_path = Path(self.github_private_key_path)
        if not key_path.exists():
            raise FileNotFoundError(
                f"GitHub private key not found at {key_path}. "
                f"Set GITHUB_PRIVATE_KEY env var or copy .pem file."
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