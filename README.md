
# TOC 2025 Final Project — Intelligent Agents with LLMs 


This project presents an Intelligent Culinary Agent designed to assist users in meal planning based on available ingredients, dietary constraints, and time limitations.


---



##  State Machine Diagram
```mermaid
stateDiagram-v2
    [*] --> Init

    Init --> Ready: session_state init + UI render
    Ready --> WaitingInput: no new user_input

    WaitingInput --> UserSubmitted: user_input received
    UserSubmitted --> RerunAfterUser: append user msg + st.rerun

    RerunAfterUser --> CheckingLastMsg: rerun renders + checks last role
    CheckingLastMsg --> Generating: last role == user
    CheckingLastMsg --> WaitingInput: last role != user

    Generating --> DishDeciding: call_llm(決定菜名)
    DishDeciding --> RecipeGenerating: call_llm(生成JSON食譜)
    RecipeGenerating --> ParseRecipe: parse_recipe_json

    ParseRecipe --> ResponseReady: success
    ParseRecipe --> ResponseReady: fail -> fallback

    ResponseReady --> RerunAfterAssistant: append assistant + history + trim + st.rerun
    RerunAfterAssistant --> WaitingInput

```
## DAG
```mermaid
flowchart TD
  U["User input from st.chat_input"] --> M1["Append user text into session_state.messages"]
  M1 --> R1["st.rerun"]

  R1 --> UI["Render sidebar and chat history"]
  UI --> CHK{Is last message role user?}

  CHK -- "No" --> IDLE["Idle, wait for next input"]
  CHK -- "Yes" --> AG["ask_chef_agent(history, last_user_text)"]

  AG --> D1["call_llm: decide dish name"]
  D1 --> CLN["Clean dish string"]
  CLN --> D2["call_llm: generate recipe JSON"]
  D2 --> PARSE["parse_recipe_json"]

  PARSE --> OK{JSON parsed?}
  OK -- "Yes" --> RES1["Build result object with recipe"]
  OK -- "No" --> RES2["Fallback recipe object"]

  RES1 --> OUT["Append assistant recipe into session_state.messages"]
  RES2 --> OUT

  OUT --> H1["Append simplified texts into session_state.history"]
  H1 --> TRIM["trim_history"]
  TRIM --> R2["st.rerun"]
  R2 --> UI


```



##  專案結構
```
.
├─ app.py                # Streamlit 主程式（Chef Agent）
├─ requirements.txt      
├─ README.md
├─ API.txt        

```

---

## How to Run

### 1) clone
```bash
git clone https://github.com/Crosonggg/TOC-2025-Final-Project.git
cd TOC-2025-Final-Project
```

### 2) Install required packages:
```bash
pip install -r requirements.txt
```
### 3) Configure API Key
將 `API.txt` 內容改成你的 API key：


### 4) run
```bash
streamlit run app.py
```

---



---


