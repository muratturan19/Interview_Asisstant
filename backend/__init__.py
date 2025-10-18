"""Backend package exposing the Flask application factory."""

from .app import (
    MAX_QA_PAIRS,
    app,
    chat,
    create_evaluation_prompt,
    get_first_question,
    get_modes,
    validate_evaluation,
    _sanitize_evaluation_text,
)

__all__ = [
    "app",
    "chat",
    "create_evaluation_prompt",
    "get_first_question",
    "get_modes",
    "validate_evaluation",
    "_sanitize_evaluation_text",
    "MAX_QA_PAIRS",
]

