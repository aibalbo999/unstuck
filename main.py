#!/usr/bin/env python3
# ============================================================
# main.py - 連續式股票分析 Agent 系統入口
# 使用方式：python main.py --ticker 2449.TW
# ============================================================

import sys
import os
import time
import argparse
import asyncio
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.rule import Rule
from rich.table import Table

# 確保 backend 模組可由專案根目錄執行
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

from agent_catalog import AGENT_NAMES
from config import OUTPUT_DIR, API_KEYS, format_model_routes, AGENT_MODELS
from data_fetch import FetchRequest, StockDataService
from pipeline_modes import get_pipeline_definition, normalize_pipeline_id
from analysis_jobs import build_data_fetch_blocking_notice
from agent_runtime import AnalysisPipelineRunner, AnalysisRequest
from reporting import ReportRenderer, ReportRequest
from temporal_memory_service import build_temporal_memory
from quant_engine import QuantEngine
from report_persistence import persist_report_bundle
from storage.report_storage import LocalFileStorage

console = Console()

STOCK_DATA_SERVICE = StockDataService()
PIPELINE_RUNNER = AnalysisPipelineRunner()
REPORT_RENDERER = ReportRenderer()

def print_banner():
    """顯示系統啟動橫幅"""
    console.print(Panel(
        "[bold blue]🏦 股票連續式分析 Agent 系統[/bold blue]\n"
        f"[dim]{len(API_KEYS)}組 API Key 輪調 · 雙模型架構[/dim]\n"
        f"[dim]{format_model_routes()}[/dim]",
        title="[bold white]Evidence-Grounded Equity Research[/bold white]",
        border_style="blue",
        padding=(1, 4),
    ))

def print_config_table(pipeline_def: dict):
    """顯示系統配置表"""
    table = Table(title=f"系統配置 ({pipeline_def['label']})", border_style="dim", show_header=True, header_style="bold cyan")
    table.add_column("Agent", style="cyan", width=4)
    table.add_column("分析主題", style="white")
    table.add_column("使用模型", style="green")
    table.add_column("功能性角色", style="yellow")
    
    roles = {
        1: "商業模式與產業證據分析",
        2: "GAAP 財務品質驗證",
        3: "護城河證據評分",
        4: "DCF 與相對估值計算",
        5: "成長可執行性驗證",
        6: "多空證據對撞",
        7: "情境風險整合",
        11: "財務上下文摘要",
        12: "動態護城河評估",
        13: "事件與籌碼分析",
        14: "DCF與情境估值",
        15: "主力與法人籌碼",
        16: "決策與風險評估",
        17: "大盤與資金流向",
        18: "做空觸發條件檢查",
        19: "逆勢決策與防軋空",
        20: "同業估值矩陣",
        21: "法人目標價對齊",
        22: "技術與動能分析",
        23: "近期催化劑",
        24: "極短線交易設定",
    }
    
    agent_sequence = pipeline_def["agents"]
    for num in agent_sequence:
        name = AGENT_NAMES.get(num, f"Agent {num}")
        model = AGENT_MODELS.get(num, "N/A")
        table.add_row(str(num), name, model, roles.get(num, "N/A"))
    
    console.print(table)
    console.print()

def print_key_status():
    """顯示 API Key 狀態"""
    key_info = Table(title="API Key 配置", border_style="dim", show_header=True, header_style="bold cyan")
    key_info.add_column("Key", style="cyan", width=5)
    key_info.add_column("Key ID（前8碼）", style="white")
    key_info.add_column("狀態", style="green")
    
    for i, key in enumerate(API_KEYS, 1):
        key_info.add_row(f"Key-{i}", f"{key[:8]}...{key[-4:]}", "✅ 待命中")
    
    console.print(key_info)
    console.print()


async def main_async():
    """主函數非同步進入點"""
    
    # ─── 解析命令列參數 ──────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="股票連續式分析 Agent 系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例：
  python main.py --ticker 2449.TW          # 分析京元電子 (預設模式 A)
  python main.py --ticker 2330.TW --pipeline v2 # 使用模式 B (實戰交易派)
  python main.py --ticker NVDA --pipeline v3    # 使用模式 C (逆勢交易派)
        """
    )
    parser.add_argument("--ticker", required=True, help="股票代號（例如：2449.TW）")
    parser.add_argument("--pipeline", default="v1", help="Pipeline 模式 (v1=模式A, v2=模式B, v3=模式C, v4=模式D)")
    parser.add_argument("--no-report", action="store_true", help="不生成 HTML 報告")
    
    args = parser.parse_args()
    ticker = args.ticker.upper().strip()
    pipeline_id = normalize_pipeline_id(args.pipeline)
    pipeline_def = get_pipeline_definition(pipeline_id)
    
    # ─── 顯示啟動畫面 ────────────────────────────────────────
    print_banner()
    print_config_table(pipeline_def)
    print_key_status()
    
    console.print(Rule(f"[bold]開始分析：[blue]{ticker}[/blue] - {pipeline_def['label']}", style="blue"))
    console.print()
    
    # ─── 獲取財務數據 ─────────────────────────────────────────
    console.print("[bold cyan]📊 步驟 1/3：獲取財務數據...[/bold cyan]")
    
    with console.status("[bold green]連接資料來源中...[/bold green]", spinner="dots"):
        data_result = await STOCK_DATA_SERVICE.fetch_async(FetchRequest.from_ticker(ticker))
    
    data = data_result.data
    blocking_notice = build_data_fetch_blocking_notice(data_result)
    
    if blocking_notice:
        console.print(f"\n[bold red]❌ 熔斷機制觸發：{blocking_notice['message']}[/bold red]")
        sys.exit(1)
        
    if "error" in data:
        console.print(f"[yellow]⚠️  財務數據部分獲取失敗：{data['error']}[/yellow]")
        console.print("[dim]將繼續使用已獲取的部分數據進行分析...[/dim]")
    
    # 顯示獲取的基本資訊
    info_table = Table(show_header=False, border_style="dim", box=None, padding=(0, 2))
    info_table.add_column("欄位", style="dim")
    info_table.add_column("數值", style="bold white")
    
    fields = [
        ("公司名稱", data.get("company_name", "N/A")),
        ("股票代號", data.get("ticker", "N/A")),
        ("產業", f"{data.get('sector', 'N/A')} · {data.get('industry', 'N/A')}"),
        ("當前股價", data.get("current_price_fmt", "N/A")),
        ("市值", data.get("market_cap_fmt", "N/A")),
        ("P/E 比率", data.get("pe_ratio", "N/A")),
        ("毛利率", data.get("gross_margin", "N/A")),
        ("ROE", data.get("roe", "N/A")),
        ("殖利率", data.get("dividend_yield", "N/A")),
    ]
    
    for field, value in fields:
        info_table.add_row(field, str(value))
    
    console.print(Panel(info_table, title="[bold]財務數據快覽[/bold]", border_style="dim"))
    console.print()
    
    # 注入時間記憶與 Quant Metrics
    temporal_memory = build_temporal_memory(ticker, output_dir=OUTPUT_DIR, current_price=data.get("current_price"))
    if temporal_memory:
        data["temporal_memory"] = temporal_memory
        console.print("[dim]已載入上一期報告記憶。[/dim]")
        
    metrics_snapshot = QuantEngine.compute_all(data)
    data["quant_metrics"] = metrics_snapshot
    if metrics_snapshot.get("fallback_fields"):
        data["quant_metrics"]["__has_fallback"] = True
    
    # ─── 執行 Agent 管道 ─────────────────────────────────────
    agent_sequence = pipeline_def["agents"]
    total_agents = len(agent_sequence)
    console.print(f"[bold cyan]🤖 步驟 2/3：執行 {total_agents} 個分析 Agent...[/bold cyan]")
    console.print("[dim]動態共享速率限制與 429 指數退避已啟用[/dim]")
    console.print()
    
    start_time = time.time()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=False,
    ) as progress:
        
        task = progress.add_task("[cyan]分析中...", total=total_agents)
        
        def update_progress(current, total=None, name=None, phase="completed", message=None, **kwargs):
            # 適配 AnalysisPipelineRunner 所傳遞的進度字典
            raw_event = current if isinstance(current, dict) else {}
            if raw_event:
                current_val = raw_event.get("current", 0)
                total_val = raw_event.get("total", total_agents)
                desc_name = raw_event.get("name") or raw_event.get("message") or "分析中"
            else:
                current_val = current
                total_val = total or total_agents
                desc_name = name or message or "分析中"
                
            # 由於 current 可能是單個 Agent 狀態而不是總進度，簡單起見在此只更新文字，若有精確進度則更新進度條
            if isinstance(current_val, int) and current_val <= total_agents:
                progress.update(task, completed=current_val, total=total_val, description=f"[cyan]{desc_name}")
            else:
                progress.update(task, total=total_val, description=f"[cyan]{desc_name}")

        analysis_req = AnalysisRequest(
            data=data,
            pipeline_id=pipeline_id,
            progress_callback=update_progress
        )
        
        analysis_result = await PIPELINE_RUNNER.run_async(analysis_req)
        context = analysis_result.context
    
    elapsed = time.time() - start_time
    console.print(f"\n[bold green]✅ 所有分析完成！總耗時：{elapsed:.0f} 秒 ({elapsed/60:.1f} 分鐘)[/bold green]")

    final_audit = context.get("final_audit", {}) or {}
    audit_critical = list(final_audit.get("critical", []) or [])
    blocking_issues = [
        issue for issue in (context.get("blocking_issues", []) or [])
        if issue not in audit_critical
    ]
    audit_issues = [*audit_critical[:8], *blocking_issues[:4]]
    if audit_issues:
        issue_text = "\n".join(f"- {issue}" for issue in audit_issues)
        console.print()
        console.print(Panel(
            f"[bold yellow]品質檢查仍有異常；系統會繼續輸出報告，並在報告內標示提醒。[/bold yellow]\n\n{issue_text}",
            title="[bold]品質檢查提醒[/bold]",
            border_style="yellow",
            padding=(1, 2),
        ))
    
    # ─── 顯示分析摘要 ─────────────────────────────────────────
    console.print()
    console.print(Rule("[bold]分析結果摘要[/bold]", style="green"))
    
    parsed = context.get("parsed", {})
    
    # 護城河評分
    moat_scores = parsed.get("moat_scores", {})
    if moat_scores:
        console.print("\n[bold cyan]🏰 護城河評分：[/bold cyan]")
        for key, val in moat_scores.items():
            bar = "█" * int(val) + "░" * (10 - int(val))
            color = "green" if val >= 7 else ("yellow" if val >= 5 else "red")
            console.print(f"  {key:12s} [{color}]{bar}[/{color}] {val}/10")
    
    # 目標股價
    price_targets = parsed.get("price_targets", {})
    if price_targets:
        console.print("\n[bold cyan]💰 目標股價：[/bold cyan]")
        colors = {"熊": "red", "基本": "blue", "牛": "green"}
        for scenario, price in price_targets.items():
            color = next((v for k, v in colors.items() if k in scenario), "white")
            console.print(f"  {scenario:20s} [bold {color}]NT${price:.0f}[/bold {color}]")
    
    # 極短線交易設定 (Mode D)
    trade_setup = parsed.get("trade_setup", {})
    if trade_setup:
        console.print("\n[bold cyan]⚡ 極短線交易設定：[/bold cyan]")
        for key, val in trade_setup.items():
            console.print(f"  {key}: {val}")
    
    # 投資建議
    recommendation = parsed.get("recommendation", {})
    if recommendation:
        console.print("\n[bold cyan]📋 最終投資建議：[/bold cyan]")
        for key, val in recommendation.items():
            rec_color = "green" if isinstance(val, str) and "買入" in val else ("red" if isinstance(val, str) and "避免" in val else "yellow")
            if "建議" in key:
                console.print(f"  {key}: [bold {rec_color}]{val}[/bold {rec_color}]")
            else:
                console.print(f"  {key}: {val}")
    
    # ─── 生成 HTML 報告 ───────────────────────────────────────
    if not args.no_report:
        console.print()
        console.print("[bold cyan]📄 步驟 3/3：生成 HTML/MD 報告與資料快照...[/bold cyan]")
        
        with console.status("[bold green]生成專業報告中...[/bold green]", spinner="dots"):
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_ticker = ticker.replace(".", "_")
            filename = f"{safe_ticker}_{pipeline_id}_report_{timestamp}.html"
            
            report_req = ReportRequest(
                context=context,
                pipeline_id=pipeline_id,
                filename=filename,
            )
            report_bundle = await REPORT_RENDERER.render_async(report_req)
            persisted = persist_report_bundle(
                filename=filename,
                html_content=report_bundle.html,
                markdown_content=report_bundle.markdown,
                data_snapshot=report_bundle.data_snapshot,
                storage=LocalFileStorage(OUTPUT_DIR),
                output_dir=OUTPUT_DIR,
            )
            html_path = os.path.join(OUTPUT_DIR, persisted["filename"])
            md_path = os.path.join(OUTPUT_DIR, persisted["md_filename"])
        
        abs_path = os.path.abspath(html_path)
        
        console.print()
        console.print(Panel(
            f"[bold green]✅ 報告與資料快照已生成並建立索引！[/bold green]\n\n"
            f"[bold white]HTML 路徑：[/bold white][blue]{abs_path}[/blue]\n"
            f"[bold white]MD 路徑：[/bold white][blue]{os.path.abspath(md_path)}[/blue]\n\n"
            f"[dim]可在 Web UI 的歷史報告中直接預覽，或在瀏覽器中開啟查看[/dim]",
            title="[bold]報告輸出[/bold]",
            border_style="green",
            padding=(1, 2),
        ))
        
        # 嘗試自動在瀏覽器中開啟（macOS）
        import subprocess
        try:
            subprocess.run(["open", abs_path], check=True, capture_output=True)
            console.print("[dim]已自動在瀏覽器中開啟 HTML 報告[/dim]")
        except Exception:
            console.print(f"[dim]請手動在瀏覽器中開啟：{abs_path}[/dim]")
    
    console.print()
    console.print(Panel(
        f"[bold blue]分析完成！[/bold blue]\n"
        f"股票：[bold]{ticker} {data.get('company_name', '')}[/bold]\n"
        f"總耗時：{elapsed:.0f} 秒\n"
        f"分析 Pipeline：{pipeline_def['label']} ({total_agents} 個 Agent)\n"
        f"使用模型：{format_model_routes()}",
        title="[bold]✨ 分析完成[/bold]",
        border_style="blue",
    ))
    
    return context


def main():
    """CLI 入口"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
