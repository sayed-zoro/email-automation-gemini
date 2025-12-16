# email_automation.py
"""
Email automation backend (Gemini + SMTP).
Provides generate_email(subject, template_key, context) and send_via_smtp(...)
Safe to import into Streamlit (CLI run only when called as script).
"""
import os
import smtplib
from email.message import EmailMessage
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT") or 587)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
DEFAULT_SENDER_NAME = os.getenv("DEFAULT_SENDER_NAME") or "Aqib"

if not GOOGLE_API_KEY:
    raise RuntimeError("Set GOOGLE_API_KEY in your .env before running (Google GenAI key)")

# Import google-genai SDK
try:
    from google import genai
    from google.genai import types
except Exception as e:
    raise ImportError("google-genai SDK required. Run: pip install google-genai") from e

# Create client
client = genai.Client(api_key=GOOGLE_API_KEY)

# Few-shot examples and templates
FEW_SHOT_EXAMPLES = [
    {
        "subject": "Request for Meeting",
        "message": "I hope you're doing well. I would like to schedule a meeting tomorrow to discuss the progress of our current project.\n\nRegards,\nAqib"
    },
    {
        "subject": "Update on Task",
        "message": "This is to inform you that I have completed the assigned task and shared the required documents.\n\nRegards,\nAqib"
    }
]

TEMPLATES = {
    "leave_request": {
        "instruction": "Using the professional email format shown in the examples, write a short, 2-4 line email requesting one day of leave tomorrow. Keep it polite and concise.",
        "placeholders": ["reason", "date"]
    },
    "meeting_request": {
        "instruction": "Using the professional email format shown in the examples, write an email requesting to schedule a meeting to discuss project progress. Suggest two time slots.",
        "placeholders": ["timeslots"]
    },
    "task_update": {
        "instruction": "Using the professional email format shown in the examples, write a short update informing that the assigned task is complete and attachments were shared.",
        "placeholders": []
    }
}

def build_prompt(subject: str, template_key: str, context: Dict[str,str]={}) -> str:
    prompt = "You are a helpful assistant that writes professional emails. Follow the exact format in the examples.\n\n"
    for ex in FEW_SHOT_EXAMPLES:
        prompt += f"Subject: {ex['subject']}\nMessage:\n{ex['message']}\n\n"
    prompt += f"Now write a new email.\nSubject: {subject}\n"
    template = TEMPLATES.get(template_key)
    if not template:
        raise ValueError(f"Unknown template: {template_key}")
    prompt += "Message:\n" + template['instruction']
    if context:
        prompt += "\nContext:"
        for k,v in context.items():
            prompt += f" {k}={v};"
    prompt += "\n\nRespond only with the email in the exact format: Subject: <...>\nMessage:\n<...>\nRegards,\nAqib"
    return prompt

def _call_gemini_chat(prompt: str, model: str='gemini-2.5-flash', max_tokens: int=512, temperature: float=0.2) -> str:
    """Call Google GenAI (Gemini) and return the assistant text."""
    # Use models.generate_content
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens)
    )
    # Try to extract textual output
    text = getattr(resp, "text", None)
    if not text:
        try:
            cand = resp.candidates[0]
            text = getattr(cand, "text", None) or getattr(cand, "content", None) or str(cand)
        except Exception:
            text = str(resp)
    return text or ""

def generate_email(subject: str, template_key: str, context: Dict[str,str]={}, model: str='gemini-2.5-flash') -> Dict[str,str]:
    prompt = build_prompt(subject, template_key, context)
    content = _call_gemini_chat(prompt, model=model, max_tokens=300, temperature=0.2)
    content = content.strip() if isinstance(content, str) else str(content).strip()
    parsed = {"subject": subject, "message": content}
    if content.lower().startswith('subject:'):
        lower = content.lower()
        idx = lower.find('\nmessage:\n')
        if idx != -1:
            subj_block = content[:idx]
            msg_block = content[idx + len('\nmessage:\n'):]
        else:
            parts = content.split('\nMessage:\n', 1)
            if len(parts) == 2:
                subj_block, msg_block = parts
            else:
                subj_block = subject
                msg_block = content
        subj = subj_block.replace('Subject:', '').strip()
        msg = msg_block.strip()
        parsed['subject'] = subj
        parsed['message'] = msg
    return parsed

def send_via_smtp(to_email: str, subject: str, message_body: str, sender_display_name: str=DEFAULT_SENDER_NAME) -> None:
    if not SMTP_SERVER or not SMTP_USER or not SMTP_PASS:
        raise RuntimeError("SMTP settings missing in .env (SMTP_SERVER/SMTP_USER/SMTP_PASS).")
    msg = EmailMessage()
    msg['From'] = f"{sender_display_name} <{SMTP_USER}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content(message_body)
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.send_message(msg)

# Allow CLI use safely
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate and optionally send professional emails via Gemini")
    parser.add_argument('--to', required=True, help='Recipient email address')
    parser.add_argument('--subject', required=True, help='Email subject')
    parser.add_argument('--template', default='leave_request', help='Template key')
    parser.add_argument('--send', action='store_true', help='If provided, actually send via SMTP')
    parser.add_argument('--context', nargs='*', help='Optional context vars key=value')
    args = parser.parse_args()
    context = {}
    if args.context:
        for kv in args.context:
            if '=' in kv:
                k,v = kv.split('=',1)
                context[k]=v
    out = generate_email(args.subject, args.template, context)
    print("Subject:", out['subject'])
    print("Message:\n", out['message'])
    if args.send:
        send_via_smtp(args.to, out['subject'], out['message'])
        print("Email sent to", args.to)
