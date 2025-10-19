"""Flask application for the Interview Assistant backend."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import anthropic
from flask import Flask, jsonify, request
from flask_cors import CORS

from configs import config_manager


# ---------------------------------------------------------------------------
# Mode configuration used to build structured evaluation prompts.
# ---------------------------------------------------------------------------

LAST_MODE_KEY = "LAST_EVALUATION_MODE"


def _all_modes() -> tuple[str, ...]:
    """Return all configured interview modes."""

    return tuple(config_manager.available_modes())


def _evaluation_modes() -> tuple[str, ...]:
    """Return modes that provide evaluation metadata."""

    return tuple(
        mode for mode in _all_modes() if config_manager.has_evaluation_config(mode)
    )


def _default_mode() -> str:
    """Return the preferred default interview mode."""

    evaluation_modes = _evaluation_modes()
    if 'toefl' in evaluation_modes:
        return 'toefl'
    if evaluation_modes:
        return evaluation_modes[0]

    modes = _all_modes()
    if not modes:  # pragma: no cover - defensive fallback
        raise RuntimeError('No interview modes are available.')
    return modes[0]


def _normalize_mode(mode: str) -> str:
    """Return a valid mode, falling back to the default if needed."""

    candidate = (mode or '').lower()
    if config_manager.has_mode(candidate):
        return candidate
    return _default_mode()


def _normalize_evaluation_mode(mode: str) -> str:
    """Return an evaluation-ready mode, falling back to the default."""

    candidate = (mode or '').lower()
    if config_manager.has_evaluation_config(candidate):
        return candidate
    return _default_mode()


ENV_KEY_NAME = "ANTHROPIC_API_KEY"
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

MAX_QA_PAIRS = 5
FENCE_LABEL_PATTERN = r"[a-z0-9_+\-]*"


Conversations = Dict[Tuple[str, str], Dict[str, Any]]
conversations: Conversations = {}

app = Flask(__name__)
CORS(app)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt helpers
# ---------------------------------------------------------------------------


def create_evaluation_prompt(transcript: str, mode: str) -> tuple[str, str]:
    """Create Anthropic system and user prompts for the requested evaluation mode."""

    mode_key = _normalize_evaluation_mode(mode)
    config = config_manager.get_evaluation_config(mode_key)

    evaluation_directive = config_manager.get_evaluation_prompt(mode_key)

    system_prompt = config["system_prompt"]
    overall_scale = config["overall_scale"]
    criterion_structure = config["criterion_template"]
    equivalent_structure = config["equivalent_template"]
    question_max = config["question_max"]
    examples = config["examples"]
    guidance = config["guidance"]
    extra_fields = config["extra_fields"]

    user_prompt = f"""{evaluation_directive}

INTERVIEW TRANSCRIPT:
{transcript}

GENERAL INSTRUCTIONS:
1. Read the entire transcript carefully.
2. Evaluate the candidate using the mode-specific rubric.
3. Provide numeric scores for every criterion and question.
4. Cite direct evidence from the transcript when explaining scores.
5. Offer actionable, encouraging feedback in professional English.

MODE-SPECIFIC GUIDANCE:
{guidance}

REFERENCE EXAMPLES FOR CALIBRATION:
{examples}

Return ONLY valid JSON in this format:
{{
    "mode": "{mode_key}",
    "overall_score": <number>,
    "overall_scale": "{overall_scale}",
    "criterion_scores": {criterion_structure},
    "cefr_level": "<A1/A2/B1/B2/C1/C2>",
    "equivalent_scores": {equivalent_structure},
    "question_breakdown": [
        {{
            "question_number": 1,
            "score": <number>,
            "max_score": {question_max},
            "feedback": "Specific feedback referencing the transcript"
        }}
    ],
    "strengths": ["strength1", "strength2", "strength3"],
    "improvements": ["area1", "area2", "area3"],
    "detailed_feedback": "Comprehensive paragraph summarising performance",
    "specific_examples": {{
        "good": ["quoted or paraphrased example 1", "example 2"],
        "needs_work": ["quoted or paraphrased example 1", "example 2"]
    }}{extra_fields}
}}
"""

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Environment & persistence helpers
# ---------------------------------------------------------------------------


def _load_env_file() -> dict:
    """Load key-value pairs from the .env file if it exists."""

    if not ENV_PATH.exists():
        return {}

    data: Dict[str, str] = {}
    with ENV_PATH.open("r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip()
    return data


def _write_env_file(values: Dict[str, str]) -> None:
    """Persist key-value pairs to the .env file."""

    with ENV_PATH.open("w", encoding="utf-8") as env_file:
        for key, value in values.items():
            env_file.write(f"{key}={value}\n")


def _get_stored_api_key() -> str | None:
    """Return the Anthropic API key from the environment or .env file."""

    env_key = os.environ.get(ENV_KEY_NAME)
    if env_key:
        return env_key

    data = _load_env_file()
    api_key = data.get(ENV_KEY_NAME)
    if api_key:
        os.environ[ENV_KEY_NAME] = api_key
    return api_key


def _save_api_key(api_key: str) -> None:
    """Persist the API key in memory and the .env file."""

    data = _load_env_file()
    data[ENV_KEY_NAME] = api_key
    _write_env_file(data)
    os.environ[ENV_KEY_NAME] = api_key


def _get_last_mode(default: str | None = None) -> str:
    """Return the most recently used evaluation mode."""

    fallback = (default or _default_mode()).lower()
    data = _load_env_file()
    stored = (data.get(LAST_MODE_KEY) or "").lower()
    if stored and config_manager.has_evaluation_config(stored):
        return stored
    return fallback


def _save_last_mode(mode: str) -> None:
    """Persist the last used evaluation mode in the .env file."""

    candidate = (mode or "").lower()
    if not config_manager.has_evaluation_config(candidate):
        return
    data = _load_env_file()
    data[LAST_MODE_KEY] = candidate
    _write_env_file(data)


def _test_api_key(api_key: str) -> None:
    """Perform a lightweight request to validate the Anthropic API key."""

    client = anthropic.Anthropic(api_key=api_key)
    client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}],
    )


# ---------------------------------------------------------------------------
# Response sanitation & validation
# ---------------------------------------------------------------------------


def _sanitize_evaluation_text(text: str) -> str:
    """Normalize Claude's response so it can be parsed as JSON."""

    if not isinstance(text, str):
        return text

    sanitized = text.strip()

    if not sanitized:
        return sanitized

    for fence in ("```", "~~~"):
        prefix_re = re.compile(
            rf"^{re.escape(fence)}{FENCE_LABEL_PATTERN}\s*",
            re.IGNORECASE,
        )
        sanitized = prefix_re.sub("", sanitized, count=1)

        suffix_re = re.compile(rf"\s*{re.escape(fence)}$", re.IGNORECASE)
        sanitized = suffix_re.sub("", sanitized, count=1)

    return sanitized.strip()


def validate_evaluation(payload: Any) -> Dict[str, Any]:
    """Validate and normalise the evaluation payload returned by Claude."""

    if not isinstance(payload, dict):
        raise ValueError("Claude evaluation payload must be a JSON object")

    result = dict(payload)

    if "mode" in result and result["mode"]:
        if not isinstance(result["mode"], str):
            raise ValueError("Evaluation mode must be a string")
        result["mode"] = result["mode"].lower()

    def _ensure_dict(key: str) -> Dict[str, Any]:
        value = result.get(key)
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise ValueError(f"Field '{key}' must be an object")
        result[key] = value
        return value

    def _ensure_list(key: str) -> List[Any]:
        value = result.get(key)
        if value is None:
            value = []
        if not isinstance(value, list):
            raise ValueError(f"Field '{key}' must be a list")
        result[key] = value
        return value

    _ensure_dict("criterion_scores")
    _ensure_dict("equivalent_scores")
    question_breakdown = _ensure_list("question_breakdown")
    strengths = _ensure_list("strengths")
    improvements = _ensure_list("improvements")

    result["question_breakdown"] = [
        item for item in question_breakdown if isinstance(item, dict)
    ]
    result["strengths"] = [
        entry for entry in strengths if isinstance(entry, str) and entry.strip()
    ]
    result["improvements"] = [
        entry for entry in improvements if isinstance(entry, str) and entry.strip()
    ]

    examples = result.get("specific_examples")
    if examples is None:
        examples = {}
    if not isinstance(examples, dict):
        raise ValueError("Field 'specific_examples' must be an object")

    good_examples = examples.get("good") or []
    needs_work_examples = examples.get("needs_work") or []

    if not isinstance(good_examples, list) or not isinstance(needs_work_examples, list):
        raise ValueError("Example lists must be arrays")

    examples["good"] = [
        entry for entry in good_examples if isinstance(entry, str) and entry.strip()
    ]
    examples["needs_work"] = [
        entry
        for entry in needs_work_examples
        if isinstance(entry, str) and entry.strip()
    ]
    result["specific_examples"] = examples

    detailed_feedback = result.get("detailed_feedback")
    if detailed_feedback is not None and not isinstance(detailed_feedback, str):
        raise ValueError("Field 'detailed_feedback' must be a string if provided")

    return result


# ---------------------------------------------------------------------------
# Conversation helpers
# ---------------------------------------------------------------------------


def _conversation_key(session_id: str, mode: str) -> Tuple[str, str]:
    return session_id, mode


def _reset_conversation(session_id: str, mode: str) -> Dict[str, Any]:
    key = _conversation_key(session_id, mode)
    conversations[key] = {
        "mode": mode,
        "system_prompt": config_manager.get_system_prompt(mode),
        "history": [],
        "pending_question": None,
    }
    return conversations[key]


def _get_or_create_conversation(session_id: str, mode: str) -> Dict[str, Any]:
    key = _conversation_key(session_id, mode)
    if key not in conversations:
        return _reset_conversation(session_id, mode)
    return conversations[key]


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@app.route("/api/chat", methods=["POST"])
def chat() -> tuple[Any, int]:
    """Chat endpoint that tracks conversation history by session and mode."""

    data = request.get_json(silent=True) or {}
    session_id = str(data.get("session_id") or "").strip()
    mode = str(data.get("mode") or _get_last_mode()).lower()
    message = str(data.get("message") or "").strip()
    api_key = data.get("api_key") or _get_stored_api_key()

    if not session_id:
        return jsonify({"error": "session_id gerekli"}), 400
    if not config_manager.has_mode(mode):
        return jsonify({"error": "Geçersiz mod"}), 400
    if not message:
        return jsonify({"error": "Mesaj boş olamaz"}), 400
    if not api_key:
        return jsonify({"error": "API key gerekli"}), 400

    conversation = _get_or_create_conversation(session_id, mode)

    user_messages = [msg for msg in conversation["history"] if msg["role"] == "user"]
    if len(user_messages) >= MAX_QA_PAIRS:
        return (
            jsonify(
                {
                    "limit_reached": True,
                    "remaining_pairs": 0,
                    "history": conversation["history"],
                }
            ),
            200,
        )

    pending_question = conversation.pop("pending_question", None)
    if pending_question:
        user_content = (
            f"Interviewer question: {pending_question}\n"
            f"Candidate answer: {message}"
        )
    else:
        user_content = message

    conversation["history"].append({"role": "user", "content": user_content})

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=400,
        system=conversation["system_prompt"],
        messages=[
            {"role": entry["role"], "content": entry["content"]}
            for entry in conversation["history"]
        ],
    )

    reply_text = "".join(
        getattr(block, "text", "")
        for block in response.content
        if getattr(block, "type", "") == "text"
    ).strip()

    if reply_text:
        conversation["history"].append({"role": "assistant", "content": reply_text})

    user_count = len(
        [msg for msg in conversation["history"] if msg["role"] == "user"]
    )
    remaining = max(0, MAX_QA_PAIRS - user_count)

    return (
        jsonify(
            {
                "reply": reply_text,
                "history": conversation["history"],
                "remaining_pairs": remaining,
                "limit_reached": remaining == 0,
            }
        ),
        200,
    )


@app.route("/api/get-first-question", methods=["POST"])
def get_first_question() -> tuple[Any, int]:
    """Return the first question for the selected mode and session."""

    data = request.get_json(silent=True) or {}
    session_id = str(data.get("session_id") or "").strip()
    requested_mode = str(data.get("mode") or "").lower()

    if not session_id:
        return jsonify({"error": "session_id gerekli"}), 400

    if requested_mode:
        if not config_manager.has_mode(requested_mode):
            return jsonify({"error": "Geçersiz mod"}), 400
        mode = requested_mode
    else:
        mode = _default_mode()

    question = config_manager.get_random_question(mode)
    conversation = _reset_conversation(session_id, mode)
    conversation["pending_question"] = question["prompt"]

    return (
        jsonify(
            {
                "session_id": session_id,
                "mode": mode,
                "question": question["prompt"],
                "part": question.get("part", ""),
                "remaining_pairs": MAX_QA_PAIRS,
            }
        ),
        200,
    )


@app.route("/api/modes", methods=["GET"])
def get_modes() -> tuple[Any, int]:
    """Expose available modes with descriptions, criteria and scale."""

    modes = [config_manager.serialise_mode(mode) for mode in _all_modes()]
    payload = {
        "modes": modes,
        "default_mode": _default_mode(),
        "evaluation_modes": list(_evaluation_modes()),
    }

    return jsonify(payload), 200


@app.route("/api/validate-key", methods=["POST"])
def validate_key() -> tuple[Any, int]:
    """Validate that an Anthropic API key is usable."""

    try:
        data = request.get_json(silent=True) or {}
        api_key = data.get("api_key")

        if not api_key:
            return jsonify({"error": "API key gerekli"}), 400

        _test_api_key(api_key)
        return jsonify({"valid": True, "message": "API Key geçerli!"}), 200

    except anthropic.AuthenticationError:
        return jsonify({"valid": False, "error": "Geçersiz API Key"}), 401
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"valid": False, "error": str(exc)}), 500


@app.route("/api/save-key", methods=["POST"])
def save_key() -> tuple[Any, int]:
    """Validate and persist the provided Anthropic API key."""

    try:
        data = request.get_json(silent=True) or {}
        api_key = data.get("api_key")

        if not api_key:
            return jsonify({"error": "API key gerekli"}), 400

        _test_api_key(api_key)
        _save_api_key(api_key)
        return jsonify({"saved": True, "message": "API key kaydedildi."}), 200

    except anthropic.AuthenticationError:
        return jsonify({"saved": False, "error": "Geçersiz API Key"}), 401
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"saved": False, "error": str(exc)}), 500


@app.route("/api/api-key-status", methods=["GET"])
def api_key_status() -> tuple[Any, int]:
    """Report whether the server has a stored Anthropic API key."""

    has_key = bool(_get_stored_api_key())
    last_mode = _get_last_mode()
    return (
        jsonify(
            {
                "has_key": has_key,
                "last_mode": last_mode,
                "modes": list(_evaluation_modes()),
                "default_mode": _default_mode(),
            }
        ),
        200,
    )


@app.route("/api/evaluate", methods=["POST"])
def evaluate() -> tuple[Any, int]:
    """Evaluate an interview transcript via the Anthropic Messages API."""

    try:
        data = request.get_json(silent=True) or {}
        api_key = data.get("api_key") or _get_stored_api_key()
        transcript = data.get("transcript")
        evaluation_mode = str(data.get("evaluation_mode") or _get_last_mode()).lower()

        if not api_key or not transcript:
            return jsonify({"error": "API key ve transcript gerekli"}), 400

        if not config_manager.has_evaluation_config(evaluation_mode):
            return jsonify({"error": "Geçersiz değerlendirme modu"}), 400

        client = anthropic.Anthropic(api_key=api_key)
        system_prompt, user_prompt = create_evaluation_prompt(transcript, evaluation_mode)

        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        evaluation_text = "".join(
            getattr(block, "text", "")
            for block in message.content
            if getattr(block, "type", "") == "text"
        )

        if not evaluation_text:
            return jsonify({"error": "Claude'dan geçerli yanıt alınamadı"}), 500

        sanitized_text = _sanitize_evaluation_text(evaluation_text)

        try:
            evaluation = json.loads(sanitized_text)
        except json.JSONDecodeError as exc:
            logger.error(
                "Failed to decode evaluation payload. Raw response: %s",
                sanitized_text,
                exc_info=True,
            )
            raise ValueError("Claude yanıtı JSON formatında değil") from exc

        validated = validate_evaluation(evaluation)
        validated.setdefault("mode", evaluation_mode)
        overall_scale = config_manager.get_evaluation_config(evaluation_mode)[
            "overall_scale"
        ]
        validated.setdefault("overall_scale", overall_scale)

        _save_last_mode(evaluation_mode)

        return jsonify(validated), 200

    except anthropic.AuthenticationError:
        return jsonify({"error": "Geçersiz API Key"}), 401
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 500
    except Exception as exc:  # pragma: no cover - defensive
        return jsonify({"error": str(exc)}), 500


@app.route("/health", methods=["GET"])
def health() -> tuple[Any, int]:
    """Simple health check endpoint."""

    return jsonify({"status": "ok", "message": "Backend çalışıyor!"}), 200


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Backend Server Başlatılıyor...")
    print("=" * 50)
    print("📍 URL: http://localhost:5000")
    print("✅ CORS: Aktif")
    print("🔑 Anthropic API: Hazır")
    print("=" * 50)
    print("\nŞimdi tarayıcınızda uygulamayı açmak için http://localhost:5173/ adresine gidebilirsiniz!")
    print("=" * 50)

    app.run(debug=True, port=5000, host="0.0.0.0")

