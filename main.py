#!/usr/bin/env python3
# ============================================================
# main.py - 連續式股票分析 Agent 系統入口
# 使用方式：python main.py --ticker 2449.TW
# ============================================================

import sys
import os
import time
import argparse
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.rule import Rule
from rich.table import Table
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

# 確保 backend 模組可由專案根目錄執行
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

from financial_data import fetch_stock_data
from agent_runner import run_analysis_pipeline, AGENT_NAMES, AGENT_MODELS
from report_gen import generate_html_report
from config import OUTPUT_DIR, API_KEYS, format_model_routes
from llm_client import is_quota_or_rate_error

console = Console()


def print_banner():
    """顯示系統啟動橫幅"""
    console.print(Panel(
        "[bold blue]🏦 股票連續式分析 Agent 系統[/bold blue]\n"
        f"[dim]7 個證據導向分析引擎 · {len(API_KEYS)}組 API Key 輪調 · 雙模型架構[/dim]\n"
        f"[dim]{format_model_routes()}[/dim]",
        title="[bold white]Evidence-Grounded Equity Research[/bold white]",
        border_style="blue",
        padding=(1, 4),
    ))


def print_config_table():
    """顯示系統配置表"""
    table = Table(title="系統配置", border_style="dim", show_header=True, header_style="bold cyan")
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
    }
    
    for num, name in AGENT_NAMES.items():
        model = AGENT_MODELS[num]
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


def save_report(html_content: str, ticker: str) -> str:
    """儲存 HTML 報告並返回路徑"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 生成檔案名稱
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_ticker = ticker.replace(".", "_")
    filename = f"{safe_ticker}_report_{timestamp}.html"
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    return filepath


def run_analysis_pipeline_with_backoff(data, progress_callback=None, wait_strategy=None):
    """Retry only quota/rate-limit failures with bounded exponential backoff."""
    retryer = Retrying(
        stop=stop_after_attempt(3),
        wait=wait_strategy or wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception(lambda exc: is_quota_or_rate_error(str(exc)) or "429" in str(exc)),
        reraise=True,
    )
    for attempt in retryer:
        with attempt:
            return run_analysis_pipeline(data, progress_callback=progress_callback)


def main():
    """主函數"""
    
    # ─── 解析命令列參數 ──────────────────────────────────────
    parser = argparse.ArgumentParser(
        description="股票連續式分析 Agent 系統",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用範例：
  python main.py --ticker 2449.TW          # 分析京元電子
  python main.py --ticker 2330.TW          # 分析台積電
  python main.py --ticker 2317.TW          # 分析鴻海
  python main.py --ticker NVDA             # 分析 NVIDIA（美股）
  python main.py --ticker 2449.TW --skip 1 # 從 Agent 2 開始（跳過 Agent 1）
        """
    )
    parser.add_argument("--ticker", required=True, help="股票代號（例如：2449.TW）")
    parser.add_argument("--skip", type=int, default=0, help="跳過前 N 個 Agent（用於續跑）")
    parser.add_argument("--no-report", action="store_true", help="不生成 HTML 報告")
    
    args = parser.parse_args()
    ticker = args.ticker.upper().strip()
    
    # ─── 顯示啟動畫面 ────────────────────────────────────────
    print_banner()
    print_config_table()
    print_key_status()
    
    console.print(Rule(f"[bold]開始分析：[blue]{ticker}[/blue]", style="blue"))
    console.print()
    
    # ─── 獲取財務數據 ─────────────────────────────────────────
    console.print("[bold cyan]📊 步驟 1/3：獲取財務數據...[/bold cyan]")
    
    with console.status("[bold green]連接 Yahoo Finance 中...[/bold green]", spinner="dots"):
        data = fetch_stock_data(ticker)
    
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
    
    # ─── 執行 Agent 管道 ─────────────────────────────────────
    console.print("[bold cyan]🤖 步驟 2/3：執行 7 個分析 Agent...[/bold cyan]")
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
        
        task = progress.add_task("[cyan]分析中...", total=7)
        
        def update_progress(current, total, name):
            progress.update(task, completed=current, description=f"[cyan]Agent {current}/7：{name}")
        
        context = run_analysis_pipeline_with_backoff(data, progress_callback=update_progress)
    
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
    
    # 投資建議
    recommendation = parsed.get("recommendation", {})
    if recommendation:
        console.print("\n[bold cyan]📋 最終投資建議：[/bold cyan]")
        for key, val in recommendation.items():
            rec_color = "green" if "買入" in val else ("red" if "避免" in val else "yellow")
            if "建議" in key:
                console.print(f"  {key}: [bold {rec_color}]{val}[/bold {rec_color}]")
            else:
                console.print(f"  {key}: {val}")
    
    # ─── 生成 HTML 報告 ───────────────────────────────────────
    if not args.no_report:
        console.print()
        console.print("[bold cyan]📄 步驟 3/3：生成 HTML 報告...[/bold cyan]")
        
        with console.status("[bold green]生成專業 HTML 報告中...[/bold green]", spinner="dots"):
            html_content = generate_html_report(context)
            report_path = save_report(html_content, ticker)
        
        abs_path = os.path.abspath(report_path)
        
        console.print()
        console.print(Panel(
            f"[bold green]✅ HTML 報告已生成！[/bold green]\n\n"
            f"[bold white]路徑：[/bold white][blue]{abs_path}[/blue]\n\n"
            f"[dim]在瀏覽器中開啟查看完整報告[/dim]",
            title="[bold]報告輸出[/bold]",
            border_style="green",
            padding=(1, 2),
        ))
        
        # 嘗試自動在瀏覽器中開啟（macOS）
        import subprocess
        try:
            subprocess.run(["open", abs_path], check=True, capture_output=True)
            console.print("[dim]已自動在瀏覽器中開啟報告[/dim]")
        except Exception:
            console.print(f"[dim]請手動在瀏覽器中開啟：{abs_path}[/dim]")
    
    console.print()
    console.print(Panel(
        f"[bold blue]分析完成！[/bold blue]\n"
        f"股票：[bold]{ticker} {data.get('company_name', '')}[/bold]\n"
        f"總耗時：{elapsed:.0f} 秒\n"
        f"分析 Agent：7 個\n"
        f"使用模型：{format_model_routes()}",
        title="[bold]✨ 分析完成[/bold]",
        border_style="blue",
    ))
    
    return context


if __name__ == "__main__":
    main()
