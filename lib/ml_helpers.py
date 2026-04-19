"""
ml_helpers.py
Hybrid RobotiX — HybX Development System

Platform-agnostic ML helper functions for the HybX ML integration.

Provides a clean interface for:
  - ML platform authentication
  - Training data collection and upload
  - Model download and management
  - Model metadata parsing

The backend is swappable — the platform is determined by the board's
ml_platform config field. Adding support for a new ML platform means
adding a new backend here without touching any commands.

Currently supported platforms:
  - edge-impulse  — Edge Impulse Linux SDK

Usage in bin commands:
    from ml_helpers import get_backend, MLError

    backend = get_backend(board)   # raises MLError if not configured
    backend.upload_sample(data, label, sensor_type)
    backend.download_model(dest_path)
    backend.model_info()
    backend.list_models()
"""

import os
import json
import subprocess
import sys

# ── Exceptions ─────────────────────────────────────────────────────────────────


class MLError(Exception):
    """Raised when an ML platform operation fails."""
    pass


# ── ML project structure ───────────────────────────────────────────────────────

ML_DIR       = "ml"
DATA_DIR     = os.path.join(ML_DIR, "data")
MODELS_DIR   = os.path.join(ML_DIR, "models")
ML_YAML      = os.path.join(ML_DIR, "ml.yaml")
MODEL_FILE   = os.path.join(MODELS_DIR, "model.eim")

# ── Platform registry ──────────────────────────────────────────────────────────

SUPPORTED_PLATFORMS = [
    "edge-impulse",
]


def get_backend(board: dict):
    """
    Return the appropriate ML backend for the board's ml_platform config.
    Raises MLError if no ML config is present or platform is unsupported.
    """
    platform   = board.get("ml_platform", "").strip()
    api_key    = board.get("ml_api_key", "").strip()
    project_id = board.get("ml_project_id", "").strip()

    if not api_key:
        raise MLError(
            "No ML platform configured for this board.\n"
            "Use: board use <n>   then update board ML config."
        )

    if not platform:
        raise MLError("ml_platform not set in board config.")

    if platform not in SUPPORTED_PLATFORMS:
        raise MLError(
            "Unsupported ML platform: " + platform + "\n"
            "Supported platforms: " + ", ".join(SUPPORTED_PLATFORMS)
        )

    if platform == "edge-impulse":
        return EdgeImpulseBackend(api_key, project_id)

    raise MLError("No backend found for platform: " + platform)


# ── ml.yaml helpers ────────────────────────────────────────────────────────────


def load_ml_yaml(project_path: str) -> dict:
    """Load the ml/ml.yaml config for a project. Returns empty dict if not found."""
    path = os.path.join(project_path, ML_YAML)
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        # Simple key: value parser — no external yaml dependency
        result = {}
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
        return result


def save_ml_yaml(project_path: str, data: dict):
    """Write ml/ml.yaml for a project."""
    path = os.path.join(project_path, ML_YAML)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("# HybX ML project configuration\n")
        f.write("# Managed by HybX — edit with care\n\n")
        for key, value in data.items():
            f.write(key + ": " + str(value) + "\n")


def is_ml_project(project_path: str) -> bool:
    """Return True if the project has an ml/ directory."""
    return os.path.isdir(os.path.join(project_path, ML_DIR))


def get_model_path(project_path: str) -> str | None:
    """Return the path to the project's model file, or None if not present."""
    path = os.path.join(project_path, MODEL_FILE)
    return path if os.path.exists(path) else None


# ── Edge Impulse backend ───────────────────────────────────────────────────────


class EdgeImpulseBackend:
    """
    Edge Impulse ML platform backend.

    Uses the edge-impulse-linux CLI tools and Python SDK.
    All operations require the edge-impulse-linux package to be installed
    in the project's virtualenv or system Python.

    Install via: pip install edge-impulse-linux
    """

    def __init__(self, api_key: str, project_id: str):
        self.api_key    = api_key
        self.project_id = project_id

    def _check_cli(self, tool: str):
        """Raise MLError if a required CLI tool is not available."""
        result = subprocess.run(
            ["which", tool],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            raise MLError(
                tool + " not found.\n"
                "Install via: pip install edge-impulse-linux"
            )

    def upload_sample(self, data_path: str, label: str, sensor_type: str = "custom"):
        """
        Upload a training data sample to Edge Impulse.

        data_path   — path to the sample file (CSV, WAV, JPG, etc.)
        label       — classification label for this sample
        sensor_type — sensor type hint for Edge Impulse Studio
        """
        self._check_cli("edge-impulse-uploader")

        if not os.path.exists(data_path):
            raise MLError("Data file not found: " + data_path)

        result = subprocess.run(
            [
                "edge-impulse-uploader",
                "--api-key", self.api_key,
                "--label",   label,
                data_path,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise MLError("Upload failed: " + result.stderr.strip())

        return result.stdout.strip()

    def download_model(self, dest_path: str):
        """
        Download the latest trained model (.eim) from Edge Impulse.

        dest_path — full path where the model file will be saved
        """
        self._check_cli("edge-impulse-linux-runner")

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        result = subprocess.run(
            [
                "edge-impulse-linux-runner",
                "--api-key",  self.api_key,
                "--download", dest_path,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise MLError("Model download failed: " + result.stderr.strip())

        if not os.path.exists(dest_path):
            raise MLError("Model file not created after download.")

        return dest_path

    def model_info(self, model_path: str) -> dict:
        """
        Return metadata from a downloaded .eim model file.
        Parses the model's embedded metadata JSON.
        """
        if not os.path.exists(model_path):
            raise MLError("Model file not found: " + model_path)

        result = subprocess.run(
            [model_path, "--info"],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise MLError("Could not read model info: " + result.stderr.strip())

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"raw": result.stdout.strip()}

    def list_models(self) -> list[dict]:
        """
        List available trained model versions for the configured project.
        Returns a list of model dicts with version, created_at, and accuracy.
        """
        # Edge Impulse does not have a simple CLI for listing models —
        # this would require the REST API directly.
        # Placeholder for v1.5 implementation using requests + API key.
        raise MLError(
            "list_models not yet implemented for Edge Impulse.\n"
            "Use Edge Impulse Studio to view available models."
        )