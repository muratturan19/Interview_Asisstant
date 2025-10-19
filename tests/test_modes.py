"""Tests covering dynamic mode configuration exposure."""
from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Iterable

import pytest

import configs

backend_module = import_module("backend.app")


@pytest.fixture()
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary configuration directory with a runtime mode."""

    config_dir = tmp_path / "configs"
    config_dir.mkdir()

    runtime_config = {
        "mode": "runtime",
        "title": "Runtime Mode",
        "description": "Dynamically added mode for testing.",
        "system_prompt": "You are a helpful interviewer.",
        "evaluation_prompt": "Evaluate clearly.",
        "questions": [
            {"part": "Warm-up", "prompts": ["Tell me about yourself."]}
        ],
        "criteria": [
            {"name": "Clarity", "description": "How clear was the response?"}
        ],
        "scale": {
            "label": "Sample Scale",
            "levels": [
                {"value": 1, "description": "Needs improvement"},
                {"value": 3, "description": "Strong"},
            ],
        },
        "evaluation": {
            "system_prompt": "Judge clarity and depth.",
            "overall_scale": "1-3",
            "criterion_template": "{\\n    \\\"clarity\\\": {\\\"score\\\": <number 1-3>, \\\"max_score\\\": 3}\\n}",
            "equivalent_template": "{\\n    \\\"cefr_level\\\": \\\"<A1/A2>\\\"\\n}",
            "question_max": 3,
            "extra_fields": "",
            "examples": "Example high and low responses.",
            "guidance": "Focus on structure and clarity.",
        },
    }

    (config_dir / "runtime.json").write_text(json.dumps(runtime_config), encoding="utf-8")

    return config_dir


def _install_manager(monkeypatch: pytest.MonkeyPatch, base_path: Path) -> None:
    """Replace the global config manager with one pointing to ``base_path``."""

    manager = configs.ConfigManager(base_path=base_path)
    monkeypatch.setattr(configs, "config_manager", manager)
    monkeypatch.setattr(backend_module, "config_manager", manager)
    backend_module.conversations.clear()


def test_create_evaluation_prompt_uses_config(monkeypatch: pytest.MonkeyPatch, temp_config_dir: Path) -> None:
    """The evaluation prompt should reflect data from the JSON configuration."""

    _install_manager(monkeypatch, temp_config_dir)

    system_prompt, user_prompt = backend_module.create_evaluation_prompt(
        "Sample transcript", "runtime"
    )

    assert "Judge clarity and depth." == system_prompt
    assert "1-3" in user_prompt
    assert "clarity" in user_prompt


def test_modes_endpoint_includes_runtime_mode(monkeypatch: pytest.MonkeyPatch, temp_config_dir: Path) -> None:
    """The /api/modes endpoint should surface dynamically added configurations."""

    _install_manager(monkeypatch, temp_config_dir)

    client = backend_module.app.test_client()
    response = client.get("/api/modes")
    assert response.status_code == 200

    payload = response.get_json()
    modes: Iterable[dict] = payload["modes"]

    mode_ids = {mode["mode"] for mode in modes}
    assert "runtime" in mode_ids
    assert payload["default_mode"] == "runtime"
    assert "runtime" in payload["evaluation_modes"]
