from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLOUDPILOT_", env_file=ROOT / ".env", extra="ignore"
    )

    database_path: Path = Path("data/local/cloudpilot.sqlite3")
    dataset_path: Path = Path("test-data")
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def resolved_database_path(self) -> Path:
        return ROOT / self.database_path

    @property
    def resolved_dataset_path(self) -> Path:
        return ROOT / self.dataset_path

