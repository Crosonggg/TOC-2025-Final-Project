import re
import time
import html
import json
import requests
import streamlit as st

# ===========================
# 設定
# ===========================
def get_api_key():
    try:
        with open("API.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

API_KEY = get_api_key()
BASE_URL = "https://api-gateway.netdb.csie.ncku.edu.tw"
MODEL_NAME = "gpt-oss:120b"
MAX_HISTORY_TURNS = 8

SYSTEM_PROMPT = (
    "你是一位親切且務實的家庭主婦主廚助理。"
    "你會根據使用者提供的食材、偏好與限制（例如：不能吃辣、想清淡、要快速）"
    "推薦一道菜並提供可操作的詳細步驟。"
    "重要：絕對不要輸出 Markdown/HackMD 表格（不要出現 |---| 或 | 欄位 |）。"
    "食譜請以 JSON 輸出（會在提示中給你結構），不要多餘文字、不要 markdown。"
    "重要 : 全部都以繁體中文輸出。"
)

# ===========================
# UI：泡泡 + 底部固定輸入列
# ===========================
def inject_ui_css():
    st.markdown(
        """
<style>
.block-container{
  max-width: 880px;
  padding-top: 2.0rem !important;
  padding-bottom: 10rem !important;
}
.chat-wrap{
  display:flex;
  flex-direction:column;
  gap: 12px;
  margin-top: 0.6rem;
}
.bubble{
  max-width: 82%;
  padding: 10px 14px;
  border-radius: 16px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: 0 2px 10px rgba(0,0,0,0.06);
  font-size: 0.98rem;
}
.bubble.user{ align-self:flex-end; background:#DCF8C6; }
.bubble.assistant{ align-self:flex-start; background:#F3F4F6; }
@media (prefers-color-scheme: dark) {
  .bubble.user{ background:#1f6f43; color:#fff; }
  .bubble.assistant{ background:#2A2A2A; color:#fff; }
}
.bubble h3, .bubble h4{ margin: 0.2rem 0 0.35rem 0; }
.bubble hr{
  margin: 0.65rem 0;
  border: none;
  border-top: 1px solid rgba(0,0,0,0.08);
}
@media (prefers-color-scheme: dark) {
  .bubble hr{ border-top: 1px solid rgba(255,255,255,0.12); }
}

.table{
  width: 100%;
  border-collapse: collapse;
  margin: 0.4rem 0 0.6rem 0;
  font-size: 0.95rem;
}
.table th, .table td{
  border: 1px solid rgba(0,0,0,0.12);
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}
.table th{ background: rgba(0,0,0,0.04); }
@media (prefers-color-scheme: dark) {
  .table th, .table td{ border: 1px solid rgba(255,255,255,0.18); }
  .table th{ background: rgba(255,255,255,0.06); }
}

.bottom-bar{
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 1.1rem;
  width: min(880px, calc(100% - 2rem));
  z-index: 9999;
  background: rgba(255,255,255,0.96);
  border-radius: 1.25rem;
  box-shadow: 0 10px 28px rgba(0,0,0,0.12);
  padding: 0.7rem 0.8rem;
}
@media (prefers-color-scheme: dark) {
  .bottom-bar{ background: rgba(17,17,17,0.92); }
}
div[data-testid="stChatInput"]{ display:none !important; }
</style>
""",
        unsafe_allow_html=True,
    )

def esc(text: str) -> str:
    return html.escape(text or "").replace("\n", "<br>")

def render_bubble(role: str, inner_html: str):
    klass = "user" if role == "user" else "assistant"
    st.markdown(f"<div class='bubble {klass}'>{inner_html}</div>", unsafe_allow_html=True)

def render_table(headers, rows):
    ths = "".join(f"<th>{esc(h)}</th>" for h in headers)
    trs = ""
    for r in rows:
        tds = "".join(f"<td>{esc(str(x))}</td>" for x in r)
        trs += f"<tr>{tds}</tr>"
    return f"<table class='table'><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>"

# ===========================
# LLM（重試）
# ===========================
def call_llm(messages, retries=2):
    global API_KEY

    if not API_KEY:
        return None

    url = f"{BASE_URL}/api/chat"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL_NAME, "messages": messages, "stream": False, "temperature": 0.7}

    for i in range(retries + 1):
        try:
            with st.status(f"LLM 思考中…（第 {i+1} 次嘗試）", expanded=False):
                r = requests.post(url, headers=headers, json=payload, timeout=180)
            if r.status_code == 200:
                data = r.json()
                content = data.get("message", {}).get("content", "")
                if content:
                    return content
            st.warning(f"⚠️ 伺服器回傳錯誤代碼: {r.status_code}")
        except requests.exceptions.Timeout:
            st.warning("⏳ Timeout，正在重試…")
        except Exception as e:
            st.error(f"❌ 連線錯誤: {e}")
        time.sleep(2)
    return None

def trim_history(history):
    max_msgs = MAX_HISTORY_TURNS * 2
    return history[-max_msgs:] if len(history) > max_msgs else history

def build_messages(history, user_prompt):
    return [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": user_prompt}]

def parse_recipe_json(text: str):
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        obj = json.loads(cleaned)
        obj.setdefault("servings", "")
        obj.setdefault("ingredients", [])
        obj.setdefault("seasonings", [])
        obj.setdefault("steps", [])
        obj.setdefault("tips", [])
        obj.setdefault("alternatives", [])
        return obj
    except Exception:
        return None

# ===========================
# Agent（無影片）
# ===========================
def ask_chef_agent(llm_history, user_input):
    prompt_decide = (
        f"根據對話內容與使用者最新輸入：{user_input}\n"
        f"請推薦『一道』最合適的菜名，只回答菜名，不要標點符號。"
    )
    dish = call_llm(build_messages(llm_history, prompt_decide))
    if not dish:
        return {"ok": False, "error": "伺服器沒有回應（或缺少 API Key）。可稍後再試。"}
    dish = dish.strip().replace("。", "").replace("【", "").replace("】", "")

    prompt_recipe = f"""
使用者最新輸入：{user_input}
料理名稱：{dish}

請輸出『純 JSON』，不要任何多餘文字、不要 markdown、不要表格語法。
JSON 內的所有內容（食材、步驟、備註）都必須嚴格使用繁體中文輸出。
JSON 結構必須是：
{{
  "servings": "2–3 人",
  "ingredients": [{{"name":"", "amount":"", "note":""}}, ...],
  "seasonings":  [{{"name":"", "amount":"", "note":""}}, ...],
  "steps": ["", "", ...],
  "tips": ["", ...],
  "alternatives": ["", ...]
}}
""".strip()

    recipe_raw = call_llm(build_messages(llm_history, prompt_recipe))
    recipe = parse_recipe_json(recipe_raw or "")
    if recipe is None:
        fallback = (recipe_raw or "").replace("|", "｜")
        recipe = {
            "servings": "",
            "ingredients": [],
            "seasonings": [],
            "steps": [fallback] if fallback else ["（食譜生成失敗，請稍後再試）"],
            "tips": [],
            "alternatives": []
        }

    return {"ok": True, "dish": dish, "recipe": recipe}

# ===========================
# App
# ===========================
st.set_page_config(page_title="Chef Agent", page_icon="🥘", layout="centered", initial_sidebar_state="auto")
inject_ui_css()

if "ui_messages" not in st.session_state:
    st.session_state.ui_messages = []
if "llm_history" not in st.session_state:
    st.session_state.llm_history = []

with st.sidebar:
    st.title("🥦 Chef Agent")

    if st.button("🧹 清空對話", use_container_width=True):
        st.session_state.ui_messages = []
        st.session_state.llm_history = []
        st.rerun()

    st.divider()
    st.write("**模型**：", MODEL_NAME)
    st.write("**伺服器**：", BASE_URL)
    if not API_KEY:
        st.warning("找不到 API.txt（需要 API Key 才能呼叫模型）。")

st.markdown("## 🥘 Chef Agent")

# render chat
st.markdown("<div class='chat-wrap'>", unsafe_allow_html=True)

for msg in st.session_state.ui_messages:
    if msg["type"] == "text":
        render_bubble(msg["role"], esc(msg["content"]))
    else:
        dish = msg["dish"]
        recipe = msg["recipe"]
        parts = [f"<h3>✅ 建議料理：{esc(dish)}</h3>"]

        if recipe.get("servings"):
            parts.append(f"<div><b>份量：</b>{esc(recipe.get('servings'))}</div>")

        ing = recipe.get("ingredients", [])
        if isinstance(ing, list) and ing:
            rows = [(i.get("name",""), i.get("amount",""), i.get("note","")) for i in ing]
            parts.append("<hr><h4>🥬 份量建議</h4>")
            parts.append(render_table(["食材", "份量", "備註"], rows))

        seas = recipe.get("seasonings", [])
        if isinstance(seas, list) and seas:
            rows = [(s.get("name",""), s.get("amount",""), s.get("note","")) for s in seas]
            parts.append("<hr><h4>🧂 調味料</h4>")
            parts.append(render_table(["調味料", "份量", "備註"], rows))

        steps = recipe.get("steps", [])
        if isinstance(steps, list) and steps:
            parts.append("<hr><h4>👩‍🍳 步驟</h4>")
            parts.append("".join(f"<div>{idx+1}. {esc(str(s))}</div>" for idx, s in enumerate(steps) if str(s).strip()))

        tips = recipe.get("tips", [])
        if isinstance(tips, list) and tips:
            parts.append("<hr><h4>💡 小訣竅</h4>")
            parts.append("".join(f"<div>- {esc(str(t))}</div>" for t in tips if str(t).strip()))

        alts = recipe.get("alternatives", [])
        if isinstance(alts, list) and alts:
            parts.append("<hr><h4>🔁 可替代食材</h4>")
            parts.append("".join(f"<div>- {esc(str(a))}</div>" for a in alts if str(a).strip()))

        render_bubble("assistant", "".join(parts))

st.markdown("</div>", unsafe_allow_html=True)

# bottom input (no prefill)
st.markdown("<div class='bottom-bar'>", unsafe_allow_html=True)
with st.form("send_form", clear_on_submit=True):
    c1, c2 = st.columns([0.86, 0.14])
    with c1:
        user_text = st.text_input(
            "",
            value="",
            placeholder="輸入食材或需求（例如：豆腐、青江菜、10分鐘、不吃辣）",
            label_visibility="collapsed"
        )
    with c2:
        send = st.form_submit_button("送出", use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

if send and user_text.strip():
    u = user_text.strip()
    st.session_state.ui_messages.append({"role": "user", "type": "text", "content": u})

    with st.spinner("主廚正在想菜色與食譜…"):
        res = ask_chef_agent(st.session_state.llm_history, u)

    if not res["ok"]:
        st.session_state.ui_messages.append({"role": "assistant", "type": "text", "content": f"⚠️ {res['error']}"})
        st.session_state.llm_history.append({"role": "user", "content": u})
        st.session_state.llm_history.append({"role": "assistant", "content": res["error"]})
        st.session_state.llm_history = trim_history(st.session_state.llm_history)
        st.rerun()

    st.session_state.ui_messages.append({
        "role": "assistant",
        "type": "result",
        "dish": res["dish"],
        "recipe": res["recipe"]
    })

    brief = f"推薦料理：{res['dish']}（已提供份量、調味、步驟）。"
    st.session_state.llm_history.append({"role": "user", "content": u})
    st.session_state.llm_history.append({"role": "assistant", "content": brief})
    st.session_state.llm_history = trim_history(st.session_state.llm_history)

    st.rerun()
