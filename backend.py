# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import os
import json
from pathlib import Path


ENV_KEY_NAME = "ANTHROPIC_API_KEY"
ENV_PATH = Path(__file__).resolve().parent / ".env"


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


def _test_api_key(api_key: str) -> None:
    """Perform a lightweight request to validate the Anthropic API key."""
    client = anthropic.Anthropic(api_key=api_key)
    client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=10,
        messages=[{"role": "user", "content": "Hi"}],
    )

app = Flask(__name__)
CORS(app)  # CORS sorununu çözer

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
    return jsonify({'has_key': has_key}), 200


@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    """Claude ile mülakat değerlendirmesi yapar"""
    try:
        data = request.json or {}
        api_key = data.get('api_key') or _get_stored_api_key()
        transcript = data.get('transcript')

        if not api_key or not transcript:
            return jsonify({'error': 'API key ve transcript gerekli'}), 400

        # Anthropic client oluştur
        client = anthropic.Anthropic(api_key=api_key)
        
        # Değerlendirme prompt'u
        prompt = f"""You are an expert English language evaluator. Below is a transcript of an English interview with a candidate. Please evaluate their English proficiency and provide a detailed assessment.

TRANSCRIPT:
{transcript}

Please provide your evaluation in the following JSON format (respond ONLY with valid JSON, no other text):

{{
  "grammar": <score 0-100>,
  "vocabulary": <score 0-100>,
  "fluency": <score 0-100>,
  "comprehension": <score 0-100>,
  "overall": <score 0-100>,
  "level": "<A1/A2/B1/B2/C1/C2>",
  "strengths": ["strength1", "strength2", "strength3"],
  "improvements": ["area1", "area2", "area3"],
  "detailed_feedback": "A comprehensive paragraph about their performance"
}}

Be specific and constructive in your evaluation."""

        # Claude'a gönder
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # Cevabı parse et
        evaluation_text = message.content[0].text

        # JSON olarak döndür
        evaluation = json.loads(evaluation_text)
        
        return jsonify(evaluation), 200
        
    except anthropic.AuthenticationError:
        return jsonify({'error': 'Geçersiz API Key'}), 401
    except json.JSONDecodeError:
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
