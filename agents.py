"""The team. A Manager (Groq LLM with tools) directs 6 specialist 'workers'.

Workers (delegated via tools):
  Researcher -> web_research / browse
  Doc-maker  -> make_pdf / make_docx
  Data/Excel -> make_xlsx
  Mailer     -> read_inbox / send_email (confirmation-gated)
  WhatsApp   -> whatsapp_send (confirmation-gated)
"""
import json
from openai import OpenAI

from app.config import config
from app import tools, db

llm = OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)

SYSTEM = """You are the Manager of Sachin's 24/7 backend office team.
You receive a command and get the work done by calling tools (your workers).
Rules:
- Break big commands into steps; use the right worker for each.
- Save every document you create; report the file path back.
- For research prefer web_research; use browse for a specific URL.
- NEVER send an email or WhatsApp directly if confirmation is required —
  instead call queue_for_confirmation so Sachin can approve.
- Reply in short, clear Hinglish. End with a one-line status per sub-task."""


def _fn(name, desc, props, required):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props, "required": required}}}


TOOLS = [
    _fn("web_research", "Research a topic on the web and get a sourced summary.",
        {"query": {"type": "string"}}, ["query"]),
    _fn("browse", "Open a specific URL in Chrome and read its text.",
        {"url": {"type": "string"}, "instruction": {"type": "string"}}, ["url"]),
    _fn("make_pdf", "Create a PDF document.",
        {"title": {"type": "string"}, "body": {"type": "string"}}, ["title", "body"]),
    _fn("make_docx", "Create a Word document.",
        {"title": {"type": "string"}, "body": {"type": "string"}}, ["title", "body"]),
    _fn("make_xlsx", "Create an Excel sheet. rows = array of arrays, first row headers.",
        {"title": {"type": "string"}, "rows": {"type": "array", "items": {"type": "array"}}}, ["title", "rows"]),
    _fn("read_inbox", "Read the latest N emails from the inbox.",
        {"n": {"type": "integer"}}, []),
    _fn("send_email", "Send an email immediately (only if allowed).",
        {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}}, ["to", "subject", "body"]),
    _fn("whatsapp_send", "Send a WhatsApp message immediately (only if allowed).",
        {"to": {"type": "string"}, "text": {"type": "string"}}, ["to", "text"]),
    _fn("queue_for_confirmation", "Queue an email/whatsapp for Sachin's approval instead of sending now.",
        {"kind": {"type": "string", "enum": ["email", "whatsapp"]},
         "payload": {"type": "object"}, "summary": {"type": "string"}}, ["kind", "payload", "summary"]),
]


def _run_tool(name, args):
    if name == "web_research":
        return tools.web_research(args["query"])
    if name == "browse":
        return tools.browse(args["url"], args.get("instruction", ""))
    if name == "make_pdf":
        return f"PDF saved: {tools.make_pdf(args['title'], args['body'])}"
    if name == "make_docx":
        return f"DOCX saved: {tools.make_docx(args['title'], args['body'])}"
    if name == "make_xlsx":
        return f"XLSX saved: {tools.make_xlsx(args['title'], args['rows'])}"
    if name == "read_inbox":
        return tools.read_inbox(int(args.get("n", 5)))
    if name == "send_email":
        if config.REQUIRE_CONFIRMATION:
            db.add_pending("email", args, f"Email to {args.get('to')}: {args.get('subject')}")
            return "Confirmation required — email queued (not sent)."
        return tools.send_email(args["to"], args["subject"], args["body"])
    if name == "whatsapp_send":
        if config.REQUIRE_CONFIRMATION:
            db.add_pending("whatsapp", args, f"WhatsApp to {args.get('to')}")
            return "Confirmation required — whatsapp queued (not sent)."
        return tools.whatsapp_send(args["to"], args["text"])
    if name == "queue_for_confirmation":
        db.add_pending(args["kind"], args["payload"], args["summary"])
        return "Queued for your approval."
    return f"[unknown tool {name}]"


def run_command(command: str, max_steps: int = 12) -> str:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": command},
    ]
    final = []
    for _ in range(max_steps):
        resp = llm.chat.completions.create(
            model=config.MODEL, max_tokens=2000,
            messages=messages, tools=TOOLS, tool_choice="auto",
        )
        msg = resp.choices[0].message
        if msg.content:
            final.append(msg.content.strip())

        if not msg.tool_calls:
            break

        # record assistant turn with its tool calls
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })
        # run each tool, append results
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = _run_tool(tc.function.name, args)
            messages.append({
                "role": "tool", "tool_call_id": tc.id, "content": str(result),
            })

    return "\n".join(final).strip() or "(done)"
