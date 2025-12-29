import re
import time
import html
import json
import requests
import streamlit as st

# ===========================
# 1. 設定與 API
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
    "你是一位經驗豐富的台灣家庭主婦主廚助理。"
    "你會根據使用者提供的食材、偏好與限制（例如：不能吃辣、想清淡、要快速）"
    "推薦一道菜並提供可操作的詳細步驟。"
    "你的專長是將使用者提供的食材，變成一道『台灣餐桌上常見、通俗且美味』的料理。"
    "食譜請以 JSON 輸出，並嚴格使用繁體中文。"
)

# ===========================
# 2. UI CSS 
# ===========================
def inject_ui_css():
    st.markdown(
        """
<style>

.block-container {
    padding-bottom: 6rem !important;
}
.chat-wrap {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

/* 對話氣泡樣式 */
.bubble {
    max-width: 85%;
    padding: 12px 16px;
    border-radius: 16px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    font-size: 1rem;
}
.bubble.user { 
    align-self: flex-end; 
    background: #DCF8C6; 
    border-bottom-right-radius: 4px;
}
.bubble.assistant { 
    align-self: flex-start; 
    background: #F3F4F6; 
    border-bottom-left-radius: 4px;
}
@media (prefers-color-scheme: dark) {
    .bubble.user { background: #1f6f43; color: #fff; }
    .bubble.assistant { background: #2A2A2A; color: #fff; }
}

/* 表格樣式 */
.table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.5rem 0;
    font-size: 0.95rem;
}
.table th, .table td {
    border: 1px solid rgba(128,128,128,0.2);
    padding: 8px;
    text-align: left;
}
.table th { background: rgba(128,128,128,0.1); }

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
# 3. LLM 邏輯
# ===========================
def call_llm(messages, retries=2):
    global API_KEY
    if not API_KEY: return None

    url = f"{BASE_URL}/api/chat"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {"model": MODEL_NAME, "messages": messages, "stream": False, "temperature": 0.6}

    for i in range(retries + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            if r.status_code == 200:
                content = r.json().get("message", {}).get("content", "")
                if content: return content
        except Exception:
            time.sleep(1)
    return None

def trim_history(history):
    return history[-(MAX_HISTORY_TURNS * 2):]

def build_messages(history, user_prompt):
    return [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": user_prompt}]

def parse_recipe_json(text: str):
    if not text: return None
    cleaned = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except:
        return None

def ask_chef_agent(llm_history, user_input):
    # 步驟一：決定菜名 
    prompt_decide = (
        f"使用者輸入：{user_input}\n"
        f"請根據上述輸入，推薦『一道』最合適的台灣家庭料理菜名。\n"
        f"規則：\n"
        f"1. 必須是通俗、常見的菜名（例如：『番茄炒蛋』、『青椒炒肉絲』）。\n"
        f"2. 若食材有些是作為點綴的，可以使用以下名稱（例如：『松露煎鴨胸佐可可焦糖蘋果』、『雞肉佐法式香草酸豆醬』）。\n"
        f"3. 絕對不要機械式地將食材拼湊（❌錯誤範例：『青椒胡椒炒』、『蛋番茄』）。\n"
        f"4. 如果食材太少，請自動聯想最常見的搭配。\n"
        f"5. 請只回答菜名，不要有任何標點符號或解釋。"
    )
    
    dish = call_llm(build_messages(llm_history, prompt_decide))
    if not dish:
        return {"ok": False, "error": "AI 正在忙碌中，請稍後再試。"}
    
    dish = dish.strip().replace("。", "").replace("！", "").split("\n")[0]

    # 步驟二：生成食譜
    prompt_recipe = f"""
料理名稱：{dish}
使用者原始需求：{user_input}

請針對這道菜輸出『純 JSON』食譜。
結構如下（所有內容皆為繁體中文）：
{{
  "servings": "例如：2-3 人份",
  "ingredients": [{{"name":"食材名", "amount":"數量", "note":"切法或備註"}}],
  "seasonings":  [{{"name":"調味料", "amount":"數量", "note":""}}],
  "steps": ["步驟1", "步驟2", ...],
  "tips": ["小撇步1", ...],
  "alternatives": ["若沒有某食材可改用..."]
}}
""".strip()

    recipe_raw = call_llm(build_messages(llm_history, prompt_recipe))
    recipe = parse_recipe_json(recipe_raw)

    if not recipe:
        recipe = {
            "servings": "未知",
            "ingredients": [], "seasonings": [],
            "steps": ["抱歉，食譜生成格式錯誤，請重試一次。"],
            "tips": [], "alternatives": []
        }
    
    return {"ok": True, "dish": dish, "recipe": recipe}

# ===========================
# 4. 主程式 App
# ===========================

st.set_page_config(
    page_title="Chef Agent", 
    page_icon="🍳", 
    layout="centered", 
    initial_sidebar_state="expanded" 
)

inject_ui_css()

if "messages" not in st.session_state:
    st.session_state.messages = []
if "history" not in st.session_state:
    st.session_state.history = []

# 左邊的收闔框
with st.sidebar:
    st.title("🍳 料理助手")
    st.caption("輸入食材，幫你想一道菜！")
    
   
    if st.button(" 清空對話", use_container_width=True):
        st.session_state.messages = []
        st.session_state.history = []
        st.rerun()
    
    st.divider()
    st.markdown("### ⚙️ 設定狀態")
    if API_KEY:
        st.success("API Key 已載入")
    else:
        st.error("⚠️ 未偵測到 API.txt")
        
    st.markdown("---")
    st.info("💡 小提示：你可以輸入「冰箱剩半顆洋蔥」或「只有雞蛋」，主廚會幫你想辦法！")

st.markdown("## 🥘 今晚吃什麼？")


st.markdown("<div class='chat-wrap'>", unsafe_allow_html=True)
for msg in st.session_state.messages:
    if msg["type"] == "text":
        render_bubble(msg["role"], esc(msg["content"]))
    elif msg["type"] == "recipe":
        d = msg["data"]
        dish_name = d['dish']
        rec = d['recipe']
        
        parts = [f"<h3>✨ 推薦：{esc(dish_name)}</h3>"]
        if rec.get("servings"):
            parts.append(f"<p><b>份量：</b>{esc(rec['servings'])}</p>")
        
        if rec.get("ingredients"):
            rows = [(i.get("name"), i.get("amount"), i.get("note","")) for i in rec["ingredients"]]
            parts.append(render_table(["🥬 食材", "份量", "備註"], rows))
        
        if rec.get("seasonings"):
            rows = [(s.get("name"), s.get("amount"), s.get("note","")) for s in rec["seasonings"]]
            parts.append(render_table(["🧂 調味", "份量", "備註"], rows))

        if rec.get("steps"):
            parts.append("<hr><h4>🔥 料理步驟</h4>")
            for idx, step in enumerate(rec["steps"]):
                parts.append(f"<div style='margin-bottom:6px;'><b>{idx+1}.</b> {esc(str(step))}</div>")

        if rec.get("tips"):
            parts.append("<div style='margin-top:10px; padding:10px; background:rgba(255,165,0,0.1); border-radius:8px;'>")
            parts.append("<b>💡 主廚小撇步：</b><br>")
            for t in rec["tips"]: parts.append(f"- {esc(str(t))}<br>")
            parts.append("</div>")

        render_bubble("assistant", "".join(parts))
st.markdown("</div>", unsafe_allow_html=True)

# input
user_input = st.chat_input("輸入食材（例如：豆腐、雞胸肉）或需求...")

if user_input:
    st.session_state.messages.append({"role": "user", "type": "text", "content": user_input})
    st.rerun()

if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_user_text = st.session_state.messages[-1]["content"]
    
    with st.spinner("👩‍🍳 主廚正在翻閱食譜..."):
        res = ask_chef_agent(st.session_state.history, last_user_text)

    if res["ok"]:
        st.session_state.messages.append({"role": "assistant", "type": "recipe", "data": res})
        st.session_state.history.append({"role": "user", "content": last_user_text})
        st.session_state.history.append({"role": "assistant", "content": f"推薦料理：{res['dish']}"})
        st.session_state.history = trim_history(st.session_state.history)
    else:
        st.session_state.messages.append({"role": "assistant", "type": "text", "content": f"⚠️ {res['error']}"})
    
    st.rerun()