"""Agent-specific RAG queries and context formatting."""

from __future__ import annotations

from typing import Any

from agent_catalog import AGENT_NAMES

from .types import RagSearchResult


AGENT_RAG_QUERIES = {
    1: "business model revenue segments supply chain customers product mix management strategy concentration pricing power disruption 供應鏈 客戶集中 價格壓力 替代風險",
    2: "five year financial statements revenue margin free cash flow balance sheet debt profitability cash conversion working capital capex impairment restatement 財務 報表 現金流 轉換率 營運資金 減損",
    3: "competitive moat peers switching costs technology patents cost advantage market share commoditization substitution entry barrier customer churn 護城河 競爭 替代 商品化 弱項",
    4: "valuation DCF WACC FCF PE multiple target price capex margin assumptions sensitivity terminal value estimate revision downside 估值 折現 同業 倍數 下修 敏感度",
    5: "growth drivers TAM demand catalysts capacity AI technology long term opportunity risks bottleneck adoption cycle competition margin dilution 成長 產能 瓶頸 技術 擴張 逆風",
    6: "bull bear debate catalysts risks valuation controversy downside upside counterarguments downgrade miss warning headwind estimate cut guidance cut demand slowdown margin compression customer concentration inventory correction 衰退 下修 警告 逆風 降評 未達預期 砍單 庫存去化 毛利率壓力 競爭",
    7: "final investment decision recommendation target price confidence risks catalysts valuation institutional flow downgrade miss warning downside upside risk event 籌碼 外資 投信 下修 降評 催化 風險",
    11: "macro economy interest rates inflation geopolitics policy tariff subsidy industry cycle inventory destocking capex expansion demand supply headwind tailwind 總經 利率 通膨 地緣政治 政策 產業週期 去庫存 順風 逆風",
    12: "business model economic moat revenue mechanism switching costs scale economy brand patents peers margin market share competitive erosion 商業模式 賺錢機制 護城河 轉換成本 規模經濟 毛利率 競爭侵蝕",
    13: "forensic accounting red flags free cash flow conversion inventory receivables margin deterioration debt leverage DuPont ROE liquidity capex 財務排雷 紅旗 自由現金流 存貨 應收帳款 毛利率惡化 槓桿 杜邦",
    14: "growth valuation DCF TAM SAM catalysts revenue growth FCF growth WACC forward PE PB estimate revision double counting 估值 成長 本益比 目標價 法說 催化 雙重樂觀 下修",
    15: "institutional trading foreign investors investment trust dealer net buy sell technical sentiment PE river chart crowded trade breakout momentum 法人 外資 投信 自營商 買賣超 籌碼 技術面 情緒 河流圖 動能",
    16: "portfolio manager trading decision bull bear actionable plan risk control entry exit timing valuation chip flow macro red flags left side trade 實戰交易 進出場 風控 多空 籌碼 估值 總經 紅旗 左側交易",
}


def _agent_query(agent_num: int, data: dict[str, Any]) -> str:
    return " ".join([
        str(data.get("ticker") or ""),
        str(data.get("company_name") or ""),
        str(data.get("industry") or ""),
        AGENT_NAMES.get(agent_num, f"Agent {agent_num}"),
        AGENT_RAG_QUERIES.get(agent_num, ""),
    ]).strip()


def _format_results(results: list[RagSearchResult], agent_num: int) -> str:
    if not results:
        return ""
    parts = [
        f"【RAG 語意檢索精選資料｜Agent {agent_num}】",
        "以下片段來自長篇法說會、財報、新聞或外部長文本；只可作為引用依據，不可假設已讀全文。",
    ]
    for idx, result in enumerate(results, 1):
        score = f"{result.score:.3f}" if isinstance(result.score, float) else str(result.score)
        parts.append(
            f"【片段 {idx}｜來源：{result.chunk.source}｜相關度：{score}】\n"
            f"{result.chunk.text}"
        )
    return "\n\n".join(parts)
