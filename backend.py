# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify
from flask_cors import CORS
import anthropic
import os

app = Flask(__name__)
CORS(app)  # CORS sorununu çözer

@app.route('/api/validate-key', methods=['POST'])
def validate_key():
    """API Key'in geçerliliğini test eder"""
    try:
        data = request.json
        api_key = data.get('api_key')
        
        if not api_key:
            return jsonify({'error': 'API key gerekli'}), 400
        
        # Anthropic client oluştur
        client = anthropic.Anthropic(api_key=api_key)
        
        # Basit bir test çağrısı
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=10,
            messages=[{"role": "user", "content": "Hi"}]
        )
        
        return jsonify({'valid': True, 'message': 'API Key geçerli!'}), 200
        
    except anthropic.AuthenticationError:
        return jsonify({'valid': False, 'error': 'Geçersiz API Key'}), 401
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)}), 500


@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    """Claude ile mülakat değerlendirmesi yapar"""
    try:
        data = request.json
        api_key = data.get('api_key')
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
        import json
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
