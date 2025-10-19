from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
import google.generativeai as genai
from pypdf import PdfReader
import gradio as gr

# Local imports
from tools import (LOG_DIR, record_customer_interest, record_feedback, get_function_declarations )

BASE_DIR = Path(__file__).resolve().parent
ME_DIR = BASE_DIR / "me"
SUMMARY_PATH = ME_DIR / "business_summary.txt"
PDF_PATH = ME_DIR / "about_business.pdf"

def load_env() -> str:
    """
    Load .env and return GEMINI API key (or raise if missing).
    """
    load_dotenv()  # loads .env in current directory
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY. Create a .env file with e.g. GEMINI_API_KEY=sk-xxxxx")
    return api_key

def read_pdf_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""
    parts: List[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            parts.append("")
    return "\n".join(parts).strip()

def load_business_knowledge() -> tuple[str, str]:
    summary = ""
    pdf_text = ""
    if SUMMARY_PATH.exists():
        summary = SUMMARY_PATH.read_text(encoding="utf-8")
    else:
        print(f"[warn] Missing summary file: {SUMMARY_PATH}")
    pdf_text = read_pdf_text(PDF_PATH)
    if not pdf_text:
        print(f"[warn] PDF text empty or PDF missing: {PDF_PATH}")
    # Optional truncation
    MAX_CHARS = 60_000
    if len(pdf_text) > MAX_CHARS:
        pdf_text = pdf_text[:MAX_CHARS] + "\n[...truncated...]"
    return summary, pdf_text

def build_system_prompt(business_name: str, summary: str, pdf_text: str) -> str:
    return f"""
    You are the in-house agent for {business_name}, a Beirut-rooted, tri-lingual (Arabic/French/English) writing consultancy.
    Your job is to provide clear, helpful, and contract-savvy guidance to authors, poets, screenwriters, and songwriters.

    AUTHORITATIVE BUSINESS KNOWLEDGE (use this to answer; do NOT invent facts):
    --- SUMMARY.txt ---
    {summary}

    --- ABOUT_BUSINESS.pdf (OCR/extracted) ---
    {pdf_text}

    OPERATING RULES:
    1) Stay in character as {business_name}. Tone: warm, professional, editorially precise, industry-savvy.
    2) Ground every factual answer in the BUSINESS KNOWLEDGE above. If the user asks for anything not covered or you're unsure:
    - Do NOT guess.
    - Call the tool: record_feedback(question="<the exact user question or the missing info you need>").
    - After calling the tool, tell the user we have logged this and will follow up once we have the answer.
    3) Lead capture: if the user expresses interest (services, pricing, timelines, availability, briefs, pitches, “how to start”, etc.),
    - Politely invite their name + email and a short note about their project.
    - When you have email, name, and message, call: record_customer_interest(email, name, message).
    - If any field is missing, ask concisely for it before calling the tool.
    4) Keep privacy in mind. Only store PII via the approved tools upon user consent/intent.
    5) Language: default to English; if the user speaks Arabic or French, switch or mix naturally while keeping clarity.
    6) Be concise, structured, and actionable. Offer next steps (e.g., “sample pages needed”, “query package”, “lyrics brief”, etc.).
    """.strip()

def configure_model(api_key: str, system_prompt: str, model_name: str = "gemini-2.5-flash"):
    genai.configure(api_key=api_key)
    tools = [{"function_declarations": get_function_declarations()}]
    model = genai.GenerativeModel(model_name=model_name, system_instruction=system_prompt, tools=tools)
    chat = model.start_chat(history=[])
    return model, chat

TOOLS_MAP = {"record_customer_interest": record_customer_interest, "record_feedback": record_feedback}

def _run_tools_if_any(chat, resp):
    """
    Execute any function calls present in `resp`. Feed function_response back to the same chat.
    Loop until the model stops requesting tools. Return the final response (with no function_call).
    """
    while True:
        called_any = False
        cand = resp.candidates[0]
        parts = list(getattr(cand.content, "parts", []) or [])
        for part in parts:
            fc = getattr(part, "function_call", None)
            if not fc:
                continue
            called_any = True
            name = fc.name
            args = dict(fc.args or {})
            fn = TOOLS_MAP.get(name)
            if not fn:
                tool_result = {"ok": False, "error": f"unknown_tool:{name}", "received_args": args}
            else:
                try:
                    tool_result = fn(**args)
                except TypeError as e:
                    tool_result = {"ok": False, "error": f"bad_arguments:{e}", "received_args": args}
                except Exception as e:
                    tool_result = {"ok": False, "error": f"runtime:{e.__class__.__name__}:{e}"}

            resp = chat.send_message({
                "role": "tool",
                "parts": [{
                    "function_response": {
                        "name": name,
                        "response": tool_result
                    }
                }]
            })
        if not called_any:
            return resp

def ask(chat, user_text: str) -> str:
    """
    Send user_text to the chat, execute tool calls if requested, and return final text.
    """
    resp = chat.send_message(user_text)
    final = _run_tools_if_any(chat, resp)
    try:
        return final.text
    except Exception:
        cand = final.candidates[0]
        return "\n".join(getattr(p, "text", "") for p in cand.content.parts if hasattr(p, "text"))

def reset_chat(model):
    return model.start_chat(history=[])

# Gradio UI
def build_ui(model, chat):
    def on_send(message, history):
        try:
            reply = ask(chat, message)
        except Exception as e:
            reply = f"Sorry—something went wrong: {e}"
        history = (history or []) + [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
        return history, ""

    with gr.Blocks(fill_height=True) as demo:
        gr.Markdown("### Ramadan & Co. - Writing Consultancy Agent")
        gr.Markdown("Ask about services, workflows, or leave your details to get matched with a writer.")

        try:
            chat_ui = gr.Chatbot(type="messages", height=500)
        except TypeError:
            chat_ui = gr.Chatbot(height=500)  # fallback for older Gradio

        msg  = gr.Textbox(placeholder="Type your message…", autofocus=True, scale=1)
        send = gr.Button("Send", variant="primary")
        reset_btn = gr.Button("Reset conversation", variant="secondary")

        msg.submit(on_send, [msg, chat_ui], [chat_ui, msg])
        send.click(on_send, [msg, chat_ui], [chat_ui, msg])

        def _reset():
            nonlocal chat
            chat = reset_chat(model)
            return []

        reset_btn.click(_reset, outputs=[chat_ui])

    return demo

# CLI loop
def run_cli(chat):
    print("Type your message (or 'exit'): ")
    while True:
        try:
            text = input("> ").strip()
        except EOFError:
            break
        if not text or text.lower() in {"exit", "quit"}:
            break
        print(ask(chat, text))

def main():
    parser = argparse.ArgumentParser(description="Ramadan & Co. Writing Consultancy Agent")
    parser.add_argument("--model", default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), help="Gemini model name (default: gemini-2.5-flash)")
    parser.add_argument("--no-ui", action="store_true", help="Run in CLI mode (no Gradio UI)")
    parser.add_argument("--server-name", default="0.0.0.0", help="Gradio server_name")
    parser.add_argument("--server-port", type=int, default=7860, help="Gradio server_port")
    args = parser.parse_args()

    api_key = load_env()
    summary, pdf_text = load_business_knowledge()
    business_name = "Ramadan & Co. Writing Consultancy"
    system_prompt = build_system_prompt(business_name, summary, pdf_text)

    model, chat = configure_model(api_key, system_prompt, model_name=args.model)

    if args.no_ui:
        print("Running in CLI mode. Logs dir:", LOG_DIR)
        run_cli(chat)
    else:
        demo = build_ui(model, chat)
        try:
            demo.queue(concurrency_count=1, max_size=16)
        except TypeError:
            try:
                demo.queue(max_size=16)
            except TypeError:
                demo.queue()
        demo.launch(server_name=args.server_name, server_port=args.server_port, share=False, debug=False)

if __name__ == "__main__":
    main()
