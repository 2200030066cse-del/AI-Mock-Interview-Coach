# Setup Guide

Step-by-step instructions to get the AI Mock Interview Coach running locally. For a tour of the
app itself once it's running, see [`USER_GUIDE.md`](USER_GUIDE.md).

## Prerequisites

- **Python 3.11+** (`python --version` to check)
- **pip** (comes with Python)
- **git** (to clone the repo)
- An API key for **one** LLM provider:
  - **Groq** (recommended to start) -- free tier, no billing setup required. Get a key at
    [console.groq.com/keys](https://console.groq.com/keys).
  - **OpenAI** -- requires a billing method on the account. Get a key at
    [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

## 1. Get the code

```bash
git clone <this-repo-url>
cd AI-Mock-Interview-Coach
```

(Or download/unzip the project folder directly if you weren't given a git URL.)

## 2. Create a virtual environment

Keeping dependencies isolated avoids version conflicts with other Python projects.

**Windows (PowerShell or Git Bash):**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

You'll know it worked if your terminal prompt now starts with `(.venv)`.

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

This installs LangGraph, LangChain, the OpenAI and Groq clients, Streamlit, Pydantic, and the
other libraries listed in `requirements.txt`.

## 4. Configure your `.env` file

```bash
cp .env.example .env
```

Then open `.env` in a text editor and fill in **one** of the two provider paths:

**Option A -- Groq (free, recommended for trying it out):**
```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
```

**Option B -- OpenAI:**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk_your_key_here
```

Everything else in `.env.example` (`LLM_MODEL`, `LLM_TEMPERATURE`, `ENABLE_GROUNDING`,
`TAVILY_API_KEY`) is optional -- leave it as-is unless you know you want to change it. See the
README's [Environment Variables](../README.md#environment-variables) table for what each one does.

**Never commit your `.env` file.** It's already covered by `.gitignore`.

## 5. Verify the install (optional but recommended)

A quick sanity check that everything is wired up before opening the browser:

```bash
python -c "from workflow import build_graph; build_graph(); print('OK -- graph builds cleanly')"
```

If this prints `OK`, your dependencies and environment variables are set up correctly. If it
errors, re-check step 4 -- the most common cause is a missing or mistyped API key variable name.

## 6. Run the app

```bash
streamlit run app.py
```

Streamlit will print a local URL (usually `http://localhost:8501`) -- open it in your browser.
The app runs entirely locally; only the LLM calls go out to your chosen provider.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `OPENAI_API_KEY is not set` / `GROQ_API_KEY is not set` | `.env` wasn't created from `.env.example`, or `LLM_PROVIDER` doesn't match which key you filled in. |
| App shows a "Free usage limit reached" card | You've hit your provider's free-tier daily token quota. Wait for it to reset (the card shows an estimated time), or switch `LLM_PROVIDER` to a different provider in `.env`. |
| `Port 8501 is already in use` | Another Streamlit app is running. Run `streamlit run app.py --server.port 8502` instead, or stop the other process. |
| PDF download button doesn't appear | `fpdf2` failed to import or generate -- this is non-fatal; the `.txt`/`.md` downloads still work. Check `pip show fpdf2` installed correctly. |
| `ModuleNotFoundError` on startup | You're not inside the activated virtual environment, or `pip install -r requirements.txt` didn't complete. Re-run step 2-3. |
| Interview feels slow / questions take a while | Normal -- each question involves 1-2 LLM calls (Interviewer, then Evaluator). Groq is typically faster than OpenAI for this. |

## Next steps

- Read [`USER_GUIDE.md`](USER_GUIDE.md) for a walkthrough of the app's features.
- Read the main [`README.md`](../README.md) for the architecture, agent design, and prompt
  engineering behind the system.
