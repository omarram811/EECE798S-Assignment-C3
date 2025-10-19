# Ramadan & Co. Writing Consultancy - Agent Bot

### C3 Assignment - Agent-Powered Business Assistant
### Omar Ramadan (AUB ID: 202204622) - EECE 798S (Agentic Systems)

A small, local-friendly AI agent that stays in character as **Ramadan & Co. Writing Consultancy**, answers questions grounded in your **summary** and **PDF**, and uses **tools** to (1) log leads and (2) capture unanswered questions. Comes with a Gradio chat UI and a CLI mode.

## Features

* **Business persona**: Warm, editorially precise, MENA-focused writing consultancy (Arabic/French/English).
* **Grounded answers**: Uses `me/business_summary.txt` and `me/about_business.pdf`.
* **Tool calls**:
  * `record_customer_interest(email, name, message)` → logs prospective leads to `logs/leads.jsonl`.
  * `record_feedback(question)` → logs questions the bot couldn’t answer to `logs/feedback.jsonl`.
* **Gradio interface** for demos + **CLI** mode for terminals.
* **Local-first**: Runs as a normal Python app (no notebook required). Configuration via `.env`.

## Project Structure
```
business_bot/
│
├── me/
│   ├── about_business.pdf        # About the company (grounding reference)
│   └── business_summary.txt      # Short summary (grounding reference)
│
├── app.py                        # Main application (UI/CLI, model, chat, tool routing)
├── tools.py                      # Tool implementations + tool schemas (Gemini format)
├── .env                          # API keys
└── requirements.txt              # Python dependencies
```

## Requirements

* Python 3.9+ (3.10/3.11 also fine)
* A valid **Gemini API key** from Google AI Studio
* Internet access for calling the Gemini API

Install dependencies:

```bash
pip install -r requirements.txt
```

`requirements.txt` includes:
```
google-generativeai>=0.7.0
pypdf>=4.2.0
python-dotenv>=1.0.1
gradio>=4.44.0
```

## Configuration (.env)

Create a `.env` file at the project root (which the app reads via `python-dotenv`):

```ini
# Required
GEMINI_API_KEY=YOUR_REAL_GEMINI_API_KEY_HERE

# Optional
# GEMINI_MODEL=gemini-2.5-flash   # default if unset
# LOG_DIR=/absolute/path/to/logs  # default: ./logs
```

## Running

### 1) Gradio UI (default)

```bash
python app.py
```

* Opens a web UI at `http://0.0.0.0:7860`. You can access it through `http://localhost:7860/`.
* Ask about services, workflows, timelines, etc.
* If you share your **email, name, and a brief**, the bot will call the **lead tool**.

#### Options

```bash
python app.py --model gemini-2.5-pro --server-port 8080
```

* `--model`: any model available to your key (e.g., `gemini-2.5-flash`, `gemini-2.5-pro`).
* `--server-name` and `--server-port`: customize Gradio hosting.

### 2) CLI Mode

```bash
python app.py --no-ui
```

Type messages in your terminal; responses print below.

## Tooling & Logs

When the bot calls a tool, data is logged to JSONL files:

* Leads → `logs/leads.jsonl`
* Feedback → `logs/feedback.jsonl`

**Example entries:**

```json
{"ts": "2025-10-18T21:16:49.972276+00:00", "event": "lead_recorded", "lead_id": "uuid-...", "email": "reader@example.com", "name": "Leila", "message": "debut novel, seeking agent"}
{"ts": "2025-10-18T21:18:10.002310+00:00", "event": "feedback_recorded", "feedback_id": "uuid-...", "question": "What’s your exact 2025 price list per service?"}
```

You can override the log directory using `.env`:

```ini
LOG_DIR=/path/to/custom/logs
```

## Grounding Data

* **`me/business_summary.txt`**: brief text summary of the business.
* **`me/about_business.pdf`**: longer-form "About" document.

The app **extracts text** from the PDF with `pypdf` and **injects both** into the system prompt. The assistant is instructed to answer **only** from these sources. If the info isn’t in these files, the assistant **must** call `record_feedback`.

> Tip: Keep these files up to date. If you update them, just restart the app.

## How the Agent Works (at a glance)

1. **System prompt** sets character & policy:

   * Warm, editorially precise, industry-savvy.
   * Answers must be grounded in `summary.txt` + `about_business.pdf`.
   * If unsure → **call `record_feedback`** (don’t guess).
   * If user wants services → collect **email, name, message**; then **call `record_customer_interest`**.

2. **Tool declarations** (Gemini format) tell the model what functions exist and when to use them.

3. **Tool dispatcher** in `app.py`:

   * Detects model `function_call` (name + args)
   * Calls the matching Python function (`tools.py`)
   * Sends `function_response` back to the model so it can continue its reply

## Quick Test Prompts

Use these to verify both tools:

* **Lead capture (should call `record_customer_interest`)**
  ```
  I'm interested in a query-letter package. Email: leila@example.com. Name: Leila. Message: debut novel seeking agent.
  ```

* **Unknown info (should call `record_feedback`)**
  ```
  What’s your exact 2025 price list per service (query letter, lyrics clinic, translation)?
  ```

Check `logs/` afterward to confirm entries.

## Customization

* **Business name**: in `app.py`, see `business_name = "Ramadan & Co. Writing Consultancy"`.
* **Model**: pass `--model` or set `GEMINI_MODEL` in `.env`.
* **Persona tone**: edit the `build_system_prompt()` template in `app.py`.
* **Tools**: extend/add new tools in `tools.py`, export declarations in `get_function_declarations()`, and register implementations in `TOOLS_MAP` (in `app.py`).

## Troubleshooting

* **`Missing GEMINI_API_KEY`**: Ensure `.env` exists and the key is correct. Re-run after any virtualenv activation.
* **Model not found**: Run `python app.py --model gemini-2.5-flash` (widely available) or check which models your key grants.
* **No tool calls happening**:

  * Ask for something not in your docs (e.g., a detailed rate card).
  * Ensure `get_function_declarations()` is used when creating the model.
* **Logs not writing**:

  * Confirm write permissions and `LOG_DIR` location.
  * The app prints compact lines to stdout (in addition to JSONL files).

## Privacy & Ethics

* The app collects **PII** only when you voluntarily provide it and only via approved tools.
* Logged data is stored locally in `logs/`. Handle it responsibly.
* The assistant gives **non-legal** guidance for rights/IP and refers legal matters to partner counsel.

## Assignment Mapping (for reference)

* **Part 1**: Business identity → `me/about_business.pdf` & `me/business_summary.txt`.
* **Part 2**: Tool functions → `tools.py` (`record_customer_interest`, `record_feedback`).
* **Part 3**: System prompt & grounding → `app.py` (`build_system_prompt`, file loaders).
* **Part 4**: Agent interaction → `app.py` (model init with tools, tool dispatcher, `ask()`).
* **Part 5**: Gradio interface → `app.py` (`build_ui()`).

## HuggingFace Spaces
Please consult the following link for the HuggingFace deployment of the application: `https://huggingface.co/spaces/omarram010/eece798s_assignment_c3`. Make sure to set the API key as a Space Secret by doing the following steps:

In your Space:
- Go to **Settings** → **Variables and secrets**
- Add a **Secret**:
    - Name: `GEMINI_API_KEY`
    - Value: your key
- (Optional) Add `GEMINI_MODEL` **variable** (e.g., `gemini-2.5-flash`).
