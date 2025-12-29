
# TOC 2025 Final Project — Intelligent Agents with LLMs 


This project presents an Intelligent Culinary Agent designed to assist users in meal planning based on available ingredients, dietary constraints, and time limitations.


---



##  State Machine Diagram
```mermaid
stateDiagram-v2
    [*] --> Init

    Init --> LoadAPIKey: read API.txt
    LoadAPIKey --> Ready: API_KEY exists
    LoadAPIKey --> ReadyNoKey: API_KEY missing

    ReadyNoKey --> ReadyNoKey: user input\n(show warning)\n(no LLM call)
    ReadyNoKey --> Ready: API.txt added later\n(reload)

    Ready --> Idle
    Idle --> UserSubmit: user clicks "送出"\n& input not empty

    UserSubmit --> AppendUserMsg: ui_messages += user bubble
    AppendUserMsg --> AgentStart: ask_chef_agent()

    state AgentStart {
        [*] --> DecideDish
        DecideDish --> DecideDishCall: call_llm(prompt_decide)
        DecideDishCall --> DecideDishOK: got dish text
        DecideDishCall --> LLMFail: no response after retries

        DecideDishOK --> BuildRecipePrompt
        BuildRecipePrompt --> GetRecipe
        GetRecipe --> GetRecipeCall: call_llm(prompt_recipe)
        GetRecipeCall --> GotRecipeText: got raw text
        GetRecipeCall --> LLMFail: no response after retries

        GotRecipeText --> ParseJSON: parse_recipe_json()
        ParseJSON --> ParsedOK: valid JSON
        ParseJSON --> ParsedFail: invalid JSON

        ParsedFail --> FallbackRecipe: replace | -> ｜\nsteps=[raw or error msg]
        ParsedOK --> ReturnOK
        FallbackRecipe --> ReturnOK

        LLMFail --> ReturnErr
        ReturnOK --> [*]
        ReturnErr --> [*]
    }

    AgentStart --> ShowError: res.ok == false
    AgentStart --> ShowResult: res.ok == true

    ShowError --> UpdateHistoryErr: llm_history += (user, error)
    ShowResult --> AppendAssistantResult: ui_messages += result bubble
    AppendAssistantResult --> UpdateHistoryBrief: llm_history += (user, brief summary)

    UpdateHistoryErr --> TrimHistory: keep last MAX_HISTORY_TURNS*2 msgs
    UpdateHistoryBrief --> TrimHistory
    TrimHistory --> Rerun: st.rerun()

    Rerun --> Idle


```
## DAG
```mermaid
flowchart TD
    A["User submits input"] --> B["Append user bubble to ui_messages"]
    B --> C["Run ask_chef_agent"]

    subgraph Agent["Agent: two LLM calls + parsing"]
        C --> D["LLM step 1: decide dish name"]
        D --> E["call_llm (with retries)"]

        E -->|success| F["Clean dish text"]
        E -->|fail| Z["Return error (no response or missing key)"]

        F --> G["LLM step 2: request recipe JSON"]
        G --> H["call_llm (with retries)"]

        H -->|success| I["Parse JSON"]
        H -->|fail| Z

        I -->|valid| J["Return OK: dish + recipe object"]
        I -->|invalid| K["Fallback recipe text (sanitize pipes)"]
        K --> J
    end

    Z --> L["Show error bubble"]
    J --> M["Show result bubble (tables + steps)"]

    L --> N["Update llm_history: user + error"]
    M --> O["Update llm_history: user + brief summary"]

    N --> P["Trim history to last N messages"]
    O --> P

    P --> Q["st.rerun (re-render UI)"]


```


---

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


