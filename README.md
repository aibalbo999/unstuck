# Wall Street AI Stock Research System

FastAPI-based stock research report generator with a multi-agent analysis pipeline.

## Security Setup

API keys are intentionally not committed. For local development:

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set:

```bash
GEMINI_API_KEYS=your_key_1,your_key_2
```

Generated reports are written to `backend/output/` by default and are ignored by Git.

## Run On macOS

Double-click:

```bash
start_mac.command
```

Or run manually:

```bash
cd backend
python3 -m pip install --user -r requirements.txt
python3 -m uvicorn api:app --host 0.0.0.0 --port 8080
```

Then open:

```text
http://127.0.0.1:8080
```
