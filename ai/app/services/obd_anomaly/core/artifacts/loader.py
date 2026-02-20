from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any, Dict


def load_artifact_json(path: Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return default or {}
    try:
        # Windows 편집기/PowerShell 저장 시 UTF-8 BOM이 들어갈 수 있어 sig 우선 처리.
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default or {}


def load_artifact_pickle(path: Path) -> Any:
    if not path.exists():
        return None
    # IF model is exported with joblib.dump in offline training script.
    # Try joblib first, then fallback to raw pickle for backward compatibility.
    try:
        import joblib

        return joblib.load(path)
    except Exception:
        pass
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None

