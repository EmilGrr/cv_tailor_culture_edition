import json
import re
import uuid
from pathlib import Path

from .config import get_settings


def _path(app_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{8}", app_id):
        raise KeyError(app_id)
    return get_settings().applications_dir / f"{app_id}.json"


def _write(application: dict) -> None:
    _path(application["id"]).write_text(
        json.dumps(application, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def create_application(data: dict) -> dict:
    get_settings().applications_dir.mkdir(parents=True, exist_ok=True)
    application = {"id": uuid.uuid4().hex[:8], **data}
    _write(application)
    return application


def get_application(app_id: str) -> dict:
    path = _path(app_id)
    if not path.exists():
        raise KeyError(app_id)
    application = json.loads(path.read_text(encoding="utf-8"))
    # The "modern" template was replaced by "fun".
    if application.get("template") == "modern":
        application["template"] = "fun"
    return application


def update_application(app_id: str, changes: dict) -> dict:
    application = get_application(app_id)
    application.update(changes)
    _write(application)
    return application


def list_applications() -> list[dict]:
    directory = get_settings().applications_dir
    if not directory.exists():
        return []
    items = []
    for path in directory.glob("*.json"):
        a = json.loads(path.read_text(encoding="utf-8"))
        items.append({"id": a["id"], "title": a.get("title", ""), "template": a.get("template", "")})
    return sorted(items, key=lambda a: a["title"].lower())


def delete_application(app_id: str) -> None:
    path = _path(app_id)
    if not path.exists():
        raise KeyError(app_id)
    path.unlink()
