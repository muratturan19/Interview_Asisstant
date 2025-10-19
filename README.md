# Interview Assistant

Interview Assistant is a config-driven practice tool for spoken-English interviews. The backend loads mode definitions from JSON files, uses Anthropic's Claude Sonnet 4.5 model for both live interview questions and structured scoring, and exposes a lightweight REST API consumed by a React + Vite front-end.

## Quick start

### Prerequisites
- Python 3.10+
- Node.js 18+
- An Anthropic API key with access to Claude Sonnet 4.5

### 1. Install backend dependencies
```bash
pip install -r requirements.txt
```

### 2. Install front-end dependencies
```bash
npm install
```

### 3. Run the services
Start the Flask API (runs on `http://localhost:5000`):
```bash
python backend.py
```

In a second terminal start the Vite dev server (serves on `http://localhost:5173`):
```bash
npm run dev
```

Open [`http://localhost:5173/`](http://localhost:5173/) to use the UI.

## Configuring credentials and preferences

The backend looks for an Anthropic API key in the environment or in a project-level `.env` file. You can create it manually:
```env
ANTHROPIC_API_KEY=sk-ant-...
```

or supply the key through the UI: the **API key** field on the main page will POST to `/api/save-key`, validate the key with a short Claude request, and persist it to `.env`. The backend also remembers the last selected evaluation mode under the `LAST_EVALUATION_MODE` entry so the UI can default to your previous choice.

To update or remove the key, edit or delete the corresponding entry in `.env` and refresh the page.

## How the new system works

1. **Mode discovery.** `/api/modes` reads the JSON definitions in `configs/*.json` and returns descriptions, criteria, and scoring scale metadata for the supported modes. The UI uses this to render the mode selector and rubric cards.
2. **Question flow.** Clicking **İlk soruyu al** requests `/api/get-first-question`. The backend picks a random prompt for the chosen mode, resets the conversation state, and tracks it by the browser-provided session ID.
3. **Guided conversation.** `/api/chat` keeps up to five question–answer pairs (`MAX_QA_PAIRS`) per session and mode. Each response is generated with the mode-specific system prompt and the active Anthropic key.
4. **Structured evaluation.** `/api/evaluate` composes a long-form user prompt that embeds the transcript, mode guidance, examples, and JSON schema. Claude's JSON response is sanitised and validated before being returned to the UI for display.

The UI automatically converts the chat history into an evaluation transcript, but you can override it manually before submitting for scoring.

## Available evaluation modes

All modes share the same JSON contract (overall score, criterion scores, question breakdown, strengths, improvements, and specific examples). Each mode simply adjusts the rubric weights, expected scale, and feedback guidance:

| Mode | Scale | Key criteria | Highlights |
| ---- | ----- | ------------ | ---------- |
| 🎓 **TOEFL Speaking (Academic)** | 0–30 total (0–4 per question) | Delivery, Language Use, Topic Development | Includes CEFR level and IELTS/Business/Casual score conversions.
| 🇬🇧 **IELTS Speaking (British)** | Band 0–9 (0.5 increments) | Fluency & Coherence, Lexical Resource, Grammatical Range & Accuracy, Pronunciation | Reports band per criterion plus TOEFL/Business/Casual equivalents.
| 💼 **Business English (Professional)** | 0–100 weighted | Professional Communication, Business Vocabulary, Clarity & Structure, Meeting Skills, Confidence | Adds professional level labels and recommended roles.
| 💬 **Casual Conversation (Daily English)** | 0–100 weighted | Natural Flow, Idiom Usage, Cultural Awareness, Informal Language, Authenticity | Surfaces idiom examples and a native-likeness percentage.

Each mode includes reference examples inside the backend prompt to keep Claude calibrated to the target rubric.

## API reference (for automation or integrations)

| Method & path | Purpose | Expected payload | Notes |
| ------------- | ------- | ---------------- | ----- |
| `GET /api/health` | Health probe | — | Returns `{ "status": "ok" }` when the backend is running. |
| `GET /api/modes` | List supported modes | — | Used by the UI to render descriptions, criteria, and scale details. |
| `POST /api/get-first-question` | Start/reset an interview session | `{ "session_id": string, "mode": string }` | Returns the first prompt plus the remaining question quota. |
| `POST /api/chat` | Continue the guided conversation | `{ "session_id": string, "mode": string, "message": string, "api_key"?: string }` | Maintains history for up to five user turns and echoes the running transcript. |
| `POST /api/evaluate` | Score an interview transcript | `{ "transcript": string, "evaluation_mode": string, "api_key"?: string }` | Responds with validated JSON containing scores, feedback, and examples. |
| `POST /api/validate-key` | Validate an Anthropic key without saving it | `{ "api_key": string }` | Useful for front-end form validation. |
| `POST /api/save-key` | Persist a verified Anthropic key | `{ "api_key": string }` | Writes the key to `.env` and to the process environment. |
| `GET /api/api-key-status` | Check stored key status | — | Returns `has_key`, `last_mode`, and the list of available modes. |

## Building for production

Create an optimised UI bundle with:
```bash
npm run build
```
The assets will be emitted to `dist/` along with a processed `index.html` wrapper that points at the built scripts.

## Tests

Backend utilities that sanitise and validate Claude responses are covered by unit tests. Run them with:
```bash
pytest
```

## Manual QA checklist

After starting the backend (`python backend.py`) and opening the UI, you can sanity-check each mode:

1. **TOEFL akademik kontrolü** – Select the TOEFL card, paste an academic-style transcript, click **Evaluate Interview**, and confirm the 0–30 totals plus per-question 0–4 scores and CEFR/IELTS equivalents.
2. **IELTS British değerlendirmesi** – Switch to IELTS and verify that each criterion reports a band score in 0.5 increments alongside the TOEFL conversion.
3. **Business English profesyonel seviyesi** – Use a business-focused transcript and confirm the professional level label and recommended roles.
4. **Casual Conversation günlük konuşması** – Provide a casual transcript and check the native-likeness percentage and idiom/slang examples.
5. **Mod kalıcılığı** – After running an evaluation, refresh the page and ensure that the last-used mode remains selected via the `LAST_EVALUATION_MODE` entry in `.env`.

