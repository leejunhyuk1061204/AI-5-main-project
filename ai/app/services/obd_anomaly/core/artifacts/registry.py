from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


class ArtifactRegistry:
    """
    Resolves artifact roots with backward-compatible fallback.
    Preferred:
      - .../models/schemas/v1
      - .../models/artifacts/v1
    Legacy:
      - .../artifacts
    """

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        env_dir = os.getenv("OBD_ANOMALY_ARTIFACT_DIR")
        if env_dir:
            self.artifact_root = Path(env_dir)
        else:
            preferred = self.base_dir / "models" / "artifacts" / "v1"
            self.artifact_root = preferred if preferred.exists() else self.base_dir / "artifacts"

        preferred_schema = self.base_dir / "models" / "schemas" / "v1"
        self.schema_root = preferred_schema if preferred_schema.exists() else self.artifact_root

    def paths(self) -> Dict[str, Path]:
        return {
            "schema_core": self.schema_root / "schema_core.json",
            "threshold_policy": self.artifact_root / "threshold_policy.json",
            "scaler": self.artifact_root / "scaler.json",
            "iforest": self.artifact_root / "iforest.pkl",
            "lstm_ae": self.artifact_root / "lstm_ae.pt",
        }

