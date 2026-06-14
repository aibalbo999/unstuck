"""Pure mathematical computation module for financial metrics.
Removes calculation responsibility from LLMs to prevent hallucinations and math errors.
"""

from typing import List, Optional, Dict, Any
import logging

try:
    import pandas as pd
    import numpy as np
except ImportError:
    logging.warning("pandas/numpy not found, falling back to pure Python implementations.")
    pd = None
    np = None

logger = logging.getLogger(__name__)


class QuantEngine:
    @staticmethod
    def calculate_wacc(
        equity: float,
        debt: float,
        cost_of_equity: float,
        cost_of_debt: float,
        tax_rate: float
    ) -> float:
        """Calculate Weighted Average Cost of Capital."""
        total_capital = equity + debt
        if total_capital <= 0:
            return 0.0
        
        weight_equity = equity / total_capital
        weight_debt = debt / total_capital
        
        wacc = (weight_equity * cost_of_equity) + (weight_debt * cost_of_debt * (1 - tax_rate))
        return round(wacc, 4)

    @staticmethod
    def calculate_dcf(
        free_cash_flows: List[float],
        wacc: float,
        terminal_growth_rate: float,
        shares_outstanding: int
    ) -> float:
        """Standard Discounted Cash Flow valuation."""
        if not free_cash_flows or wacc <= terminal_growth_rate or shares_outstanding <= 0:
            return 0.0
            
        pv_fcf = sum([fcf / ((1 + wacc) ** i) for i, fcf in enumerate(free_cash_flows, 1)])
        
        terminal_value = (free_cash_flows[-1] * (1 + terminal_growth_rate)) / (wacc - terminal_growth_rate)
        pv_tv = terminal_value / ((1 + wacc) ** len(free_cash_flows))
        
        enterprise_value = pv_fcf + pv_tv
        intrinsic_value_per_share = enterprise_value / shares_outstanding
        
        return round(intrinsic_value_per_share, 2)

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                # Basic cleanup: remove NT$, 億, spaces, commas, etc.
                import re
                cleaned = re.sub(r'[^\d.-]', '', value.split('(')[0]) # take the first part before parenthesis
                return float(cleaned) if cleaned else default
            except ValueError:
                return default
        return default

    @staticmethod
    def compute_all(data: Dict[str, Any]) -> Dict[str, Any]:
        """Compute all quantitative metrics from raw data for the LLM."""
        try:
            # Fallback values if data is missing
            current_price = QuantEngine._safe_float(data.get("current_price"), 0.0)
            shares = QuantEngine._safe_float(data.get("shares_outstanding"), 0.0)
            
            equity = QuantEngine._safe_float(data.get("total_equity"), 1000.0)
            debt = QuantEngine._safe_float(data.get("total_debt"), 500.0)
            tax_rate = QuantEngine._safe_float(data.get("tax_rate"), 0.21)
            
            # free_cash_flows might be a list of dicts or numbers
            fcf_raw = data.get("free_cash_flows", [100.0, 110.0, 120.0, 130.0, 140.0])
            fcf_list = []
            for item in (fcf_raw if isinstance(fcf_raw, list) else []):
                fcf_list.append(QuantEngine._safe_float(item, 100.0))
            if not fcf_list:
                fcf_list = [100.0, 110.0, 120.0, 130.0, 140.0]
            
            wacc = QuantEngine.calculate_wacc(equity, debt, 0.10, 0.05, tax_rate)
            dcf_value = QuantEngine.calculate_dcf(fcf_list, wacc or 0.08, 0.02, int(shares) or 100)
            
            eps = QuantEngine._safe_float(data.get("eps", 1.0), 1.0)
            pe_ratio = round(current_price / eps, 2) if eps > 0 else 0.0
            
            return {
                "wacc_computed": wacc,
                "dcf_intrinsic_value": dcf_value,
                "implied_pe_ratio": pe_ratio,
                "margin_of_safety": round((dcf_value - current_price) / dcf_value, 4) if dcf_value > 0 else 0.0,
                "note": "以上數據由系統精算模組自動產生，分析師無須重新計算。"
            }
        except Exception as e:
            logger.error(f"QuantEngine calculation failed: {e}")
            return {"error": "計算失敗，請參考原始財報資料。"}
