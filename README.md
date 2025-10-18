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

Once the key is stored in `.env`, the input form is hidden on future visits.

## Running the backend
Start the Flask server:
```bash
python backend.py
```
The server listens on `http://localhost:5000` and exposes endpoints for validating API keys and evaluating interviews.

## Using the front-end
1. Open the `interview.html` file in a browser.
2. If prompted, save a valid Anthropic API key.
3. Paste an interview transcript and click **Evaluate Interview** to receive structured feedback.

## Updating or removing the API key
To change the stored key, edit or delete the `ANTHROPIC_API_KEY` entry inside the `.env` file and refresh the page. The UI will prompt for a new key when needed.
