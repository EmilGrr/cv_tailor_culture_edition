import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    model_id: str
    region: str
    tectonic: str | None

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "sources"

    @property
    def applications_dir(self) -> Path:
        return self.data_dir / "applications"


def _find_tectonic() -> str | None:
    explicit = os.environ.get("TECTONIC_PATH")
    if explicit and Path(explicit).exists():
        return explicit
    local = ROOT / "tools" / "tectonic" / "tectonic.exe"
    if local.exists():
        return str(local)
    return shutil.which("tectonic")


def get_settings() -> Settings:
    return Settings(
        data_dir=Path(os.environ.get("CV_DATA_DIR", ROOT / "data")),
        model_id=os.environ.get("BEDROCK_MODEL_ID", "eu.anthropic.claude-sonnet-5-5"),
        region=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-north-1",
        tectonic=_find_tectonic(),
    )


def fake_llm_enabled() -> bool:
    return os.environ.get("CV_FAKE_LLM") == "1"


def demo_data_enabled() -> bool:
    return os.environ.get("CV_DEMO") == "1"


def has_aws_credentials() -> bool:
    if os.environ.get("AWS_BEARER_TOKEN_BEDROCK"):
        return True
    return bool(os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"))
