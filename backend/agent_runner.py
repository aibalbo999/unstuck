# ============================================================
# agent_runner.py - 連續式 Agent 執行引擎
# 包含：API Key 輪調、速率限制、7個分析 Agent 的 Prompt
# ============================================================

import time
import asyncio
import re
import google.generativeai as genai
from config import API_KEYS, AGENT_MODELS, RPM_LIMITS, INTER_AGENT_DELAY
from financial_data import format_data_for_prompt


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API Key 輪調管理器
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class KeyRotator:
    """
    API Key 輪調管理器
    - 追蹤每個 Key + Model 組合的呼叫時間
    - 自動選擇未超過 RPM 的 Key
    - 超過限制時自動等待
    """
    
    def __init__(self, keys: list):
        if not keys:
            raise RuntimeError(
                "未設定 Gemini API key。請設定 GEMINI_API_KEYS / GOOGLE_API_KEYS，"
                "或在 backend/.env 放入 GEMINI_API_KEYS=key1,key2。"
            )
        self.keys = keys
        self.index = 0
        # 格式：{key: {model: [timestamp, ...]}}
        self.call_log: dict = {k: {} for k in keys}
    
    def _clean_old_calls(self, key: str, model: str):
        """清除超過 60 秒的通話記錄"""
        now = time.time()
        if model not in self.call_log[key]:
            self.call_log[key][model] = []
        self.call_log[key][model] = [
            t for t in self.call_log[key][model] 
            if now - t < 60
        ]
    
    def get_key(self, model: str) -> str:
        """取得可用的 API Key（自動輪調 + 速率限制）"""
        rpm_limit = RPM_LIMITS.get(model, 5)
        
        # 嘗試所有 Key 找到可用的
        for attempt in range(len(self.keys)):
            key = self.keys[self.index]
            self.index = (self.index + 1) % len(self.keys)
            
            self._clean_old_calls(key, model)
            current_calls = len(self.call_log[key][model])
            
            if current_calls < rpm_limit:
                self.call_log[key][model].append(time.time())
                key_preview = f"{key[:8]}...{key[-4:]}"
                print(f"    🔑 使用 Key {self.keys.index(key)+1}/5 ({key_preview})")
                return key
        
        # 所有 Key 都已超限，等待最早的呼叫過期
        print(f"    ⏳ 所有 API Key 已達 RPM 限制，等待 60 秒...")
        time.sleep(60)
        return self.get_key(model)
    
    def get_status(self) -> dict:
        """取得各 Key 的使用狀態"""
        now = time.time()
        status = {}
        for i, key in enumerate(self.keys):
            key_name = f"Key-{i+1}"
            status[key_name] = {}
            for model, calls in self.call_log[key].items():
                recent = [t for t in calls if now - t < 60]
                status[key_name][model] = len(recent)
        return status


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 各 Agent 系統提示詞（System Prompts）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SYSTEM_PROMPTS = {
    1: """你是高盛（Goldman Sachs）股票研究部門的資深分析師，擁有 20 年的台灣及亞太區股票研究經驗，專精於科技硬體、半導體及電子供應鏈分析。

你的分析特點：
- 深度理解商業模式和產業生態
- 以數據為導向，但能用簡單語言解釋複雜概念  
- 嚴格客觀，不受市場情緒影響
- 注重長期價值而非短期波動

請用繁體中文撰寫，風格專業但易於理解。分析要有深度，數據要有根據。""",

    2: """你是摩根士丹利（Morgan Stanley）台灣研究部的財務模型專家，擁有 CFA 資格，專精於財務報表深度分析和財務體質評估。

你的專長：
- 透過財務數據識別公司的真實競爭力
- 辨別一次性項目與持續性獲利
- 評估現金流品質和財務槓桿風險
- 預判財務趨勢的轉折點

請用繁體中文撰寫，分析要具體，引用提供的財務數據支持論點。""",

    3: """你是貝萊德（BlackRock）主動投資研究團隊的競爭優勢分析師，專門研究公司的護城河（Economic Moat）和長期競爭力。

你深入理解五種護城河類型：品牌、網路效應、轉換成本、成本優勢、無形資產。

評分標準（1-10分）：
- 1-3：護城河很弱或不存在
- 4-6：護城河一般，競爭壓力大
- 7-8：護城河較強，有一定防禦能力
- 9-10：強大護城河，具有持久競爭優勢

請用繁體中文撰寫。⚠️ 重要：請在回應的**第一段**先輸出以下格式的評分，然後再展開詳細分析：

[護城河評分]
品牌影響力: X
網路效應: X
轉換成本: X
成本優勢: X
專利技術: X
整體護城河: X/10
[/護城河評分]""",

    4: """你是 JP 摩根（JPMorgan Chase）投資銀行部門的股票估值專家，精通多種估值方法論，包括 DCF、相對估值、資產評估等。

你的估值方法嚴謹：
- DCF 分析採用合理的折現率和終值假設
- 相對估值與同業進行有意義的比較
- 清楚說明估值假設和敏感度

請用繁體中文撰寫。估值分析必須包含以下格式的價格目標：

[目標股價]
熊市情境: NT$XX（下跌X%）
基本情境: NT$XX（上漲/下跌X%）
牛市情境: NT$XX（上漲X%）
[/目標股價]""",

    5: """你是富達投資（Fidelity Investments）的成長股研究員，專門分析科技公司的長期成長潛力和市場機會。

你的分析框架：
- 由上而請依照以下架構進行分析：

## 一、市場規模分析 (TAM/SAM/SOM)
請以 Markdown 表格呈現 TAM（總可潛在市場）、SAM（可服務市場）與 SOM（可獲得市場）的預估規模與增長率。

## 二、關鍵成長驅動力 (未來 5-10 年)
列舉 3-5 個將推動公司長期成長的核心因素。

## 三、AI 與新技術的潛在影響
分析生成式 AI 或其他顛覆性技術對該公司的潛在影響（正面或負面）。

## 四、長期市佔率與利潤率預期
預估未來的競爭格局變化。""",

    6: """你是一個資深財經媒體的節目主持人，正在主持一場關於特定股票的多空辯論節目。

辯論者：
🐂 多頭分析師（陳博士）：看好股票，積極尋找上漲理由
🐻 空頭分析師（李博士）：看空股票，指出潛在風險

規則：
- 每位分析師至少發言 3 次
- 每次發言必須引用具體數據
- 辯論要有邏輯性和對話感
- 最後給出中性平衡結論
- ⚠️ 嚴格限制：必須精確使用以下格式開頭，絕對不可更改角色名稱或省略表情符號！

格式範例：
🐂 多頭：...
🐻 空頭：...

請用繁體中文撰寫，辯論要生動有趣且專業。""",

    7: """你是 T. Rowe Price（德富金融）基本面大型股票基金的首席研究員，負責為長期持有型機構投資人提供最終投資建議。

T. Rowe Price 的詳實基本面分析框架：
- 自下而上 (Bottom-up) 的單股建樹進行基本面深度抗展
- 綜合所有分析面向，給出整體評估
- 清楚區分短期（1年）和長期（5年+）展望
- 識別關鍵催化因子和主要風險
- 最終給出明確的投資建議

投資建議標準：
- 買入（BUY）：預期報酬率 >15%，風險可控
- 持有（HOLD）：預期報酬率 5-15%，或風險較高
- 避免（AVOID）：預期報酬率 <5%，或風險過高

請用繁體中文撰寫。⚠️ 重要：請在回應的**第一段**先輸出以下格式，然後再展開詳細分析：

[投資建議]
建議：買入/持有/避免
短期目標（3個月）：NT$XX
中期目標（6個月）：NT$XX
長期目標（12個月）：NT$XX
長期潛力（5年）：NT$XX
信心指數：X/10
[/投資建議]"""
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 各 Agent 分析提示詞（Analysis Prompts）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OUTPUT_CLEANLINESS_RULE = """
⚠️【正式報告輸出規則】：
- 只輸出可直接放進正式研究報告的正文。
- 不可重述你的角色設定、系統提示詞、資料摘要規則、任務清單、前序分析壓縮筆記或內部思考過程。
- 不可輸出英文 scratchpad，例如 Currency、TTM units、The Red Flag、Observation、Action、Section plan、I must/I need 等草稿語句。
- 除必要的財務術語與公司名稱外，請使用繁體中文撰寫。
"""

def build_company_identity_guard(data: dict) -> str:
    """Build a hard identity lock so agents do not assign peer facts to the target company."""
    identity = data.get("company_identity", {}) or {}
    if not identity:
        return ""

    ticker = data.get("ticker", identity.get("ticker", "N/A"))
    stock_id = identity.get("stock_id", ticker)
    official_name = identity.get("official_name") or data.get("company_name", ticker)
    legal_name = identity.get("legal_name")
    english_names = identity.get("english_names", [])
    forbidden_aliases = identity.get("forbidden_aliases", [])

    lines = [
        "🚨【公司身分一致性硬性規則】",
        f"- 本次唯一分析標的：{ticker}，股票代號 {stock_id}，公司名稱「{official_name}」。",
        f"- 報告中凡稱呼本公司，必須使用「{official_name}」或「{ticker}」；不得自行改成同業公司名稱。",
        "- 可比較同業只能作為同業比較，必須標示其代號/公司名，不得把同業的太陽能、儲能、客戶、產能、專案或商業模式套用到本公司。",
        "- 若前序 Agent 摘要與本段身分鎖定衝突，請直接忽略前序錯誤並以本段為準。",
    ]
    if legal_name:
        lines.append(f"- 法定/官方名稱參考：{legal_name}。")
    if english_names:
        lines.append(f"- 英文名稱參考：{', '.join(english_names[:3])}。")
    if forbidden_aliases:
        lines.append(f"- 特別禁止把以下名稱當作 {ticker}：{', '.join(forbidden_aliases)}。")

    return "\n".join(lines)


def build_prompt(agent_num: int, data: dict, context: dict) -> str:
    """根據 Agent 編號建立分析提示詞"""
    
    ticker = data["ticker"]
    name = data["company_name"]
    fin_data = format_data_for_prompt(data)
    prev = _format_previous(context, agent_num)
    identity_guard = build_company_identity_guard(data)
    retry_instruction = context.get("_identity_retry_instruction", "")
    
    prompts = {
        1: f"""請對 {ticker}（{name}）進行完整的華爾街風格股票研究分析。

{fin_data}

請依照以下架構撰寫完整分析報告（每個部分至少 200 字）：

## 一、公司概述與商業模式
說明公司的核心業務、主要產品/服務、收入來源分佈和商業模式特點。

## 二、總體經濟與產業趨勢分析
分析所在產業的整體趨勢，包括成長動力、技術演進、供需狀況，以及總體經濟環境對該公司的影響。

## 三、供應鏈地位與競爭態勢
分析公司在上下游供應鏈中的地位，並盤點主要競爭對手。

## 四、主要風險因子
列出並詳細說明 3-5 個最重要的投資風險與營運挑戰。

請務必：引用提供的數據，保持客觀平衡。不需要進行估值或深入財務分析，那是其他專家的工作。""",

        2: f"""請對 {ticker}（{name}）進行深度財務數據分析，重點是過去 5 年的財務趨勢。

{fin_data}

前序整體分析摘要：
{prev}

⚠️ 嚴格限制：
1. 請務必「只」使用上方提供的財務數據進行分析，不可自行捏造或推估不存在的歷史數字。若資料有缺漏，請誠實指出。
2. 🚨【製造業與成長期現金流防呆】：若該公司屬硬體製造業且處於高成長期，營運資金（應收帳款與存貨）及資本支出（CapEx）必然大增，自由現金流 (FCF) 理應受到擠壓。若發現營收暴增但 FCF 轉換率依然極高（>100%），請提出嚴肅的財務質疑（例如：是否為強勢預收款、或資本支出遞延），絕對不可盲目讚美其現金流！
3. 🚨【FCF 常態化防呆】：若營收成長超過 50% 且 FCF/淨利 >100%，不可把該年度 FCF 當作可持續常態。必須拆解營業現金流、營運資金變動與 CapEx；若資料不足，請標示為「需查核/不可持續」，並提醒估值端應使用 normalized FCF。

請依照以下架構進行分析（每部分至少 150 字，必須引用具體數字）：

## 一、營收成長分析
- 歷年營收數據和成長率
- CAGR 計算與評估
- 成長的驅動因素分析

## 二、獲利趨勢深析
- 淨利趨勢（含一次性項目辨別）
- 毛利率/營業利潤率/淨利率的歷年走勢
- 獲利品質評估

## 三、自由現金流分析
- 歷年 FCF 數據
- FCF 轉換率（FCF/淨利）
- 資本支出趨勢與投資效率

## 四、財務槓桿與償債能力
- 負債水準分析（絕對數和比率）
- 債務結構和期限分佈
- 利息保障倍數

## 五、股東權益報酬率（ROE）分析
- 歷年 ROE 趨勢
- 杜邦分析（拆解利潤率×資產周轉×權益乘數）
  ★ 重要：權益乘數必須使用「Total Assets / Equity」，系統已對你提供「真實權益乘數」就請使用它。
  ★ 杜邦分析是會計恒等式：同期間 ROE 必須等於淨利率 × 資產周轉率 × 權益乘數。
  ★ 嚴禁把不同期間/不同口徑資料拼接後的差距，解讀成「應付帳款等非計息負債槓桿」。若驗算差距超過5%，只能說明資料口徑、平均資產/權益或期間不一致。
  ★ 注意：D/E 比率只包含有息負債，不能代替權益乘數；但正確權益乘數本身已包含所有負債，不能再額外歸因一次。

## 六、財務體質最終判斷
明確結論：公司財務體質正在【強化】還是【走弱】？原因為何？""",

        3: f"""請對 {ticker}（{name}）進行深度的競爭護城河評估。

{fin_data}

前序分析摘要（商業模式與財務）：
{prev}

⚠️ 重要：請在回應的**第一段**先輸出以下結構化的 [護城河評分] 區塊，再展開詳細分析：
[護城河評分]
品牌影響力: X
網路效應: X
轉換成本: X
成本優勢: X
專利技術: X
整體護城河: X/10
[/護城河評分]

---

接下來，請依照以下五個維度，深入分析並給予 1-10 的評分與具體理由：

1. **無形資產（品牌影響力、專利、特許經營權）**
2. **網路效應（Network Effect）**
3. **轉換成本（Switching Costs）**
4. **成本優勢（Cost Advantage）**
5. **護城河趨勢（擴張、穩定或縮減）**

結論請總結其競爭優勢的持久性。""",

        4: f"""請對 {ticker}（{name}）進行投資銀行等級的估值分析。

{fin_data}

前序分析摘要（商業模式、財務、護城河）：
{prev}

⚠️ 重要：請在回應的**第一段**先輸出以下結構化目標股價，再展開詳細分析：
[目標股價]
熊市情境: NT$XX
基本情境: NT$XX
牛市情境: NT$XX
[/目標股價]

---

接下來請依照以下架構進行完整估值分析（必須給出具體數字）：

⚠️ 【估值方法防呆規則】：
- 相對估值與 DCF 必須分開呈現。若用「Forward EPS × 目標 P/E」推導股價，請明確標示為「本益比估值」，且乘法要正確。
- DCF 估值必須從未來自由現金流、WACC、終值成長率/終值倍數推導；DCF 結果不需要、也不應該剛好等於 Forward EPS × P/E。
- 嚴禁把「Forward EPS × P/E 與 DCF 完全吻合」稱為防呆驗證；若兩者接近，只能說是估值交叉檢查，且必須解釋各自假設。
- WACC 權重必須優先採用市場價值資本結構（市值與有息負債市值/近似值），不可用帳面 D/E 直接推估股權權重。
- 對硬體製造業，若情境假設營收成長超過 50%，必須同步納入產能、CapEx、折舊、良率學習曲線與客戶第二供應商壓價；缺乏證據時應下修 FCF 或利潤率。
- 雙重樂觀禁止：若 Forward EPS 或你的財測已隱含營收一年內成長超過 50%，不得再給予高於 20x 的目標 Forward P/E，除非提出可驗證的多年度成長證據；即使採用高倍數，也必須在基本情境下提供折讓後估值作為主要結論。
- FCF 基準常態化：若最近年度營收高速成長且 FCF/淨利 >100%，DCF 不得直接以該年度 FCF 作為穩態基準，必須用 normalized FCF（扣除一次性營運資金釋放、補足成長 CapEx 與折舊壓力）。

## 一、相對估值分析
1. **本益比（P/E）分析**：當前 P/E vs 歷史平均 vs 同業平均，判斷高低估
2. **股價淨值比（P/B）分析**：同上邏輯
3. **EV/EBITDA 分析**：與同業比較
4. **綜合相對估值結論**：基於多個倍數的合理估值區間

## 二、折現現金流（DCF）估值
假設說明：
- 預估未來 5 年的 FCF 成長率（依三情境）
- 終值成長率
- 折現率（WACC）假設，含市場價值股權/債務權重
- 營收高成長所需 CapEx、折舊與營運資金假設

三情境 DCF 計算：
| 情境 | FCF成長率 | 終值倍數 | 合理股價 |
|------|----------|---------|---------|
| 熊市 | X%       | X倍     | NT$XX   |
| 基本 | X%       | X倍     | NT$XX   |
| 牛市 | X%       | X倍     | NT$XX   |

## 三、同業估值水準參考
列舉 3-5 個可比公司的估值倍數。

## 四、估值結論
當前股價是否被【低估】、【合理】或【高估】？理由？""",

        5: f"""請分析 {ticker}（{name}）的未來 5-10 年成長潛力。

{fin_data}

前序分析摘要：
{prev}

請依照以下架構進行分析：

## 一、市場規模分析 (TAM/SAM/SOM)
請以 Markdown 表格呈現 TAM（總可潛在市場）、SAM（可服務市場）與 SOM（可獲得市場）的預估規模與增長率。

## 二、關鍵成長驅動力 (未來 5-10 年)
列舉 3-5 個將推動公司長期成長的核心因素。

## 三、AI 與新技術的潛在影響
分析生成式 AI 或其他顛覆性技術對該公司的潛在影響（正面或負面）。

## 四、長期市佔率與利潤率預期
預估未來的競爭格局變化。

## 五、成長情境預測（5年）
| 情境 | 核心假設 | 5年後年營收 | 年化成長率 |
|------|---------|-----------|----------|
| 保守 | ...     | NT$XXX億  | X%       |
| 基本 | ...     | NT$XXX億  | X%       |
| 樂觀 | ...     | NT$XXX億  | X%       |

若任何情境預測營收較目前成長超過 50%，請在核心假設中明確寫出產能來源、CapEx/折舊壓力、人力與良率學習曲線、客戶議價或第二供應商風險，並判斷淨利率是否必須回落。

## 六、成長潛力總評
未來 5-10 年的整體成長空間評估和關鍵催化因子排序。""",

        6: f"""請以兩位知名分析師辯論的形式，對 {ticker}（{name}）進行多空辯論。

{fin_data}

前序所有分析摘要：
{prev}

辯論規則：
- 🐂 多頭：每次發言都必須有具體數據支持
- 🐻 空頭：每次發言也必須有數據反駁
- 辯論要有對話感，後一個人要回應前一個人的論點
- 至少進行 4 輪來回
- ⚠️ 嚴格限制：對話開頭必須精確使用「🐂 多頭：」與「🐻 空頭：」，不可使用其他稱呼！
- ⚠️ 財務紅線：任何一方都不得把杜邦恒等式的口徑差異歸因於應付帳款槓桿；不得把高速成長下 >100% FCF 轉換率當作可持續常態；不得同時假設營收暴增與高估值倍數而不揭露雙重樂觀風險。

請開始辯論：

（注意：辯論要生動、專業，雙方論點都要有說服力）

最後格式：
---
**主持人總結：**
[平衡的中性結論，含整體評估]""",

        7: f"""請作為機構投資人的首席研究員，基於所有前序分析，給出 {ticker}（{name}）的最終投資決策報告。

{fin_data}

所有前序分析（請仔細閱讀所有 6 位分析師的結論）：
{prev}

⚠️ 重要：Agent 4 (估值專家) 已經給出了三個情境的 [目標股價]。你的最終預測必須與估值專家的數字保持邏輯一致性。若你提及目標本益比 (Forward P/E) 與預估 EPS 推導出的目標價，請標示為「本益比估值」且乘法必須正確；不得把它稱作 DCF 防呆或要求它與 DCF 完全相等。

⚠️ 風險一致性要求：若最終投資論述依賴營收在 1-2 年內成長超過 50%，必須同步處理產能、CapEx、折舊、良率學習曲線、客戶第二供應商與價格壓力。若沒有明確證據支持「營收暴增但淨利率不掉」，必須降低信心指數、目標價或投資建議。

⚠️ 雙重樂觀限制：若 Forward EPS 已隱含營收暴增，最終目標價不得再套用高 Forward P/E 來重複計價成長。原則上應使用折讓後倍數或 normalized DCF；若給予 >20x 的目標 Forward P/E，必須清楚說明為何沒有 double-counting upside，並提供保守折讓情境。

⚠️ 關鍵指令：請務必在回應的**最上方第一段**，先輸出以下 [投資建議] 區塊（這對系統解析非常重要）：
[投資建議]
建議：買入/持有/避免
短期目標（3個月）：NT$XX
中期目標（6個月）：NT$XX
長期目標（12個月）：NT$XX
長期潛力（5年）：NT$XX
信心指數：X/10
[/投資建議]

---
請依照以下格式撰寫最終決策備忘錄：

## 執行摘要
一段話概述投資機會的本質。

## 短中長期展望（未來 3-12 個月）
- 關鍵催化因子（正面）
- 主要風險事件（負面）
- 短中長期價格目標 (3個月、6個月、12個月)

## 長期展望（未來 5 年以上）
- 核心成長邏輯
- 長期競爭優勢的可持續性
- 長期價值創造潛力

## 關鍵催化因子（按重要性排序）
1. XXX（時間點：XX）
2. XXX（時間點：XX）
3. XXX（時間點：XX）

## 主要風險（按嚴重性排序）
1. XXX（緩解方法：XX）
2. XXX（緩解方法：XX）
3. XXX（緩解方法：XX）

## 最終投資決策論述
基於以上所有分析，詳細說明為何給出該建議（買入/持有/避免）。
"""
    }
    
    prompt_parts = [prompts[agent_num], identity_guard, retry_instruction, OUTPUT_CLEANLINESS_RULE]
    return "\n\n".join(part for part in prompt_parts if part)


def _format_previous(context: dict, current_agent: int) -> str:
    """格式化前序分析摘要"""
    analyses = context.get("analyses", {})
    if not analyses:
        return "（無前序分析）"
    
    agent_names = {
        1: "整體分析",
        2: "財務分析",
        3: "護城河評估",
        4: "估值分析",
        5: "成長潛力",
        6: "多空辯論",
    }
    
    parts = []
    for i in range(1, current_agent):
        if i in analyses:
            name = agent_names.get(i, f"Agent {i}")
            # 只取前 800 字避免 prompt 過長
            content = analyses[i][:800] + "..." if len(analyses[i]) > 800 else analyses[i]
            parts.append(f"【{name}】\n{content}")
    
    return "\n\n".join(parts) if parts else "（無前序分析）"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 核心 Agent 執行函數
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_single_agent(
    agent_num: int,
    data: dict,
    context: dict,
    rotator: KeyRotator,
    max_retries: int = 3
) -> str:
    """
    執行單個分析 Agent
    - 自動選擇可用的 API Key
    - 超限時自動重試
    - 錯誤時返回錯誤訊息
    """
    model_id = AGENT_MODELS[agent_num]
    
    for attempt in range(max_retries):
        try:
            # 取得可用 API Key
            api_key = rotator.get_key(model_id)
            
            # 配置 Gemini 客戶端
            genai.configure(api_key=api_key)
            
            # 建立模型實例
            model = genai.GenerativeModel(
                model_name=model_id,
                system_instruction=SYSTEM_PROMPTS[agent_num],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    top_p=0.95,
                    max_output_tokens=8192,
                )
            )
            
            # 建立分析提示詞
            prompt = build_prompt(agent_num, data, context)
            
            # 執行分析
            response = model.generate_content(prompt)
            result = response.text
            
            if result and len(result) > 100:
                return result
            else:
                print(f"    ⚠️  回應過短，重試 ({attempt+1}/{max_retries})")
                time.sleep(5)
                
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                wait_time = 65 * (attempt + 1)
                print(f"    ⏳ 速率限制，等待 {wait_time} 秒... ({attempt+1}/{max_retries})")
                time.sleep(wait_time)
            elif "404" in error_msg or "not found" in error_msg.lower():
                print(f"    ❌ 模型 {model_id} 不可用，嘗試備用模型...")
                # 嘗試備用模型
                backup_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
                for backup in backup_models:
                    try:
                        genai.configure(api_key=rotator.get_key(backup))
                        model = genai.GenerativeModel(
                            model_name=backup,
                            system_instruction=SYSTEM_PROMPTS[agent_num],
                        )
                        response = model.generate_content(prompt)
                        return response.text
                    except Exception:
                        continue
                return f"[Agent {agent_num} 執行失敗：模型不可用]"
            else:
                print(f"    ❌ 錯誤：{error_msg[:100]}... 重試 ({attempt+1}/{max_retries})")
                time.sleep(10 * (attempt + 1))
    
    # 如果重試皆失敗，自動降級/備援至最穩定的 gemini-3.5-flash
    print(f"    ⚠️ 模型 {model_id} 多次失敗，啟用備援機制 (gemini-3.5-flash)...")
    try:
        genai.configure(api_key=rotator.get_key("gemini-3.5-flash"))
        model = genai.GenerativeModel(
            model_name="gemini-3.5-flash",
            system_instruction=SYSTEM_PROMPTS[agent_num],
        )
        response = model.generate_content(build_prompt(agent_num, data, context))
        return response.text
    except Exception as e:
        return f"[Agent {agent_num} 執行失敗且備援無效：{str(e)[:50]}]"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 主要執行管道
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AGENT_NAMES = {
    1: "商業模式與整體分析",
    2: "五年財務深度分析",
    3: "競爭護城河評估",
    4: "投資銀行估值分析",
    5: "未來成長潛力",
    6: "多空辯論",
    7: "最終投資決策",
}


def validate_analysis_output(agent_num: int, text: str) -> list[str]:
    """檢查模型輸出是否踩到硬性財務邏輯紅線。"""
    import re

    issues = []
    normalized = re.sub(r"\s+", "", text or "")

    has_dupont_gap = (
        ("ROA" in normalized)
        and ("權益乘數" in normalized)
        and any(word in normalized for word in ["差距", "落差", "不一致", "偏差"])
        and any(word in normalized for word in ["應付帳款", "非計息負債", "無息流動負債", "營運槓桿"])
    )
    if has_dupont_gap:
        issues.append(
            "杜邦分析紅線：同期間 ROE = ROA × 權益乘數（或淨利率 × 資產周轉 × 權益乘數）是恒等式；"
            "不同資料口徑造成的差距不得歸因於應付帳款或非計息負債。"
        )

    if agent_num == 4:
        dcf_pe_blend = (
            "DCF" in normalized
            and any(word in normalized for word in ["ForwardEPS", "預估EPS"])
            and any(word in normalized for word in ["完全吻合", "完全相符", "完全等於", "數學防呆"])
        )
        if dcf_pe_blend:
            issues.append(
                "估值方法紅線：DCF 與 EPS × P/E 是兩套不同估值法；P/E 乘法只能作相對估值交叉檢查，"
                "不得宣稱 DCF 必須與其完全吻合。"
            )

        book_value_wacc = (
            "WACC" in normalized
            and any(word in normalized for word in ["D/E", "負債權益比", "帳面"])
            and re.search(r"權益權重.{0,12}9[0-6]%", normalized)
        )
        if book_value_wacc:
            issues.append(
                "WACC 紅線：上市公司 WACC 權重應採市場價值資本結構；不可用帳面 D/E 直接推出股權權重。"
            )

    high_growth_fcf = (
        re.search(r"營收.{0,30}(?:成長|增加|提升|暴增).{0,12}(?:[5-9]\d|1\d\d)%", normalized)
        and (
            re.search(r"FCF.{0,20}(?:轉換率|/淨利).{0,12}(?:1\d\d|超過100|>100)%", normalized)
            or re.search(r"自由現金流.{0,20}(?:轉換率|/淨利).{0,12}(?:1\d\d|超過100|>100)%", normalized)
        )
    )
    fcf_has_caution = any(
        word in normalized
        for word in ["不可持續", "一次性", "異常", "需查核", "質疑", "預收", "營運資金", "資本支出", "CapEx", "遞延"]
    )
    if high_growth_fcf and not fcf_has_caution:
        issues.append(
            "FCF 品質紅線：硬體製造業在營收成長超過 50% 時仍有 FCF/淨利 >100%，不可視為常態；"
            "需拆解營運資金、預收款與 CapEx，DCF 應使用 normalized FCF。"
        )

    if agent_num in (4, 5, 7):
        aggressive_growth = re.search(r"營收.{0,30}(?:成長|增加|提升).{0,12}(?:[5-9]\d|1\d\d)%", normalized)
        no_capacity_cost = not any(word in normalized for word in ["CapEx", "資本支出", "折舊", "產能", "良率", "第二供應商"])
        if aggressive_growth and no_capacity_cost:
            issues.append(
                "製造業情境紅線：營收成長超過 50% 時，必須同步討論產能、CapEx、折舊、良率與客戶議價風險。"
            )

    if agent_num in (4, 7):
        high_multiple = re.search(r"(?:ForwardP/E|目標本益比|合理ForwardP/E|給予).{0,20}(?:2[5-9]|[3-9]\d)(?:\.\d+)?x", normalized)
        high_implied_growth = (
            re.search(r"營收.{0,40}(?:成長|增長|暴增|增加|提升).{0,20}(?:[5-9]\d|1\d\d)%", normalized)
            or ("ForwardEPS" in normalized and "隱含" in normalized and any(word in normalized for word in ["營收需", "營收必須", "營收要"]))
        )
        if high_multiple and high_implied_growth:
            issues.append(
                "雙重樂觀紅線：若 Forward EPS/財測已隱含營收暴增，不應再套用高 Forward P/E 重複計價成長；"
                "基本情境應使用折讓倍數或 normalized DCF。"
            )

    return issues


def append_quality_warnings(agent_num: int, text: str) -> str:
    issues = validate_analysis_output(agent_num, text)
    if not issues:
        return text

    warning_lines = "\n".join(f"- {issue}" for issue in issues)
    return (
        f"{text}\n\n"
        "## 系統品質檢查警示\n"
        "以下內容觸發硬性財務邏輯檢查；閱讀本段分析時請優先採用警示所述修正口徑：\n"
        f"{warning_lines}"
    )


def _count_unqualified_alias(text: str, alias: str, peer_code=None) -> int:
    """Count suspicious alias mentions that are not clearly marked as peer comparisons."""
    if not text or not alias:
        return 0

    count = 0
    peer_tokens = []
    if peer_code:
        peer_tokens = [peer_code, f"{peer_code}.TW", f"{peer_code}.TWO"]

    peer_context_words = [
        "同業",
        "競爭",
        "競品",
        "對手",
        "可比",
        "比較",
        "peer",
        "Peers",
        "同業比較",
    ]

    for match in re.finditer(re.escape(alias), text, flags=re.IGNORECASE):
        window = text[max(0, match.start() - 30): min(len(text), match.end() + 30)]
        if peer_tokens and any(token in window for token in peer_tokens):
            continue
        if any(word in window for word in peer_context_words):
            continue
        count += 1
    return count


def validate_company_identity(text: str, data: dict) -> list[str]:
    """Detect target-company identity contamination before it enters later-agent context."""
    identity = data.get("company_identity", {}) or {}
    if not identity or not text:
        return []

    issues = []
    ticker = data.get("ticker", identity.get("ticker", ""))
    stock_id = identity.get("stock_id", ticker.replace(".TW", "").replace(".TWO", ""))
    official_name = identity.get("official_name")
    allowed_aliases = set(identity.get("allowed_aliases", []))
    forbidden_aliases = set(identity.get("forbidden_aliases", []))

    current_ticker_patterns = [
        re.escape(ticker),
        re.escape(stock_id),
        rf"{re.escape(stock_id)}\.(?:TW|TWO)",
    ]

    def alias_bound_to_current_ticker(alias: str) -> bool:
        alias_re = re.escape(alias)
        for ticker_re in current_ticker_patterns:
            patterns = [
                rf"{alias_re}\s*[（(]\s*{ticker_re}",
                rf"{ticker_re}\s*[）)]?\s*{alias_re}",
            ]
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
                return True
        return False

    for alias in identity.get("forbidden_aliases", []):
        if len(alias) < 2:
            continue
        if alias_bound_to_current_ticker(alias):
            issues.append(f"公司身分錯置：輸出將「{alias}」綁定到本次標的 {ticker}。")
            continue
        unqualified_count = _count_unqualified_alias(text, alias)
        if unqualified_count >= 2:
            issues.append(f"公司身分污染：輸出中多次以「{alias}」作為主體，疑似套用了錯誤公司。")

    for peer in identity.get("same_industry_peers", []):
        peer_name = peer.get("stock_name", "")
        peer_code = peer.get("stock_id", "")
        # 同業名單裡有不少兩字名稱會同時是產業普通名詞（例如「綠電」）。
        # 這類詞只適合在「代號綁定錯置」時攔截，不能單靠出現次數判定為公司身分污染。
        if not peer_name or peer_name in allowed_aliases or peer_name in forbidden_aliases:
            continue
        if alias_bound_to_current_ticker(peer_name):
            issues.append(f"公司身分錯置：同業「{peer_name}」被綁定到本次標的 {ticker}。")
            continue
        if len(peer_name) < 3:
            continue
        unqualified_count = _count_unqualified_alias(text, peer_name, peer_code=peer_code)
        if unqualified_count >= 4:
            issues.append(f"公司身分污染：同業「{peer_name}」在未標示為同業的脈絡中出現 {unqualified_count} 次。")

    if official_name and issues and official_name not in text:
        issues.append(f"公司身分缺失：輸出未使用官方中文名稱「{official_name}」。")

    return list(dict.fromkeys(issues))


def build_identity_retry_instruction(data: dict, issues: list[str]) -> str:
    """Tell the model exactly why the prior output was rejected."""
    identity = data.get("company_identity", {}) or {}
    official_name = identity.get("official_name") or data.get("company_name", data.get("ticker", "本公司"))
    ticker = data.get("ticker", identity.get("ticker", "N/A"))
    issue_lines = "\n".join(f"- {issue}" for issue in issues)
    return (
        "🚨【前一次輸出已被系統退件，請重寫】\n"
        f"退件原因：\n{issue_lines}\n"
        f"請完全重寫本段，唯一主體必須是「{official_name}（{ticker}）」；"
        "不得使用同業公司名稱作為本公司稱呼，也不得把同業商業模式、專案或新聞套用到本公司。"
    )


def append_identity_warnings(text: str, issues: list[str]) -> str:
    if not issues:
        return text
    warning_lines = "\n".join(f"- {issue}" for issue in issues)
    return (
        f"{text}\n\n"
        "## 系統身分一致性警示\n"
        "本段未通過公司身分一致性檢查，報告不應作為正式輸出：\n"
        f"{warning_lines}"
    )


def sanitize_model_output(text: str) -> str:
    """Remove prompt/scratchpad leakage before it enters reports or later-agent context."""
    if not text:
        return ""

    leak_patterns = [
        r"^\s*(Morgan Stanley Taiwan Research Department Financial Modeling Expert|Competitive Advantage Analyst at BlackRock|BlackRock Active Investment Research Team|Growth Equity Researcher at Fidelity|Fidelity Investments Growth Equity Researcher)\b",
        r"^\s*你好，我是(高盛|摩根士丹利|貝萊德|JP\s*摩根|富達投資|T\.?\s*Rowe|德富金融)",
        r"^\s*(Deep financial analysis of|Deep financial data analysis of|Economic Moat analysis of|.*Deep moat evaluation|.*Analyze the growth potential|Analyze the growth potential|Analyze the 5-10 year growth potential of|Financial data provided)\b",
        r"^\s*\*?\s*(Currency|Units|TTM units|Debt to Equity|Manufacturing Logic|Valuation Cross-check|Forward EPS implicit.*|FCF quality check.*|WACC|DuPont Analysis|ROE Discrepancy|Language|Unit Check|Tone|Constraint Check|First paragraph MUST|No internal monologue)\s*:",
        r"^\s*\*?\s*(Specific scoring format|Traditional Chinese|Rigorous adherence|Cross-check Forward EPS|Manufacturing logic|First paragraph MUST|No internal monologue)\b",
        r"^\s*\*?\s*(Observation|The Red Flag|Action|Company Profile|Financials \(Key Highlights\))\s*:",
        r"^\s*\*?\s*(Section\s+[IVX0-9]+|TAM|SAM|SOM|Estimation)\s*:",
        r"^\s*\d+\.\s*(Market Size|Key Growth Drivers|AI\s*&\s*New Tech Impact|Long-term Market Share|5-Year Growth Scenarios|Overall Growth Potential)",
        r"^\s*\*?\s*(Data|Trend|Calculation|Driver|Net Profit|Margins|Quality|Critical Check|Conversion Rate|Warning Flag|Total Debt|Net Cash Position|Valuation|Growth|Key Product|Intellectual Property)\s*:",
        r"\b(I must|I need to|Let's|Wait:|As a Fidelity researcher)\b",
    ]
    leak_re = re.compile("|".join(leak_patterns), re.IGNORECASE)

    kept_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if leak_re.search(stripped):
            continue
        kept_lines.append(line)

    cleaned = "\n".join(kept_lines)
    cleaned = normalize_bad_number_commas(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def normalize_bad_number_commas(text: str) -> str:
    """Fix values like 1,0064.8億 -> 10,064.8億."""
    def repl(match):
        raw = f"{match.group(1)}{match.group(2)}"
        decimal = match.group(3) or ""
        return f"{int(raw):,}{decimal}"

    return re.sub(r"(?<!\d)(\d),(\d{4})(\.\d+)?(?=億)", repl, text or "")


def _parse_price_number(raw: str) -> float:
    return float(raw.replace(",", ""))


def _extract_price_numbers(text: str) -> list[float]:
    """Extract currency-like prices while preserving thousands separators."""
    import re

    number_pattern = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
    currency_matches = re.findall(rf"(?:NT\$?|\$)\s*({number_pattern})", text)
    matches = currency_matches or re.findall(number_pattern, text)
    return [_parse_price_number(match) for match in matches]


def run_analysis_pipeline(data: dict, progress_callback=None) -> dict:
    """
    執行完整的 7-Agent 連續分析管道
    
    Args:
        data: 從 financial_data.fetch_stock_data() 返回的數據字典
        progress_callback: 進度回調函數（可選）
    
    Returns:
        包含所有分析結果的 context 字典
    """
    ticker = data["ticker"]
    name = data["company_name"]
    
    # 初始化輪調器和上下文
    rotator = KeyRotator(API_KEYS)
    context = {
        "ticker": ticker,
        "company_name": name,
        "data": data,
        "analyses": {},
        "start_time": time.time(),
    }
    
    print(f"\n{'='*60}")
    print(f"  🚀 開始分析 {ticker} {name}")
    print(f"  📅 時間：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  🔑 可用 API Keys：{len(API_KEYS)} 組（輪調中）")
    print(f"{'='*60}\n")
    
    for agent_num in range(1, 8):
        agent_name = AGENT_NAMES[agent_num]
        model_id = AGENT_MODELS[agent_num]
        
        print(f"{'─'*60}")
        print(f"  📌 Agent {agent_num}/7：{agent_name}")
        print(f"  🤖 模型：{model_id}")
        print(f"{'─'*60}")
        
        start = time.time()
        
        result = run_single_agent(agent_num, data, context, rotator)
        result = sanitize_model_output(result)

        identity_issues = validate_company_identity(result, data)
        if identity_issues:
            print("  🚨 公司身分一致性檢查未通過，退回 Agent 重寫...")
            for issue in identity_issues:
                print(f"     - {issue}")
            context["_identity_retry_instruction"] = build_identity_retry_instruction(data, identity_issues)
            retry_result = run_single_agent(agent_num, data, context, rotator)
            retry_result = sanitize_model_output(retry_result)
            retry_issues = validate_company_identity(retry_result, data)
            context.pop("_identity_retry_instruction", None)

            result = retry_result
            identity_issues = retry_issues
            if identity_issues:
                print("  ❌ 重寫後仍未通過公司身分一致性檢查，停止產生正式報告。")
                for issue in identity_issues:
                    print(f"     - {issue}")
                context.setdefault("blocking_issues", []).extend(
                    f"Agent {agent_num} {agent_name}: {issue}"
                    for issue in identity_issues
                )
                result = append_identity_warnings(result, identity_issues)
            else:
                print("  ✅ 重寫後通過公司身分一致性檢查。")

        result = append_quality_warnings(agent_num, result)
        
        elapsed = time.time() - start
        context["analyses"][agent_num] = result
        
        print(f"  ✅ 完成！耗時 {elapsed:.1f} 秒")
        print(f"  📝 輸出長度：{len(result)} 字元")
        
        # 顯示結果前 100 字
        preview = result[:120].replace("\n", " ")
        print(f"  💬 預覽：{preview}...")
        
        if progress_callback:
            progress_callback(agent_num, 7, agent_name)

        if context.get("blocking_issues"):
            break
        
        # Agent 之間的延遲（避免速率限制）
        if agent_num < 7:
            wait = INTER_AGENT_DELAY
            print(f"\n  ⏰ 等待 {wait} 秒後執行下一個 Agent...\n")
            time.sleep(wait)
    
    # 解析結構化數據
    context["parsed"] = parse_structured_data(context)
    context["total_time"] = time.time() - context["start_time"]
    
    print(f"\n{'='*60}")
    print(f"  🎉 分析完成！總耗時：{context['total_time']:.1f} 秒")
    print(f"{'='*60}\n")
    
    return context


def parse_structured_data(context: dict) -> dict:
    """解析 Agent 輸出中的結構化數據（評分、目標價等）"""
    parsed = {
        "moat_scores": {},
        "price_targets": {},
        "recommendation": {},
    }
    
    # 解析護城河評分（Agent 3）
    if 3 in context["analyses"]:
        text = context["analyses"][3]
        try:
            import re
            allowed_moat_keys = {"品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "整體護城河"}
            moat_section = re.search(r'\[護城河評分\](.*?)\[/護城河評分\]', text, re.DOTALL)
            if moat_section:
                moat_text = moat_section.group(1)
                for line in moat_text.strip().split('\n'):
                    if ':' in line or '：' in line:
                        sep = ':' if ':' in line else '：'
                        key, val = line.split(sep, 1)
                        key = re.sub(r"^[\s*・\-]+", "", key).strip()
                        if key not in allowed_moat_keys:
                            continue
                        val = val.strip()
                        try:
                            score = float(re.search(r'[\d.]+', val).group())
                            parsed["moat_scores"][key] = min(score, 10)
                        except Exception:
                            pass
        except Exception:
            pass
    
    # 設定預設護城河分數（如解析失敗）
    if not parsed["moat_scores"]:
        parsed["moat_scores"] = {
            "品牌影響力": 6,
            "網路效應": 4,
            "轉換成本": 7,
            "成本優勢": 7,
            "專利技術": 6,
            "整體護城河": 6,
        }
    
    # 解析目標股價（Agent 4）
    if 4 in context["analyses"]:
        text = context["analyses"][4]
        try:
            import re
            # --- Primary: parse [目標股價] block ---
            price_section = re.search(r'\[目標股價\](.*?)\[/目標股價\]', text, re.DOTALL)
            if price_section:
                price_text = price_section.group(1)
                for line in price_text.strip().split('\n'):
                    if ':' in line or '：' in line:
                        sep = ':' if ':' in line else '：'
                        key, val = line.split(sep, 1)
                        key = key.strip()
                        prices = _extract_price_numbers(val)
                        if prices:
                            price_val = prices[0]
                            if price_val > 1:  # 排除百分比數字
                                parsed["price_targets"][key] = price_val
            
            # --- Fallback: parse from markdown tables or inline text ---
            if not parsed["price_targets"]:
                scenario_map = {
                    "熊市": ["熊市", "bear", "Bear"],
                    "基本": ["基本", "base", "Base"],
                    "牛市": ["牛市", "bull", "Bull"],
                }
                for label, keywords in scenario_map.items():
                    for kw in keywords:
                        # 在 kw 後面的文字中找 NT$ 數字，忽略百分比行
                        number_pattern = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{2,6}(?:\.\d+)?"
                        pattern = rf'{kw}.{{0,80}}?(?:NT\$|\$|合理股價|目標價|合理價值)\s*:?\s*({number_pattern})'
                        m = re.search(pattern, text)
                        if m:
                            price_val = _parse_price_number(m.group(1))
                            if price_val > 10:  # 合理股價應 > 10
                                key_name = f"{label}情境"
                                parsed["price_targets"][key_name] = price_val
                                break

            current_price = context.get("data", {}).get("current_price")
            if isinstance(current_price, (int, float)) and current_price > 100:
                suspicious = [
                    key for key, price in parsed["price_targets"].items()
                    if isinstance(price, (int, float)) and price < current_price * 0.05
                ]
                if suspicious:
                    reparsed = {}
                    for line in text.splitlines():
                        if not any(label in line for label in ["熊市", "基本", "牛市"]):
                            continue
                        values = [value for value in _extract_price_numbers(line) if value >= current_price * 0.05]
                        if not values:
                            continue
                        if "熊市" in line:
                            reparsed["熊市情境"] = values[0]
                        elif "基本" in line:
                            reparsed["基本情境"] = values[0]
                        elif "牛市" in line:
                            reparsed["牛市情境"] = values[0]
                    if reparsed:
                        parsed["price_targets"] = reparsed
        except Exception:
            pass
    
    # 解析投資建議（Agent 7）
    if 7 in context["analyses"]:
        text = context["analyses"][7]
        try:
            import re
            rec_section = re.search(r'\[投資建議\](.*?)\[/投資建議\]', text, re.DOTALL)
            if rec_section:
                rec_text = rec_section.group(1)
                for line in rec_text.strip().split('\n'):
                    if ':' in line or '：' in line:
                        sep = ':' if ':' in line else '：'
                        key, val = line.split(sep, 1)
                        parsed["recommendation"][key.strip()] = val.strip()
        except Exception:
            pass
    
    return parsed
