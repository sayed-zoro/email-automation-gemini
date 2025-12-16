# streamlit_app.py
import streamlit as st
import traceback
from pathlib import Path
from dotenv import load_dotenv
import os

# load .env for local debugging inside Streamlit
load_dotenv()

st.set_page_config(page_title="Email Automation", layout="centered")
st.title("Email Automation — Gemini (Google GenAI)")

# import backend functions
try:
    from email_automation import generate_email, send_via_smtp
except Exception as e:
    st.error("Could not import email_automation.py. Ensure the file is in the same folder and google-genai is installed.")
    st.exception(e)
    st.stop()

st.markdown("Use the template dropdown to generate professional emails. Requires GOOGLE_API_KEY in `.env`.")

# Inputs
to_email = st.text_input("To (recipient email)")
subject = st.text_input("Subject", value="Request for One Day Leave")
template = st.selectbox("Template", options=["leave_request", "meeting_request", "task_update"])
st.text("Context variables (one per line, key=value). Example: reason=personal")
context_raw = st.text_area("Context (optional)", height=100)
send_immediately = st.checkbox("Send email after generation (uses SMTP in .env)", value=False)

def parse_context(text: str):
    ctx={}
    for line in text.splitlines():
        line=line.strip()
        if not line: continue
        if "=" in line:
            k,v=line.split("=",1)
            ctx[k.strip()]=v.strip()
    return ctx

ctx = parse_context(context_raw)

col1, col2 = st.columns(2)
with col1:
    if st.button("Generate Email"):
        try:
            with st.spinner("Generating email..."):
                out = generate_email(subject, template, ctx)
            st.success("Generated")
            st.markdown("**Subject:**")
            st.code(out.get("subject", subject))
            st.markdown("**Message:**")
            st.text_area("Generated message", value=out.get("message",""), height=200, key="generated_msg")
            st.session_state["last_generated"] = out
        except Exception as e:
            st.error("Generation failed. See details below.")
            st.code(traceback.format_exc())

with col2:
    if st.button("Send Email (from last generated)"):
        if "last_generated" not in st.session_state:
            st.warning("No generated email found. Click 'Generate Email' first.")
        else:
            out = st.session_state["last_generated"]
            subj = out.get("subject", subject)
            msg = out.get("message", "")
            if not to_email:
                st.error("Please enter recipient email in the 'To' field.")
            else:
                try:
                    with st.spinner("Sending via SMTP..."):
                        send_via_smtp(to_email, subj, msg)
                    st.success(f"Email sent to {to_email}")
                except Exception as e:
                    st.error("Failed to send email. Make sure SMTP env vars are set.")
                    st.code(traceback.format_exc())

st.markdown("---")
st.info("Notes: make sure GOOGLE_API_KEY is set in .env and google-genai is installed.")
