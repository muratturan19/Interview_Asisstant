# Interview Assistant

Interview Assistant is a lightweight tool that validates an Anthropic API key, sends interview transcripts to Claude for evaluation, and presents the results in a rich web UI.

## Prerequisites
- Python 3.10+
- An Anthropic API key

## Installation
1. (Optional) Create and activate a virtual environment.
2. Install the backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuring the Anthropic API key
You can provide the API key in two different ways:

- **Using a `.env` file**: create a file named `.env` in the project root and add the key as shown below:
  ```env
  ANTHROPIC_API_KEY=sk-ant-...
  ```
- **Using the web UI**: start the backend server (see below) and open `interview.html` in your browser. If no key is found in `.env`, the page will prompt you to enter the key. Click **Save API Key** to validate and persist it automatically.

Once the key is stored in `.env`, the input form is hidden on future visits. The same file now also remembers your last scoring preference under `LAST_EVALUATION_MODE` so that the UI can default to the framework you used previously.

## Running the backend
Start the Flask server:
```bash
python backend.py
```
The server listens on `http://localhost:5000` and exposes endpoints for validating API keys and evaluating interviews.

## Using the front-end
1. Open the `interview.html` file in a browser. When loaded directly via `file://`, the page automatically targets the backend at `http://localhost:5000`, so make sure the Flask server is running first.
2. Seçmek istediğiniz değerlendirme modunu kartlardan işaretleyin (TOEFL, IELTS, Business veya Casual).
3. If prompted, save a valid Anthropic API key.
4. Paste an interview transcript and click **Evaluate Interview** to receive mode-specific feedback.

## Updating or removing the API key
To change the stored key, edit or delete the `ANTHROPIC_API_KEY` entry inside the `.env` file and refresh the page. The UI will prompt for a new key when needed.

## Evaluation modes

The assistant now supports four professional scoring frameworks. Each mode uses a dedicated system prompt, dedicated rubrics, and tailored reporting on the results screen.

### 🎓 TOEFL Speaking (Academic)
- **Skala:** 0–4 (soru bazında) → 0–30 toplam.
- **Kriterler:** Delivery, Language Use, Topic Development.
- **Çıktılar:** Her görev için 0–4 puan, CEFR eşleştirmesi, IELTS/Biz/Casual karşılıkları.
- **Örnek çıktı:**
  ```json
  {
    "mode": "toefl",
    "overall_score": 27,
    "overall_scale": "0-30",
    "criterion_scores": {
      "delivery": {"score": 3, "max_score": 4, "weight": 0.15},
      "language_use": {"score": 3.5, "max_score": 4, "weight": 0.4},
      "topic_development": {"score": 3.5, "max_score": 4, "weight": 0.45}
    },
    "cefr_level": "C1",
    "equivalent_scores": {
      "ielts_band": 7.5,
      "business_score": 82,
      "casual_score": 85
    },
    "question_breakdown": [
      {
        "question_number": 1,
        "score": 3,
        "max_score": 4,
        "feedback": "Speech was clear with minor pauses; add one more detail about the neighbourhood."
      }
    ],
    "strengths": ["Net ve akıcı anlatım", "Akademik kelime seçimi"],
    "improvements": ["Daha fazla örnek", "Bağlaç çeşitliliği"],
    "detailed_feedback": "The response demonstrates solid academic English with occasional hesitation. Provide richer examples to secure a 4.",
    "specific_examples": {
      "good": ["'bridges Europe and Asia' ifadesi", "Tarihsel referanslar"],
      "needs_work": ["Kapanış cümlesi kısa kaldı"]
    }
  }
  ```

### 🇬🇧 IELTS Speaking (British)
- **Skala:** Band 0–9 (0.5 artışlarla).
- **Kriterler:** Fluency & Coherence, Lexical Resource, Grammatical Range & Accuracy, Pronunciation.
- **Çıktılar:** Her kriter için band değeri, CEFR, TOEFL/Business/Casual tahminleri.
- **Örnek çıktı:**
  ```json
  {
    "mode": "ielts",
    "overall_score": 7.5,
    "overall_scale": "Band 0-9",
    "criterion_scores": {
      "fluency_coherence": {"score": 7.5, "max_score": 9},
      "lexical_resource": {"score": 7, "max_score": 9},
      "grammatical_range_accuracy": {"score": 7, "max_score": 9},
      "pronunciation": {"score": 8, "max_score": 9}
    },
    "cefr_level": "C1",
    "equivalent_scores": {
      "toefl_total": 25,
      "business_score": 80,
      "casual_score": 83
    },
    "question_breakdown": [
      {
        "question_number": 1,
        "score": 7.5,
        "max_score": 9,
        "feedback": "Uses linking phrases naturally; add one complex sentence to reach band 8."
      }
    ],
    "strengths": ["Akıcı ve bağlantılı anlatım", "Doğru telaffuz"],
    "improvements": ["Daha fazla ileri yapı", "Kelime çeşitliliği"],
    "detailed_feedback": "Overall performance aligns with a strong band 7.5. Continue adding idiomatic language for band 8.",
    "specific_examples": {
      "good": ["'on balance' ifadesi"],
      "needs_work": ["Karmaşık cümle yapısı eksik"]
    }
  }
  ```

### 💼 Business English (Professional)
- **Skala:** 0–100, % ağırlıklı kriterler.
- **Kriterler:** Professional Communication, Business Vocabulary, Clarity & Structure, Meeting Skills, Confidence.
- **Çıktılar:** Profesyonel seviye etiketi, önerilen pozisyonlar, diğer modlara dönüşümler.
- **Örnek çıktı:**
  ```json
  {
    "mode": "business",
    "overall_score": 84,
    "overall_scale": "0-100",
    "criterion_scores": {
      "professional_communication": {"score": 86, "weight": 0.25},
      "business_vocabulary": {"score": 82, "weight": 0.25},
      "clarity_structure": {"score": 80, "weight": 0.2},
      "meeting_skills": {"score": 85, "weight": 0.15},
      "confidence": {"score": 88, "weight": 0.15}
    },
    "professional_level": "Senior professional",
    "recommended_roles": ["Product Manager", "Client Success Lead"],
    "equivalent_scores": {
      "toefl_total": 24,
      "ielts_band": 7,
      "casual_score": 88
    },
    "strengths": ["Net toplantı çerçevesi", "Kurumsal ton"],
    "improvements": ["Raporlamada daha fazla metrik", "Kapanış çağrısı"],
    "detailed_feedback": "Presentation-ready delivery with clear stakeholder language. Introduce metrics earlier for executive impact.",
    "specific_examples": {
      "good": ["'stakeholder alignment' ifadesi"],
      "needs_work": ["Sonuç bölümünde aksiyon listesi eksik"]
    }
  }
  ```

### 💬 Casual Conversation (Daily English)
- **Skala:** 0–100; doğal akış ve kültürel referanslara odaklı.
- **Kriterler:** Natural Flow, Idiom Usage, Cultural Awareness, Informal Language, Authenticity.
- **Çıktılar:** Native-likeness yüzdesi, kullanılan idiom/slang örnekleri, diğer modlara dönüşümler.
- **Örnek çıktı:**
  ```json
  {
    "mode": "casual",
    "overall_score": 78,
    "overall_scale": "0-100",
    "criterion_scores": {
      "natural_flow": {"score": 80, "weight": 0.3},
      "idiom_usage": {"score": 74, "weight": 0.2},
      "cultural_awareness": {"score": 76, "weight": 0.15},
      "informal_language": {"score": 79, "weight": 0.2},
      "authenticity": {"score": 81, "weight": 0.15}
    },
    "native_likeness": 78,
    "idiom_examples": ["kind of", "hang out", "beat me to it"],
    "equivalent_scores": {
      "toefl_total": 23,
      "ielts_band": 6.5,
      "business_score": 70
    },
    "strengths": ["Doğal reaksiyonlar", "Günlük deyimler"],
    "improvements": ["Bazı cümleler fazla uzun", "Daha fazla kültürel referans"],
    "detailed_feedback": "Casual tone feels authentic with well-placed idioms. Watch for run-on sentences when excited.",
    "specific_examples": {
      "good": ["'we just binge-watched' ifadesi"],
      "needs_work": ["Uzun cümlede nefes almadan konuşma"]
    }
  }
  ```

## Manual test scenarios

Use the following quick checks after starting the Flask backend (`python backend.py`) and opening `interview.html`:

1. **TOEFL akademik kontrolü**
   - TOEFL kartını seçin, kısa bir akademik konuşma transcripti yapıştırın (ör. şehir tanıtımı).
   - **Evaluate Interview** düğmesine basın.
   - Sonuç ekranında toplam 0–30 puan, her görev için 0–4 değerleri ve CEFR/IELTS karşılığını doğrulayın.

2. **IELTS British değerlendirmesi**
   - IELTS kartını seçin ve aynı transcripti kullanın.
   - Çıktıda dört kriterin ayrı band değerlerini (0.5 artış) ve TOEFL karşılığını kontrol edin.

3. **Business English profesyonel seviyesi**
   - Business kartını seçin, toplantı/iş sunumu odaklı transcript yapıştırın.
   - Profesyonel seviye (Entry/Junior/Mid/Senior/Executive) etiketinin ve önerilen pozisyonların geldiğini doğrulayın.

4. **Casual Conversation günlük konuşması**
   - Casual kartını seçin, arkadaş sohbeti tarzında transcript kullanın.
   - Native-likeness yüzdesi ve idiom/slang örneklerinin listelendiğini kontrol edin.

5. **Mod kalıcılığı**
   - Bir modu seçip değerlendirme yaptıktan sonra sayfayı yenileyin.
   - `interview.html` tekrar açıldığında aynı modun varsayılan seçili olduğunu doğrulayın (`LAST_EVALUATION_MODE` `.env` dosyasına yazılır).
