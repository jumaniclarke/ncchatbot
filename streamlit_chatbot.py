# streamlit_chatbot.py
import streamlit as st
import spacy
from spacy.matcher import Matcher
import re
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from nltk.corpus import wordnet
from spacy import displacy
from pandas_automation import get_base
from streamlit_google_auth import Authenticate
# ------------------------------------
# Page config
# ------------------------------------
st.set_page_config(page_title="Stats Chatbot — Percentage Interpretation", layout="wide")

# ------------------------------------
# Google Authentication
# ------------------------------------
# Initialize authentication
authenticator = Authenticate(
    secret_credentials_path='google_credentials.json',
    cookie_name='streamlit_auth_cookie',
    cookie_key='streamlit_auth_key',
    redirect_uri='http://localhost:8501',
)

# Check authentication
authenticator.check_authentification()

# Show login button if not authenticated
if not st.session_state['connected']:
    st.title("Statistics Chatbot")
    st.markdown("### Please sign in with your Google account to continue")
    authenticator.login()
    st.stop()  # Stop execution if not authenticated

# Show logout button in sidebar if authenticated
with st.sidebar:
    st.write(f"**Logged in as:** {st.session_state['user_info'].get('email', 'Unknown')}")
    if st.button('Logout'):
        authenticator.logout()

# ------------------------------------
# NLP setup
# ------------------------------------
@st.cache_resource
def load_nlp():
    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        try:
            from spacy.cli import download
            download("en_core_web_sm")
            return spacy.load("en_core_web_sm")
        except Exception:
            # Fallback to md if sm fails to download in some environments
            return spacy.load("en_core_web_md")
nlp = load_nlp()

@st.cache_resource
def build_matchers(_nlp):
    matcher = Matcher(_nlp.vocab)
    matcher.add("PERCENT_MENTION", [[{"LIKE_NUM": True}, {"TEXT": "%"}]])
    matcher.add("COMPARATIVE", [[{"LEMMA": {"IN": ["more", "less", "greater", "lower", "higher"]}}]])
    matcher.add("CAUSAL", [[{"LEMMA": {"IN": ["cause", "lead", "result"]}}]])
    matcher.add("HEDGING", [[{"LOWER": {"IN": ["might", "may", "appears", "seems", "suggests"]}}]])
    return matcher

matcher = build_matchers(nlp)

# ------------------------------------
# Task definitions
# ------------------------------------
TASKS = [
    {
        "id": "task1",
        "title": "Task 1: Bar chart — category frequency (%)",
        "description": "Describe the meaning of the percentage for the highlighted category.",
        "chart_type": "bar",
        "data": pd.DataFrame({"Category": ["A", "B", "C", "D"], "Percent": [25, 40, 20, 15]}),
        "highlight": "B",
        "expected": {
            "text": "Category B accounts for 40% of the observations; i.e., 40 out of every 100 items fall into Category B.",
            "percent": 40,
            "units": "%",
            "category": "B"
        }
    },
    {
        "id": "task2",
        "title": "Task 2: Pie chart — segment share (%)",
        "description": "Explain what the percentage means for the selected segment.",
        "chart_type": "pie",
        "data": pd.DataFrame({"Segment": ["East", "West", "North", "South"], "Percent": [30, 25, 15, 30]}),
        "highlight": "East",
        "expected": {
            "text": "The East region represents 30% of the total, meaning 30 out of every 100 observations come from East.",
            "percent": 30,
            "units": "%",
            "category": "East"
        }
    },
    {
        "id": "task3",
        "title": "Task 3: Stacked bar chart — subcategory proportion (%)",
        "description": "Interpret the percentage of the subcategory within a stacked bar.",
        "chart_type": "stacked_bar",
        "data": pd.DataFrame({
            "Group": ["G1", "G2"],
            "Subcategory": ["Correct", "Incorrect"],
            "G1": [60, 40],
            "G2": [35, 65]
        }),
        "highlight": {"Group": "G2", "Subcategory": "Correct"},
        "expected": {
            "text": "Within Group G2, 35% are labeled Correct, meaning 35 out of 100 items in G2 are Correct.",
            "percent": 35,
            "units": "%",
            "group": "G2",
            "subcategory": "Correct"
        }
    }
]

# ------------------------------------
# Chart renderers
# ------------------------------------
def render_chart(task):
    fig, ax = plt.subplots(figsize=(5, 3.5))
    if task["chart_type"] == "bar":
        df = task["data"]
        ax.bar(df["Category"], df["Percent"], color=["C0" if c != task["highlight"] else "C3" for c in df["Category"]])
        ax.set_ylabel("Percent (%)")
        ax.set_title("Bar chart of percent by category")
        for i, p in enumerate(df["Percent"]):
            ax.text(i, p + 1, f"{p}%", ha="center")
    elif task["chart_type"] == "pie":
        df = task["data"]
        colors = ["C3" if seg == task["highlight"] else "C0" for seg in df["Segment"]]
        ax.pie(df["Percent"], labels=df["Segment"], autopct="%1.0f%%", colors=colors)
        ax.set_title("Pie chart of percent by segment")
    elif task["chart_type"] == "stacked_bar":
        df = task["data"]
        groups = df["Group"].unique().tolist()  # ["G1","G2"]
        subcats = df["Subcategory"].unique().tolist()  # ["Correct","Incorrect"]
        width = 0.5
        g1_vals = df["G1"].values
        g2_vals = df["G2"].values
        # Stacked bars
        ax.bar([0], g1_vals[0], width, label=subcats[0], color="C0")
        ax.bar([0], g1_vals[1], width, bottom=g1_vals[0], label=subcats[1], color="C1")
        ax.bar([1], g2_vals[0], width, color="C0")
        ax.bar([1], g2_vals[1], width, bottom=g2_vals[0], color="C1")
        ax.set_xticks([0, 1])
        ax.set_xticklabels(groups)
        ax.set_ylabel("Percent within group (%)")
        ax.set_title("Stacked bar: subcategory proportions by group")
        focus = task["highlight"]
        if focus["Group"] == "G2" and focus["Subcategory"] == "Correct":
            ax.scatter([1], [g2_vals[0]], s=400, facecolors='none', edgecolors='C3', linewidths=2)
        ax.legend(loc="upper right")
    buf = BytesIO()
    plt.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return buf

# ------------------------------------
# Analysis & feedback
# ------------------------------------
def extract_percentages(text):
    nums = []
    for m in re.finditer(r"(\d+(\.\d+)?)\s*(%|percent|percentage)", text.lower()):
        nums.append(float(m.group(1)))
    return nums

def grammar_checks(doc):
    issues = []
    if re.search(r"\bdata is\b", doc.text.lower()):
        issues.append("Consider using 'data are' in formal statistical writing (if your style guide prefers plural).")
    for sent in doc.sents:
        if not any(t.pos_ in ("VERB", "AUX") for t in sent):
            issues.append(f"Possible fragment: '{sent.text.strip()}'. Add a verb for a complete sentence.")
        if len(sent) > 40 and not any(t.text in [",", ";", "—"] for t in sent):
            issues.append("Long sentence detected; consider splitting for clarity.")
    return issues

def analyze_text(user_text, task):
    doc = nlp(user_text.strip())
    hits = matcher(doc)
    match_labels = set(nlp.vocab.strings[m_id] for m_id, s, e in hits)
    exp = task["expected"]
    
    # feeback about the base
    base_msgs = []
    thebase = get_base(user_text)
    if thebase:
        base_msgs.append(f"✅ You mentioned the base as '{thebase}'.")
    else:
        base_msgs.append("ℹ️ Consider mentioning the base (e.g., 'out of 100 observations') for clarity.")

    # Percent correctness
    percents = extract_percentages(doc.text)
    tol = 1.0
    percent_msgs = []
    if percents:
        if any(abs(p - exp["percent"]) <= tol for p in percents):
            chosen = min(percents, key=lambda p: abs(p-exp['percent']))
            percent_msgs.append(f"✅ Your percentage ({round(chosen,2)}%) matches the chart value ({exp['percent']}%).")
        else:
            closest = min(percents, key=lambda p: abs(p-exp['percent']))
            percent_msgs.append(f"❌ The mentioned percentage ({closest}%) does not match the chart value ({exp['percent']}%). Re-check the highlighted part.")
    else:
        percent_msgs.append("ℹ️ Try stating the percentage explicitly (e.g., '40%').")

    # Unit presence
    unit_msgs = ["✅ You included percentage units, good."] if ("%" in doc.text or re.search(r"\bpercent(age)?\b", doc.text.lower())) \
                else ["ℹ️ Include units (e.g., '%') to make your statement precise."]

    # Category/group references
    cat_msgs = []
    if task["chart_type"] in ("bar", "pie"):
        cat = exp["category"]
        if re.search(rf"\b{re.escape(cat.lower())}\b", doc.text.lower()):
            cat_msgs.append(f"✅ You referenced the correct category (‘{cat}’).")
        else:
            cat_msgs.append(f"ℹ️ Mention the category name (‘{cat}’) to make the claim explicit.")
    else:  # stacked_bar
        grp = exp["group"]; sub = exp["subcategory"]
        has_grp = re.search(rf"\b{re.escape(grp.lower())}\b", doc.text.lower())
        has_sub = re.search(rf"\b{re.escape(sub.lower())}\b", doc.text.lower())
        if has_grp and has_sub:
            cat_msgs.append(f"✅ You referenced both the group (‘{grp}’) and subcategory (‘{sub}’).")
        else:
            missing = []
            if not has_grp: missing.append(f"group ‘{grp}’")
            if not has_sub: missing.append(f"subcategory ‘{sub}’")
            cat_msgs.append("ℹ️ Please mention " + " and ".join(missing) + " explicitly.")

    # Language use
    lang_msgs = []
    if "CAUSAL" in match_labels:
        lang_msgs.append("⚠️ Avoid causal language when interpreting descriptive charts. Prefer phrasing like ‘represents’, ‘accounts for’, or ‘share of’.")
    if "HEDGING" in match_labels:
        lang_msgs.append("✅ Hedging language detected. Neutral phrasing is fine; ensure clarity about what the percentage represents.")

    # Grammar
    gram_msgs = grammar_checks(doc)

    return {
        "Content Accuracy": percent_msgs + cat_msgs,
        "Units & Precision": unit_msgs,
        "Language Use": lang_msgs,
        "Grammar & Clarity": gram_msgs,
        "The base you gave": base_msgs
    }

# ------------------------------------
# Session state (chat)
# ------------------------------------
def init_state():
    # Check URL parameters for task parameter
    query_params = st.query_params
    task_param = query_params.get("task", None)
    
    if "task_index" not in st.session_state:
        # Initialize based on URL parameter if provided
        if task_param:
            try:
                task_num = int(task_param)
                if 1 <= task_num <= len(TASKS):
                    st.session_state.task_index = task_num - 1  # Convert to 0-based index
                else:
                    st.session_state.task_index = 0
            except (ValueError, TypeError):
                st.session_state.task_index = 0
        else:
            st.session_state.task_index = 0
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []  # list of dicts: {role: "user"/"assistant", text: str, task_id: str}
    if "started" not in st.session_state:
        st.session_state.started = False

init_state()

def current_task():
    return TASKS[st.session_state.task_index]

# ------------------------------------
# Assistant helpers
# ------------------------------------
def assistant_say(text, task_id=None, allow_markdown=True):
    with st.chat_message("assistant"):
        if allow_markdown:
            st.markdown(text)
        else:
            st.write(text)
    st.session_state.chat_history.append({"role": "assistant", "text": text, "task_id": task_id or current_task()["id"]})

def user_say(text, task_id=None):
    with st.chat_message("user"):
        st.markdown(text)
    st.session_state.chat_history.append({"role": "user", "text": text, "task_id": task_id or current_task()["id"]})

def show_chart_in_chat(task):
    chart = render_chart(task)
    with st.chat_message("assistant"):
        st.image(chart, caption=task["title"], width=400)
    st.session_state.chat_history.append({"role": "assistant", "text": f"[Chart displayed: {task['title']}]", "task_id": task["id"]})

def show_quick_replies():
    cols = st.columns([1,1,1,1])
    with cols[0]:
        st.button("Model exemplar", key=f"exemplar_{st.session_state.task_index}", on_click=lambda: assistant_say(f"**Exemplar:** {current_task()['expected']['text']}", current_task()["id"]))
    with cols[1]:
        st.button("Remind prompt", key=f"remind_{st.session_state.task_index}", on_click=lambda: assistant_say(current_task()["description"], current_task()["id"]))
    with cols[2]:
        st.button("Show chart again", key=f"chart_{st.session_state.task_index}", on_click=lambda: show_chart_in_chat(current_task()))
    with cols[3]:
        can_advance = st.session_state.task_index < len(TASKS)-1
        st.button("Next task →", key=f"next_{st.session_state.task_index}", disabled=not can_advance, on_click=advance_task)

def advance_task():
    if st.session_state.task_index < len(TASKS)-1:
        st.session_state.task_index += 1
        t = current_task()
        assistant_say(f"**{t['title']}**\n\n{t['description']}", t["id"])
        show_chart_in_chat(t)

def jump_to_task(task_index):
    """Jump to a specific task by index"""
    if 0 <= task_index < len(TASKS):
        st.session_state.task_index = task_index
        t = current_task()
        assistant_say(f"**{t['title']}**\n\n{t['description']}", t["id"])
        show_chart_in_chat(t)

# ------------------------------------
# UI header
# ------------------------------------
st.title("Statistics Chatbot")
st.caption("Describe the meaning of a percentage frequency for the highlighted part of each chart. I'll respond with targeted feedback.")

# Task navigation links
st.markdown("**Jump to task:**")
cols = st.columns(3)
for i, task in enumerate(TASKS):
    with cols[i]:
        is_current = (i == st.session_state.task_index)
        button_label = f"{'✓ ' if is_current else ''}{task['title'].split(':')[0]}"
        if st.button(button_label, key=f"nav_task_{i}", disabled=is_current, use_container_width=True):
            jump_to_task(i)
            st.rerun()
st.markdown("---")

# ------------------------------------
# Boot: greet and show first chart
# ------------------------------------
if not st.session_state.started:
    t = current_task()
    st.session_state.chat_history.append({"role": "assistant", "text": f"Hi! Let's start with **{t['title']}**.\n\n{t['description']}", "task_id": t["id"]})
    st.session_state.chat_history.append({"role": "assistant", "text": f"[Chart displayed: {t['title']}]", "task_id": t["id"]})
    st.session_state.chat_history.append({"role": "assistant", "text": "When you're ready, type your description (e.g., *'Category B accounts for 40% of the total...'*).", "task_id": t["id"]})
    st.session_state.started = True
    st.rerun()

# ------------------------------------
# Replay chat history
# ------------------------------------
for msg in st.session_state.chat_history:
    if msg["text"].startswith("[Chart displayed:"):
        # Find the task by looking through TASKS
        task_for_chart = next((task for task in TASKS if task["id"] == msg["task_id"]), current_task())
        chart = render_chart(task_for_chart)
        with st.chat_message("assistant"):
            st.image(chart, caption=task_for_chart["title"], width=400)
    else:
        with st.chat_message(msg["role"]):
            st.markdown(msg["text"])

# Quick helpers under the thread
show_quick_replies()

# ------------------------------------
# Chat input
# ------------------------------------
prompt = st.chat_input("Write your description here…")
if prompt:
    # Route to current task
    t = current_task()
    user_say(prompt, t["id"])
    # Analyze and reply with structured feedback
    fb = analyze_text(prompt, t)

    # Compose assistant reply (chat-friendly)
    bullet = []
    for sec, items in fb.items():
        if items:
            bullet.append(f"**{sec}**")
            bullet.extend([f"- {i}" for i in items])
    
    # Debug: check what's in fb
    st.write("DEBUG - Feedback sections:", list(fb.keys()))
    st.write("DEBUG - Base msgs:", fb.get("The base you gave", []))
    
    reply = "\n".join(bullet) if bullet else "Thanks! I didn't find any specific issues. If you'd like, I can show the exemplar."
    assistant_say(reply, t["id"]) 

    # Offer the exemplar automatically if incorrect percentage detected
    incorrect = any("❌" in m for m in fb["Content Accuracy"])
    if incorrect:
        assistant_say(f"Would you like to see an exemplar for this task?\n\n**Exemplar:** {t['expected']['text']}", t["id"])
