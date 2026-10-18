"""Capital-structure and DuPont notes for yfinance payload assembly."""

from __future__ import annotations

import pandas as pd
import time

from .formatting import format_number
from .market_sources.common import safe_get


def build_capital_structure_notes(
    stock,
    info: dict,
    *,
    revenue_history: list,
    net_income_history: list,
    total_assets_history: list,
    total_equity_history: list,
    market_cap,
    total_debt,
    financial_history_data: dict | None = None,
) -> dict:
    equity_multiplier = "N/A"
    equity_multiplier_note = ""
    dupont_identity_note = ""
    wacc_capital_structure_note = ""

    from .financial_history_basis import prompt_history_basis, INSTITUTION_SCHEMAS
    annual_inputs = {"revenue_history": revenue_history, "net_income_history": net_income_history,
                     "total_assets_history": total_assets_history, "total_equity_history": total_equity_history}
    official_basis = (prompt_history_basis(financial_history_data)
                      if isinstance(financial_history_data, dict)
                      and all(financial_history_data.get(key) == value for key, value in annual_inputs.items()) else {})
    try:
        from .annual_history_cache_freshness import primary_balance_frame
        balance_latest = None if official_basis else primary_balance_frame(financial_history_data,time.time())
        if not official_basis and balance_latest is None:
            balance_latest = stock.balance_sheet
        if official_basis:
            institution = official_basis["statement_schema"] in INSTITUTION_SCHEMAS
            insurer = official_basis["statement_schema"] == "insurer_standalone.v1"
            ordinary_individual = official_basis["statement_schema"] == "ordinary_individual.v1"
            individual = insurer or ordinary_individual
            income_label = "合併淨收益" if institution else "保險業個別營業收入" if insurer else "個別營業收入" if ordinary_individual else "申報營業收入"
            sector_label = "金融業" if institution else "保險業" if insurer else "一般業個別" if ordinary_individual else "證券商"
            asset_label = "個別資產" if individual else "合併資產"
            equity_label = "期末個別權益" if individual else "期末母公司權益"
            profit_label = "個別本期損益" if individual else "母公司淨利"
            latest_rev = financial_history_data["net_revenue_history"][-1] if institution else revenue_history[-1]
            latest_ni = net_income_history[-1]
            latest_assets, latest_equity = total_assets_history[-1], total_equity_history[-1]
            if latest_assets > 0 and latest_equity > 0:
                em = latest_assets / latest_equity
                equity_multiplier = f"{em:.3f}x"
                year = official_basis["years"][-1]
                equity_multiplier_note = f"{year} 年{sector_label}官方{asset_label}／{equity_label}；同年度原始科目。"
                if latest_rev > 0:
                    margin, turnover = latest_ni / latest_rev, latest_rev / latest_assets
                    same_period_roe = latest_ni / latest_equity * 100
                    dupont_identity_note = (
                        f"{year} 年{sector_label}同期間年度杜邦算式：{profit_label}／{income_label} {margin*100:.1f}% × "
                        f"{income_label}／期末資產 {turnover:.3f}x × 資產／{equity_label} {em:.3f}x "
                        f"= {same_period_roe:.1f}%（{profit_label}／{equity_label}，非平均權益 ROE）")
        if balance_latest is not None and not balance_latest.empty:
            ta_0 = balance_latest.loc["Total Assets"].iloc[0] if "Total Assets" in balance_latest.index else None
            eq_0 = balance_latest.loc["Stockholders Equity"].iloc[0] if "Stockholders Equity" in balance_latest.index else (
                balance_latest.loc["Total Equity Gross Minority Interest"].iloc[0] if "Total Equity Gross Minority Interest" in balance_latest.index else None)
            if ta_0 and eq_0 and float(eq_0) > 0 and not pd.isna(ta_0) and not pd.isna(eq_0):
                em = float(ta_0) / float(eq_0)
                equity_multiplier = f"{em:.3f}x"
                roa_raw = safe_get(info, "returnOnAssets", None)
                if roa_raw and roa_raw != "N/A":
                    dupont_roe = float(roa_raw) * em * 100
                    equity_multiplier_note = (
                        f"(僅供口徑差異提示：Yahoo ROA {float(roa_raw)*100:.1f}% × 最新期 EM "
                        f"{em:.3f}x = {dupont_roe:.1f}%，不可解讀為嚴格杜邦恒等式)"
                    )

                if revenue_history and net_income_history and total_assets_history and total_equity_history:
                    latest_rev = revenue_history[-1]
                    latest_ni = net_income_history[-1]
                    latest_assets = total_assets_history[-1]
                    latest_equity = total_equity_history[-1]
                    if latest_rev and latest_ni and latest_assets and latest_equity:
                        same_period_margin = latest_ni / latest_rev
                        same_period_turnover = latest_rev / latest_assets
                        same_period_em = latest_assets / latest_equity
                        same_period_roe = same_period_margin * same_period_turnover * same_period_em * 100
                        dupont_identity_note = (
                            f"同期間年度杜邦恒等式：淨利率 {same_period_margin*100:.1f}% × "
                            f"資產周轉率 {same_period_turnover:.3f}x × 權益乘數 {same_period_em:.3f}x "
                            f"= ROE {same_period_roe:.1f}%（等同淨利/股東權益）"
                        )
    except Exception:
        pass

    try:
        if isinstance(market_cap, (int, float)) and isinstance(total_debt, (int, float)):
            invested_capital = market_cap + total_debt
            if invested_capital > 0:
                equity_weight = market_cap / invested_capital * 100
                debt_weight = total_debt / invested_capital * 100
                wacc_capital_structure_note = (
                    f"WACC 市值權重：股權 {equity_weight:.2f}% / 有息負債 {debt_weight:.2f}% "
                    f"（以市值 {format_number(market_cap, '億')} 與有息負債 {format_number(total_debt, '億')} 計算）"
                )
    except Exception:
        pass

    return {
        "equity_multiplier": equity_multiplier,
        "equity_multiplier_note": equity_multiplier_note,
        "dupont_identity_note": dupont_identity_note,
        "wacc_capital_structure_note": wacc_capital_structure_note,
    }
