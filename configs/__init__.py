"""Configuration management utilities for interview modes."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class ConfigManager:
    """Loads and exposes configuration data for interview modes.

    The configuration files are stored as JSON documents inside the
    ``configs`` package. Each file represents a different interview
    mode (e.g. CEFR, IELTS) and contains prompts, evaluation criteria and
    grading scales that will be used by the backend.
    """

    def __init__(self, base_path: Optional[Path] = None) -> None:
        self._base_path = Path(base_path) if base_path else Path(__file__).resolve().parent
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._config_files = self._discover_config_files()

    def _discover_config_files(self) -> Dict[str, Path]:
        files: Dict[str, Path] = {}
        for path in self._base_path.glob("*.json"):
            files[path.stem.lower()] = path
        if not files:
            raise FileNotFoundError(
                f"No configuration files were found in {self._base_path}"
            )
        return files

    def _load_config(self, mode: str) -> Dict[str, Any]:
        key = mode.lower()
        if key not in self._cache:
            try:
                config_path = self._config_files[key]
            except KeyError as exc:  # pragma: no cover - defensive branch
                available = ", ".join(sorted(self._config_files))
                raise ValueError(
                    f"Unknown interview mode '{mode}'. Available modes: {available}"
                ) from exc

            with config_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
            self._cache[key] = data
        return self._cache[key]

    def has_mode(self, mode: str) -> bool:
        """Return whether the requested mode exists."""

        return mode.lower() in self._config_files

    def get_config(self, mode: str) -> Dict[str, Any]:
        """Return the raw configuration dictionary for a mode."""

        return self._load_config(mode)

    def available_modes(self) -> Iterable[str]:
        """Return the available configuration modes."""

        return sorted(self._config_files.keys())

    def get_description(self, mode: str) -> str:
        """Return the mode description."""

        config = self._load_config(mode)
        description = config.get("description")
        if not isinstance(description, str):
            raise ValueError(f"Mode '{mode}' does not define a valid description.")
        return description

    def get_system_prompt(self, mode: str) -> str:
        """Return the system prompt for a given mode."""

        config = self._load_config(mode)
        prompt = config.get("system_prompt")
        if not isinstance(prompt, str):
            raise ValueError(f"Mode '{mode}' does not define a valid system prompt.")
        return prompt

    def get_evaluation_prompt(self, mode: str) -> str:
        """Return the evaluation prompt for a given mode."""

        config = self._load_config(mode)
        prompt = config.get("evaluation_prompt")
        if not isinstance(prompt, str):
            raise ValueError(f"Mode '{mode}' does not define a valid evaluation prompt.")
        return prompt

    def has_evaluation_config(self, mode: str) -> bool:
        """Return whether a mode defines evaluation metadata."""

        config = self._load_config(mode)
        evaluation = config.get("evaluation")
        return isinstance(evaluation, dict) and bool(evaluation)

    def get_evaluation_config(self, mode: str) -> Dict[str, Any]:
        """Return structured evaluation metadata for the requested mode."""

        config = self._load_config(mode)
        evaluation = config.get("evaluation")
        if not isinstance(evaluation, dict):
            raise ValueError(f"Mode '{mode}' does not provide evaluation metadata.")

        required_fields = {
            "system_prompt": str,
            "overall_scale": str,
            "criterion_template": str,
            "equivalent_template": str,
            "question_max": (int, float),
            "examples": str,
            "guidance": str,
        }

        result: Dict[str, Any] = {}
        for field, expected_type in required_fields.items():
            value = evaluation.get(field)
            if not isinstance(value, expected_type):
                raise ValueError(
                    f"Mode '{mode}' is missing required evaluation field '{field}'."
                )
            result[field] = value

        result["question_max"] = int(result["question_max"])

        extra_fields = evaluation.get("extra_fields", "")
        if not isinstance(extra_fields, str):
            raise ValueError(
                f"Mode '{mode}' must define 'extra_fields' as a string if provided."
            )
        result["extra_fields"] = extra_fields

        return result

    def get_criteria(self, mode: str) -> List[Dict[str, Any]]:
        """Return the evaluation criteria for the requested mode."""

        config = self._load_config(mode)
        criteria = config.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            raise ValueError(f"Mode '{mode}' does not define evaluation criteria.")
        return criteria

    def get_scale(self, mode: str) -> Dict[str, Any]:
        """Return the evaluation scale definition for the requested mode."""

        config = self._load_config(mode)
        scale = config.get("scale")
        if not isinstance(scale, dict) or not scale:
            raise ValueError(f"Mode '{mode}' does not define an evaluation scale.")
        return scale

    def get_random_question(self, mode: str) -> Dict[str, Any]:
        """Return a random question prompt for the given interview mode."""

        config = self._load_config(mode)
        question_sets = config.get("questions")
        if not isinstance(question_sets, list) or not question_sets:
            raise ValueError(f"Mode '{mode}' does not provide any questions.")

        selected_part = random.choice(question_sets)
        prompts = selected_part.get("prompts")
        if not isinstance(prompts, list) or not prompts:
            raise ValueError(
                f"Mode '{mode}' contains a question part without prompts: {selected_part!r}"
            )

        selected_prompt = random.choice(prompts)
        return {
            "part": selected_part.get("part", ""),
            "prompt": selected_prompt,
        }

    def serialise_mode(self, mode: str) -> Dict[str, Any]:
        """Return a JSON-ready summary for the requested mode."""

        config = self._load_config(mode)
        description = self.get_description(mode)
        criteria = self.get_criteria(mode)
        scale = self.get_scale(mode)
        title = config.get("title")
        evaluation_available = self.has_evaluation_config(mode)

        payload: Dict[str, Any] = {
            "mode": mode,
            "description": description,
            "criteria": criteria,
            "scale": scale,
            "evaluation_available": evaluation_available,
        }

        if isinstance(title, str) and title.strip():
            payload["title"] = title

        return payload


config_manager = ConfigManager()

__all__ = ["ConfigManager", "config_manager"]
