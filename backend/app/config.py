import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DATASET_PATH = BASE_DIR / "data" / "processed" / "application_portfolio_1000.csv"
DEFAULT_MODEL_PATH = BASE_DIR / "notebook" / "model.joblib"
DEFAULT_LABEL_ENCODER_PATH = BASE_DIR / "notebook" / "label_encoder.joblib"


def _read_csv_list(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or default


class Settings:
    def __init__(self) -> None:
        self.dataset_path = os.getenv("APP_DATASET_PATH", str(DEFAULT_DATASET_PATH))
        self.allow_origins = _read_csv_list(
            os.getenv("APP_ALLOW_ORIGINS"),
            ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],
        )
        self.log_level = os.getenv("APP_LOG_LEVEL", "INFO")
        self.recommendation_model_path = os.getenv("APP_RECOMMENDATION_MODEL_PATH", str(DEFAULT_MODEL_PATH))
        self.recommendation_label_encoder_path = os.getenv(
            "APP_RECOMMENDATION_LABEL_ENCODER_PATH",
            str(DEFAULT_LABEL_ENCODER_PATH),
        )
        self.wave_model_path = os.getenv("APP_WAVE_MODEL_PATH")
        self.copilot_model_path = os.getenv("APP_COPILOT_MODEL_PATH")


settings = Settings()
