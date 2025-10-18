# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import os
import json
import logging
import re
import importlib.util
import sys
from pathlib import Path

VALID_MODES = {"toefl", "ielts", "business", "casual"}
DEFAULT_MODE = "toefl"
LAST_MODE_KEY = "LAST_EVALUATION_MODE"


ENV_KEY_NAME = "ANTHROPIC_API_KEY"
ENV_PATH = Path(__file__).resolve().parent / ".env"


def _register_config_module() -> None:
    """Expose the configuration package under the ``backend`` namespace."""

    configs_path = Path(__file__).resolve().parent / "backend" / "configs" / "__init__.py"
    module_name = "backend.configs"

    if module_name in sys.modules:
        return

    if not configs_path.exists():  # pragma: no cover - defensive safeguard
        return

    spec = importlib.util.spec_from_file_location(module_name, configs_path)
    if not spec or not spec.loader:
        raise ImportError(f"Unable to load configuration module from {configs_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[module_name] = module
    setattr(sys.modules[__name__], "configs", module)

    if hasattr(module, "ConfigManager"):
        setattr(sys.modules[__name__], "ConfigManager", module.ConfigManager)


_register_config_module()


TOEFL_SYSTEM = """You are a certified TOEFL iBT Speaking examiner with 15+ years of experience.

SCORING GUIDE (0-4 scale per question):
4 (Good): Speech is generally clear and fluid. Minor lapses in grammar/vocabulary don't obscure meaning. Response is well-organized and developed with appropriate detail.

3 (Fair): Speech is generally clear with some fluidity. Grammar/vocabulary sometimes limits ability to express ideas clearly. Response shows basic development but may lack detail or clarity.

2 (Limited): Speech lacks clarity and fluidity. Limited grammar/vocabulary significantly affects expression. Response is limited in content and development.

1 (Weak): Very little relevant content. Speech is unclear. Severe problems with grammar/vocabulary.

0: No attempt or completely off-topic.

EVALUATION CRITERIA:
- Delivery (15%): Pace, clarity, pronunciation, intonation
- Language Use (40%): Grammar accuracy, vocabulary range and precision, sentence complexity
- Topic Development (45%): Relevance, organization, coherence, supporting details

Provide scores for each question (0-4), calculate total (sum * 1.5 = /30), and CEFR level.
"""

IELTS_SYSTEM = """You are an official IELTS Speaking examiner certified by British Council/IDP.

BAND DESCRIPTORS (0-9 scale, use 0.5 increments):

Band 9 (Expert): Full operational command, appropriate, accurate, and fluent.
Band 8 (Very Good): Fully operational with occasional inaccuracies.
Band 7 (Good): Operational command, occasional inaccuracies, some complex language.
Band 6 (Competent): Effective command despite inaccuracies, can use complex language.
Band 5 (Modest): Partial command, frequent errors, basic meaning usually clear.
Band 4 (Limited): Very limited to familiar situations, frequent communication breakdowns.
Band 3 (Extremely Limited): Conveys only general meaning in familiar situations.
Band 2-1: Essentially no communication possible.

ASSESSMENT CRITERIA (Equal 25% each):
1. Fluency & Coherence: Flow, linking, self-correction, hesitation
2. Lexical Resource: Vocabulary range, precision, collocations, paraphrasing
3. Grammatical Range & Accuracy: Complexity, structures, error-free sentences
4. Pronunciation: Sounds, word stress, intonation, intelligibility

Provide individual criterion scores and overall band (average, rounded to 0.5).
"""

BUSINESS_SYSTEM = """You are a corporate communication trainer specializing in Business English assessment.

EVALUATION AREAS (0-100 scale):
1. Professional Communication (25%): Appropriate formality, politeness, directness
2. Business Vocabulary (25%): Industry terms, corporate jargon, professional expressions
3. Clarity & Structure (20%): Organized thoughts, clear main points, logical flow
4. Meeting & Presentation Skills (15%): Confidence, engagement, persuasiveness
5. Email/Written Parallels (15%): Formal structures that translate to business writing

SCORING LEVELS:
90-100: Executive level, ready for C-suite communication
80-89: Senior professional, can handle complex business scenarios
70-79: Mid-level professional, effective in standard business contexts
60-69: Junior professional, needs development in advanced scenarios
50-59: Entry level, requires significant improvement
Below 50: Not yet ready for professional business communication

Provide detailed feedback on professional strengths and development areas.
"""

CASUAL_SYSTEM = """You are a native English speaker evaluating natural, everyday conversation ability.

EVALUATION CRITERIA (0-100 scale):
1. Natural Flow (30%): Sounds like a real conversation, not scripted/formal
2. Idioms & Expressions (20%): Uses common sayings, phrasal verbs, colloquialisms
3. Cultural Awareness (15%): References to culture, current events, shared knowledge
4. Informal Language (20%): Contractions, slang (appropriate), casual vocabulary
5. Authenticity (15%): Would pass as native-like in casual settings

SCORING LEVELS:
90-100: Near-native, sounds completely natural
80-89: Advanced, very comfortable and natural
70-79: Upper-intermediate, mostly natural with minor awkwardness
60-69: Intermediate, understandable but noticeably non-native
50-59: Basic, struggles with informal contexts
Below 50: Too formal or limited for casual conversation

Look for: "gonna", "wanna", "kinda", phrasal verbs, natural reactions, filler words (um, like, you know).
"""


TOEFL_EXAMPLES = """
EXAMPLE 1 (Score 4):
Q: Describe your hometown.
A: "I'm from Istanbul, which is a fascinating city that bridges Europe and Asia. It has a rich history dating back thousands of years, with landmarks like the Hagia Sophia and Blue Mosque. The city offers a unique blend of traditional and modern culture, and the food scene is absolutely incredible. I particularly love the vibrant neighborhoods along the Bosphorus."
Reasoning: Clear delivery, varied vocabulary (fascinating, bridges, landmarks), complex structures, well-organized response with specific details.

EXAMPLE 2 (Score 2):
Q: Describe your hometown.
A: "My hometown is... um... it's big city. Has many building and people. I like it because... uh... it is nice. Many restaurant and shop there. People is friendly."
Reasoning: Frequent errors (many building, people is), limited vocabulary, choppy delivery with many hesitations, minimal development.
"""

IELTS_EXAMPLES = """
EXAMPLE 1 (Band 8.0):
Candidate answers fluently with natural linking phrases, uses advanced vocabulary like "resilient workforce" and "strategic foresight", demonstrates accurate complex grammar, and pronunciation is clear with native-like intonation.

EXAMPLE 2 (Band 5.5):
Candidate hesitates frequently, vocabulary is limited to basic terms, grammar errors ("she go", "he don't"), and pronunciation causes occasional misunderstandings.
"""

BUSINESS_EXAMPLES = """
EXAMPLE 1 (Score 92):
Clear executive presence, uses terms like "stakeholder alignment" and "quarterly runway", structures responses with signposting, and demonstrates confident delivery appropriate for board-level meetings.

EXAMPLE 2 (Score 58):
Overly informal tone in a leadership context, limited business vocabulary, ideas presented without clear structure, and responses lack persuasive impact.
"""

CASUAL_EXAMPLES = """
EXAMPLE 1 (Score 88):
Speaks with relaxed rhythm, uses idioms such as "hit the nail on the head" and phrasal verbs like "hang out", references popular shows naturally, and sounds spontaneous.

EXAMPLE 2 (Score 52):
Overly formal phrases, minimal idiom usage, responses feel rehearsed, and limited cultural references make the conversation sound unnatural.
"""


MODE_CONFIG = {
    "toefl": {
        "system": TOEFL_SYSTEM,
        "overall_scale": "0-30",
        "criterion_structure": """{
    \"delivery\": {\"score\": <number 0-4>, \"max_score\": 4, \"weight\": 0.15},
    \"language_use\": {\"score\": <number 0-4>, \"max_score\": 4, \"weight\": 0.4},
    \"topic_development\": {\"score\": <number 0-4>, \"max_score\": 4, \"weight\": 0.45}
}""",
        "equivalent_structure": """{
    \"ielts_band\": <number 0-9>,
    \"business_score\": <number 0-100>,
    \"casual_score\": <number 0-100>
}""",
        "question_max": 4,
        "extra_fields": "",
        "examples": TOEFL_EXAMPLES,
        "guidance": "Focus on academic tone, cite specific sentences that demonstrate vocabulary precision or organizational clarity, and ensure total TOEFL score is the sum of question scores multiplied by 1.5."
    },
    "ielts": {
        "system": IELTS_SYSTEM,
        "overall_scale": "Band 0-9",
        "criterion_structure": """{
    \"fluency_coherence\": {\"score\": <number 0-9>, \"max_score\": 9},
    \"lexical_resource\": {\"score\": <number 0-9>, \"max_score\": 9},
    \"grammatical_range_accuracy\": {\"score\": <number 0-9>, \"max_score\": 9},
    \"pronunciation\": {\"score\": <number 0-9>, \"max_score\": 9}
}""",
        "equivalent_structure": """{
    \"toefl_total\": <number 0-30>,
    \"business_score\": <number 0-100>,
    \"casual_score\": <number 0-100>
}""",
        "question_max": 9,
        "extra_fields": "",
        "examples": IELTS_EXAMPLES,
        "guidance": "Use British/International English spelling, justify each band descriptor with precise evidence, and round the overall band score to the nearest 0.5."
    },
    "business": {
        "system": BUSINESS_SYSTEM,
        "overall_scale": "0-100",
        "criterion_structure": """{
    \"professional_communication\": {\"score\": <number 0-100>, \"weight\": 0.25},
    \"business_vocabulary\": {\"score\": <number 0-100>, \"weight\": 0.25},
    \"clarity_structure\": {\"score\": <number 0-100>, \"weight\": 0.2},
    \"meeting_skills\": {\"score\": <number 0-100>, \"weight\": 0.15},
    \"confidence\": {\"score\": <number 0-100>, \"weight\": 0.15}
}""",
        "equivalent_structure": """{
    \"toefl_total\": <number 0-30>,
    \"ielts_band\": <number 0-9>,
    \"casual_score\": <number 0-100>
}""",
        "question_max": 100,
        "extra_fields": ",\n    \"professional_level\": \"<Entry/Junior/Mid/Senior/Executive>\",\n    \"recommended_roles\": [\"role1\", \"role2\"],",
        "examples": BUSINESS_EXAMPLES,
        "guidance": "Adopt a corporate tone, align feedback with leadership competencies, and explain how the candidate performs in meetings, presentations, and stakeholder updates."
    },
    "casual": {
        "system": CASUAL_SYSTEM,
        "overall_scale": "0-100",
        "criterion_structure": """{
    \"natural_flow\": {\"score\": <number 0-100>, \"weight\": 0.3},
    \"idiom_usage\": {\"score\": <number 0-100>, \"weight\": 0.2},
    \"cultural_awareness\": {\"score\": <number 0-100>, \"weight\": 0.15},
    \"informal_language\": {\"score\": <number 0-100>, \"weight\": 0.2},
    \"authenticity\": {\"score\": <number 0-100>, \"weight\": 0.15}
}""",
        "equivalent_structure": """{
    \"toefl_total\": <number 0-30>,
    \"ielts_band\": <number 0-9>,
    \"business_score\": <number 0-100>
}""",
        "question_max": 100,
        "extra_fields": ",\n    \"native_likeness\": <number 0-100>,\n    \"idiom_examples\": [\"example1\", \"example2\"],",
        "examples": CASUAL_EXAMPLES,
        "guidance": "Focus on informal markers such as contractions, filler words, and cultural references. Highlight idioms or slang that stood out, and comment on how natural the conversation felt."
    },
}


def create_evaluation_prompt(transcript: str, mode: str) -> tuple[str, str]:
    """Create Anthropic system and user prompts for the requested evaluation mode."""

    mode_key = mode if mode in MODE_CONFIG else DEFAULT_MODE
    config = MODE_CONFIG[mode_key]

    system_prompt = config["system"]
    overall_scale = config["overall_scale"]
    criterion_structure = config["criterion_structure"]
    equivalent_structure = config["equivalent_structure"]
    question_max = config["question_max"]
    examples = config["examples"]
    guidance = config["guidance"]
    extra_fields = config["extra_fields"]

    user_prompt = f"""INTERVIEW TRANSCRIPT:
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


def _load_env_file() -> dict:
    """Load key-value pairs from the .env file if it exists."""
    if not ENV_PATH.exists():
        return {}

    data = {}
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


def _write_env_file(values: dict) -> None:
    """Persist key-value pairs to the .env file."""
    with ENV_PATH.open("w", encoding="utf-8") as env_file:
        for key, value in values.items():
            env_file.write(f"{key}={value}\n")


def _save_api_key(api_key: str) -> None:
    """Persist the API key in memory and the .env file."""
    data = _load_env_file()
    data[ENV_KEY_NAME] = api_key
    _write_env_file(data)
    os.environ[ENV_KEY_NAME] = api_key


def _get_last_mode(default: str = DEFAULT_MODE) -> str:
    """Return the most recently used evaluation mode."""
    data = _load_env_file()
    mode = data.get(LAST_MODE_KEY, default)
    return mode if mode in VALID_MODES else default


def _save_last_mode(mode: str) -> None:
    """Persist the last used evaluation mode in the .env file."""
    if mode not in VALID_MODES:
        return
    data = _load_env_file()
    data[LAST_MODE_KEY] = mode
    _write_env_file(data)


def _test_api_key(api_key: str) -> None:
    """Perform a lightweight request to validate the Anthropic API key."""
    client = anthropic.Anthropic(api_key=api_key)
    client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}],
    )


FENCE_LABEL_PATTERN = r"[a-z0-9_+\-]*"


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

app = Flask(__name__)
CORS(app)  # CORS sorununu çözer
logger = logging.getLogger(__name__)

@app.route('/api/validate-key', methods=['POST'])
def validate_key():
    """API Key'in geçerliliğini test eder"""
    try:
        data = request.json or {}
        api_key = data.get('api_key')

        if not api_key:
            return jsonify({'error': 'API key gerekli'}), 400

        _test_api_key(api_key)
        return jsonify({'valid': True, 'message': 'API Key geçerli!'}), 200

    except anthropic.AuthenticationError:
        return jsonify({'valid': False, 'error': 'Geçersiz API Key'}), 401
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)}), 500


@app.route('/api/save-key', methods=['POST'])
def save_key():
    """API key'i doğrular ve .env dosyasına kaydeder."""
    try:
        data = request.json or {}
        api_key = data.get('api_key')

        if not api_key:
            return jsonify({'error': 'API key gerekli'}), 400

        _test_api_key(api_key)
        _save_api_key(api_key)
        return jsonify({'saved': True, 'message': 'API key kaydedildi.'}), 200

    except anthropic.AuthenticationError:
        return jsonify({'saved': False, 'error': 'Geçersiz API Key'}), 401
    except Exception as e:
        return jsonify({'saved': False, 'error': str(e)}), 500


@app.route('/api/api-key-status', methods=['GET'])
def api_key_status():
    """Sunucuda API key mevcut mu kontrol eder."""
    has_key = bool(_get_stored_api_key())
    last_mode = _get_last_mode()
    return jsonify({'has_key': has_key, 'last_mode': last_mode, 'modes': sorted(VALID_MODES)}), 200


@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    """Claude ile mülakat değerlendirmesi yapar"""
    try:
        data = request.json or {}
        api_key = data.get('api_key') or _get_stored_api_key()
        transcript = data.get('transcript')
        evaluation_mode = (data.get('evaluation_mode') or _get_last_mode()).lower()

        if not api_key or not transcript:
            return jsonify({'error': 'API key ve transcript gerekli'}), 400

        if evaluation_mode not in VALID_MODES:
            return jsonify({'error': 'Geçersiz değerlendirme modu'}), 400

        # Anthropic client oluştur
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
            return jsonify({'error': "Claude'dan geçerli yanıt alınamadı"}), 500

        sanitized_text = _sanitize_evaluation_text(evaluation_text)

        try:
            evaluation = json.loads(sanitized_text)
        except json.JSONDecodeError:
            logger.error(
                "Failed to decode evaluation payload. Raw response: %s",
                sanitized_text,
                exc_info=True,
            )
            return (
                jsonify(
                    {
                        'error': "Claude'dan geçersiz yanıt",
                        'details': 'Claude yanıtı JSON formatında değil.',
                    }
                ),
                500,
            )

        evaluation.setdefault('mode', evaluation_mode)
        evaluation.setdefault('overall_scale', MODE_CONFIG[evaluation_mode]['overall_scale'])

        _save_last_mode(evaluation_mode)

        return jsonify(evaluation), 200

    except anthropic.AuthenticationError:
        return jsonify({'error': 'Geçersiz API Key'}), 401
    except json.JSONDecodeError:
        logger.exception('Failed to decode evaluation payload outside main handler')
        return jsonify({'error': 'Claude\'dan geçersiz yanıt'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Server sağlık kontrolü"""
    return jsonify({'status': 'ok', 'message': 'Backend çalışıyor!'}), 200


if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Backend Server Başlatılıyor...")
    print("=" * 50)
    print("📍 URL: http://localhost:5000")
    print("✅ CORS: Aktif")
    print("🔑 Anthropic API: Hazır")
    print("=" * 50)
    print("\nŞimdi tarayıcınızda interview.html'i açabilirsiniz!")
    print("=" * 50)
    
    app.run(debug=True, port=5000, host='0.0.0.0')
