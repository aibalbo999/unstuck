/* Offline DOM, layout and chart checks. All browser requests are denied unless
 * the exact pinned Chart.js URL is fulfilled from a supplied local file. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_NODE_MODULE || 'playwright');
const args = process.argv.slice(2);
const option = name => args.includes(name) ? args[args.indexOf(name) + 1] : null;
const preview = option('--preview-dir');
const output = option('--output-dir');
const chartFile = option('--chart-js');
const root = path.resolve(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'backend/templates/includes/report_reader_script.html.j2'), 'utf8');
const style = fs.readFileSync(path.join(root, 'backend/templates/includes/report_reader_styles.html.j2'), 'utf8');

function fixture(mode, state = 'warning', observations = {}) {
    const rows = mode === 'trading' ? [['部位動作', '等待'], ['部位大小', '0%'], ['進場區間', 'N/A'], ['部位基準', '未評估，未取得資金與持倉輸入'], ['比例意義', '0% 僅指本研究不新增部位，不代表使用者實際持倉為零。']] : mode === 'event-swing' ? [['交易方向', 'Neutral'], ['進場區間', 'N/A'], ['1-2 週目標', '資料不足'], ['嚴格停損', 'N/A'], ['事件催化', '事件日期未確認'], ['重新評估條件', '等待站回10日均線且法人轉買超'], ['波動風險', 'High']] : mode === 'contrarian' ? [['空方結論', '避免'], ['做空觸發', '不建立空方部位'], ['下行目標', 'N/A'], ['防軋空停損', 'N/A']] : [['最終建議', '持有'], ['基本情境估值', 'NT$100.00'], ['整體護城河', '資料不足']];
    const focusRows = mode === 'contrarian' ? `<div class="mode-focus-risk-grid">${rows.map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join('')}</div>` : `<dl>${rows.map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join('')}</dl>`;
    return `<!doctype html><html><head><style>${style}</style></head><body>
    <nav class="sidebar"><div class="sidebar-rec">持有</div><div class="nav-section"></div></nav>
    <main class="main" data-report-layout="${mode}"><div class="hero"><div class="hero-badge">模式</div><div class="hero-title">測試公司</div><div class="hero-subtitle">分析日期：2026年10月17日</div>
    <div class="verdict-banner"><div class="verdict-label">研究評級</div><div class="verdict-main">持有</div><div class="verdict-sub"></div></div>
    <section class="report-reading-notice report-reading-notice-${state}"><h2>報告使用範圍與判讀限制</h2><span class="report-reading-notice-status">品質 gate ${state === 'blocked' ? '未通過' : '有警示'}</span><ul class="report-reading-notice-checks"><li><span>輸出契約</span><strong>有警示</strong></li></ul><p>資料已更新，分析未重新執行，不能作為最新結論。</p></section>
    <section class="report-reading-notice"><h2>保存分析驗證重播</h2><span class="report-reading-notice-status">品質 gate 有警示</span><p>未產生新模型預測。</p></section>
    <p class="report-reading-notice-note">Agent 23 驗證發布，不是新的預測。</p>
    <div class="execution-summary-card">Pipeline V1 Agent 22 <div class="execution-summary-note">數字未能核實，不可採用目標價。</div>Evidence gate：caution</div>
    <section class="trade-setup-dashboard"><p class="trade-catalyst">short_term_market_context.event_calendar 與 data_trust 狀態：stale</p>${mode === 'event-swing' ? '<dl><div><dt>交易方向</dt><dd>Neutral</dd></div><div><dt>進場區間</dt><dd>N/A</dd></div></dl>' : ''}</section>
    <section class="mode-focus">${focusRows}</section></div>
    <div class="content"><div class="section" id="section-22"><div class="section-title">技術動能分析師</div><div class="analysis-card"><p>股價為 100.00，不能認定已突破。（來源：short_term_market_context.technical_indicators.sma_10；資料截至 2026-10-16）</p><p>依據 deterministic_financial_tool_results.scenarios。TTM 資料未取得。現金流 -2.84 billion_twd。其他指標 N/A。市場情緒中性，非交易方向。</p><table><tr><th>交易方向</th><td>${mode === 'event-swing' ? 'Neutral' : '中性'}</td></tr><tr><th>進場區間</th><td>N/A</td></tr></table>${mode === 'event-swing' ? '<ul><li><strong>交易方向：Neutral</strong></li><li><strong>進場區間：N/A</strong></li><li><strong>1-2週目標價：N/A</strong></li><li><strong>🛑 停損點：N/A</strong></li></ul><p><strong>交易方向</strong>：Neutral</p>' : ''}</div></div></div>
    <div class="references"><table class="source-audit-table"><tbody>
    <tr><td>新聞來源</td><td>provider</td><td><span class="audit-status audit-status-error">失敗</span></td><td></td><td>10</td><td>0</td><td>否</td><td>否</td><td>HTTP 429，請求暫受限制</td></tr>
    <tr><td>公告來源</td><td>provider</td><td><span class="audit-status audit-status-unavailable">無資料</span></td><td></td><td>10</td><td>0</td><td>否</td><td>否</td><td>查詢期間無公告，不推論沒有風險</td></tr>
    </tbody></table></div>
    </main><script id="report-reader-observations" type="application/json">${JSON.stringify(observations).replaceAll('<', '\\u003c')}</script><script id="report-chart-data" type="application/json">{"prices":[100.00,null,98]}</script><script>${script}</script></body></html>`;
}

function changedFixture(mode, from, to) {
    const html = fixture(mode);
    const start = html.indexOf('<script id="report-chart-data"');
    return html.slice(0, start).replaceAll(from, to) + html.slice(start);
}

async function main() {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext();
    const requests = [];
    await context.route('**/*', route => {
        const url = route.request().url();
        if (chartFile && url === 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js') {
            return route.fulfill({ path: chartFile, contentType: 'application/javascript' });
        }
        requests.push(url);
        return route.abort();
    });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    const results = [];
    try {
        for (const mode of ['research', 'trading', 'contrarian', 'event-swing']) {
            for (const state of ['warning', 'blocked']) {
                await page.goto('about:blank');
                await page.setContent(fixture(mode, state));
                const visible = await page.locator('body').innerText();
                assert.equal(await page.locator('body').getAttribute('data-reader-version'), '1');
                assert(await page.locator('.reader-facts > div').count() > 0);
                assert(!visible.includes('Pipeline'));
                assert(!visible.includes('short_term_market_context'), JSON.stringify({ visible, errors }));
                assert(!visible.includes('品質 gate'));
                assert(!visible.includes('Agent 23'));
                assert(!visible.includes('data_trust'));
                assert(!visible.includes('_results'));
                assert(visible.includes('財務計算結果'));
                assert(visible.includes('未產生新模型預測'));
                assert(visible.includes('資料已過期'));
                assert(visible.includes('不能認定已突破'));
                assert(visible.includes('分析未重新執行'));
                assert(visible.includes('不可採用目標價'));
                assert(visible.includes('尚未提供（原報告未填此項，未記錄缺漏原因）'));
                assert(visible.includes('來源異常'));
                assert(visible.includes('HTTP 429'));
                assert(visible.includes('尚未確認'));
                assert(visible.includes('查詢期間無公告，不推論沒有風險'));
                assert(!visible.includes('未提供（原因未註明）'));
                assert(visible.includes('市場情緒中性，非交易方向'));
                assert(visible.includes('-28.4 億元新臺幣'));
                assert.equal(await page.locator('#report-chart-data').textContent(), '{"prices":[100.00,null,98]}');
                assert((await page.locator('.analysis-card > .reader-original').textContent()).includes('short_term_market_context.technical_indicators.sma_10'));
                if (mode === 'trading') {
                    assert.equal(await page.locator('.hero > .verdict-banner .verdict-main').innerText(), '等待');
                    assert(visible.includes('不代表使用者實際持倉為零'));
                    assert(visible.includes('尚未提供（原報告未取得資金與持倉輸入'));
                    assert(visible.includes('不適用（本次等待'));
                }
                if (mode === 'research') assert(visible.includes('尚未確認（原報告未提供可核實的護城河評分'));
                if (mode === 'contrarian') assert(visible.includes('不適用（原計畫明示不建立空方部位'));
                if (mode === 'event-swing') {
                    assert(visible.includes('尚未確認（原保存資料未包含可判讀的事件日曆'));
                    assert(!visible.includes('Neutral'));
                    assert(!visible.includes('High'));
                    assert.equal(await page.locator('.hero > .verdict-banner .verdict-main').innerText(), '觀望（暫不建立新交易）');
                    assert(visible.includes('不適用（觀望中，暫不設定交易價位）'));
                    assert(visible.includes('等待站回10日均線且法人轉買超'));
                    assert(visible.includes('不等於「持有」'));
                    const analysis = await page.locator('.reader-analysis').innerText();
                    assert(analysis.includes('交易方向：觀望（暫不建立新交易）'));
                    assert(analysis.includes('1-2週目標價：不適用（觀望中，暫不設定交易價位）'));
                    assert(!analysis.includes('交易方向：中性'));
                }
                const firstLink = page.locator('.reader-analysis .reader-reference').first();
                await firstLink.click();
                assert.equal(await page.locator('#reader-audit').getAttribute('open'), '');
                await page.evaluate(script);
                assert.equal(await page.locator('#reader-brief').count(), 1);
                results.push({ mode, state, status: 'passed' });
            }
        }
        const variants = [
            ['long-missing-entry', changedFixture('event-swing', 'Neutral', 'Long'), '進場區間', '尚未提供', '不適用'],
            ['unknown-direction', changedFixture('event-swing', 'Neutral', 'N/A'), '進場區間', '尚未提供', '不適用'],
            ['no-assumed-short', changedFixture('contrarian', '不建立空方部位', '等待財報確認'), '下行目標', '尚未確認', '不適用'],
            ['conditional-is-not-no-short', changedFixture('contrarian', '不建立空方部位', '若未跌破支撐則不做空'), '下行目標', '尚未確認', '不適用'],
            ['preserve-existing-missing-reason', changedFixture('contrarian', '<span>下行目標</span><strong>N/A</strong>', '<span>下行目標</span><strong>資料不足，需重新產生可驗證下行目標</strong>'), '下行目標', '尚未確認，需重新產生可驗證下行目標', '不適用'],
            ['research-neutral', changedFixture('research', '持有', '中性'), '最終建議', '觀望（研究尚未形成明確買賣傾向）', '暫不建立新交易'],
        ];
        for (const [name, html, label, expected, excluded] of variants) {
            await page.goto('about:blank');
            await page.setContent(html);
            const observed = await page.locator('.reader-facts > div').evaluateAll((rows, label) => rows.find(row => row.querySelector('dt').textContent === label)?.querySelector('dd').textContent, label);
            assert(observed?.includes(expected), `${name}: ${observed}`);
            assert(!observed.includes(excluded), `${name}: ${observed}`);
            results.push({ case: name, status: 'passed' });
        }
        await page.goto('about:blank');
        await page.setContent(fixture('research').replace('audit-status-error', 'audit-status-skipped_fresh_cache').replace('HTTP 429，請求暫受限制', '有效快取已提供資料').replace('audit-status-unavailable', 'audit-status-not_configured'));
        const limits = await page.locator('.reader-limits').innerText();
        assert(!limits.includes('來源異常'));
        assert(!limits.includes('有效快取已提供資料'));
        assert(limits.includes('尚未提供｜公告來源'));
        results.push({ case: 'cache-and-configuration-are-not-provider-errors', status: 'passed' });
        for (const [kind, message, expected] of [
            ['cooldown', '來源仍在冷卻期間', '本次沒有重新取得資料'],
            ['single_flight_busy', '來源未回傳名單', '已有其他取得工作進行中'],
            ['FilingError', 'fewer than five contiguous published consolidated annual filings', '不能用較少年度冒充完整五年'],
            ['FilingError', 'conflicting incomplete financial-institution comparative for 2022', '官方比較期間不完整或資料互有衝突'],
            ['timeout', '發行人原文核對未完成', '實際取得逾時'],
        ]) {
            const data = { source_audit: [{ label: '新聞來源', provider: 'provider', status: 'error', fetched_at: '', error_kind: kind }] };
            await page.goto('about:blank');
            await page.setContent(fixture('research', 'warning', data).replace('HTTP 429，請求暫受限制', message));
            const visible = await page.locator('.reader-limits').innerText();
            assert(visible.includes(expected), `${kind}: ${visible}`);
            if (kind !== 'timeout') assert(!visible.includes('來源異常｜新聞來源'));
            assert((await page.locator('#reader-audit').textContent()).includes(message));
            results.push({ case: `source-reason-${kind}-${message.slice(0, 12)}`, status: 'passed' });
        }
        for (const [day, expected] of [['2026-11-11', '不在原報告的 14 日範圍內'], ['2026-10-20', '原分析尚未確認其影響與交易條件']]) {
            const data = { event_calendar: { as_of_date: '2026-10-17', status: 'success', calendar_fetch_status: 'success', coverage_complete: false, events: [{ type: 'earnings_date', date: day }] } };
            await page.goto('about:blank');
            await page.setContent(fixture('event-swing', 'warning', data));
            const visible = await page.locator('.reader-brief').innerText();
            assert(visible.includes(day) && visible.includes(expected));
            assert(visible.includes('來源未保證完整覆蓋'));
            assert(visible.includes('觀望（暫不建立新交易）'));
            results.push({ case: `calendar-reason-${day}`, status: 'passed' });
        }
        const recovery = { source_audit: [{ label: '新聞來源', provider: 'provider', status: 'success', fetched_at: '2026-10-18T00:00:00Z', record_count: 1, stale: false }], analysis_not_rerun: true };
        await page.goto('about:blank');
        await page.setContent(fixture('research', 'warning', recovery).replace('audit-status-error">失敗</span></td><td></td>', 'audit-status-error">失敗</span></td><td>2026-10-17T00:00:00Z</td>'));
        const recoveryText = await page.locator('.reader-limits').innerText();
        assert(recoveryText.includes('來源異常（原報告紀錄）'));
        assert(recoveryText.includes('較新的來源取得紀錄'));
        assert(recoveryText.includes('更新資料不代表原分析已重跑'));
        results.push({ case: 'new-source-receipt-does-not-erase-original-warning', status: 'passed' });
        const replacement = { source_audit: [{ source: 'earnings_call', label: '法說會', provider: 'New official source', status: 'success', fetched_at: '2026-10-18T00:00:00Z', record_count: 1, stale: false }], analysis_not_rerun: true, refreshed_at: '2026-10-18T00:00:10Z' };
        await page.goto('about:blank');
        await page.setContent(fixture('research', 'warning', replacement));
        const replacementText = await page.locator('.reader-limits').innerText();
        assert(replacementText.includes('資料補抓紀錄｜法說會'));
        assert(replacementText.includes('不能把原報告視為最新結論'));
        results.push({ case: 'replacement-source-does-not-rewrite-the-old-analysis', status: 'passed' });
        await page.goto('about:blank');
        await page.setContent(changedFixture('research', '其他指標 N/A', '護城河待補推論步驟；其他指標 N/A'));
        assert((await page.locator('.reader-brief').innerText()).includes('須重新分析；不能靠補股價直接填分'));
        results.push({ case: 'incomplete-moat-is-not-a-missing-quote', status: 'passed' });
        await page.goto('about:blank');
        await page.setContent(fixture('event-swing', 'warning', { evidence_gaps: {
            cash_flow: { status: 'annual_originals_verified', period_start: '2025-01-01', period_end: '2025-12-31', operating_cash_flow_twd: 1000, ppe_purchase_twd: -200, intangible_purchase_twd: -50, free_cash_flow_twd: 750, raw_scalar: -900, raw_scalar_currency: 'TWD' },
            volume: { official_original_verified: true, date: '2026-10-16', provider_label: 'Yahoo', provider_volume: 1000, official_volume: 1200, provider_unit: 'shares', official_unit: 'shares', delta_shares: -200 },
            institutional: { expected_values: 90, matched_values: 15, missing_dates: ['2026-10-01'], issues: [] },
        } }));
        const gapText = await page.locator('.reader-limits').innerText();
        assert(gapText.includes('年度自由現金流 750 元'));
        assert(gapText.includes('原即期數值 -900 新臺幣元仍保留'));
        assert(gapText.includes('差額（Yahoo 減官方）為 -200 股'));
        assert(gapText.includes('不能把差額直接認定為零股或盤後交易'));
        assert(gapText.includes('15／90 個值與官方原件一致'));
        assert(gapText.includes('不證明原報告當時已可取得'));
        results.push({ case: 'recovered-evidence-keeps-scalar-scope-and-pit-warnings', status: 'passed' });
        if (preview) {
            fs.mkdirSync(output, { recursive: true });
            for (const mode of ['v1', 'v2', 'v3', 'v4']) {
                const html = fs.readFileSync(path.join(preview, `${mode}.html`), 'utf8');
                for (const [name, width, height] of [['desktop', 1440, 1000], ['mobile', 390, 844]]) {
                    await page.setViewportSize({ width, height });
                    await page.emulateMedia({ media: 'screen' });
                    await page.goto('about:blank');
                    const headersPath = path.join(preview, `${mode}.headers.json`);
                    const headers = JSON.parse(fs.readFileSync(headersPath, 'utf8'));
                    delete headers['content-length'];
                    const injected = '<script>window.untrustedReaderProbe=true</script><img src="blocked-image" onerror="window.untrustedReaderProbe=true">';
                    await page.route('https://reader.test/view', route => route.fulfill({ status: 200, headers, body: html.replace('</body>', injected + '</body>') }));
                    await page.goto('https://reader.test/view', { waitUntil: 'load' });
                    await page.unroute('https://reader.test/view');
                    await page.waitForFunction(() => document.body.dataset.readerVersion === '1');
                    assert.equal(await page.evaluate(() => window.untrustedReaderProbe), undefined);
                    await page.waitForTimeout(1000);
                    const observation = await page.evaluate(() => {
                        const visible = document.body.innerText;
                        const overflow = [...document.querySelectorAll('main *, nav *')].filter(node => {
                            const rect = node.getBoundingClientRect();
                            return rect.width && rect.height && (rect.left < -1 || rect.right > innerWidth + 1) && !node.closest('.source-audit-scroll,.table-wrapper,details:not([open])');
                        }).slice(0, 12).map(node => ({ tag: node.tagName, class: node.className, text: node.textContent.slice(0, 80) }));
                        const charts = [...document.querySelectorAll('canvas')].map(canvas => {
                            const ctx = canvas.getContext('2d');
                            const data = canvas.width && canvas.height ? ctx.getImageData(0, 0, canvas.width, canvas.height).data : [];
                            let painted = 0;
                            for (let i = 3; i < data.length; i += 4) if (data[i]) painted++;
                            return { id: canvas.id, width: canvas.width, height: canvas.height, painted, chart: !!window.Chart?.getChart(canvas), empty: canvas.parentElement.innerText.trim() };
                        });
                        return { scrollWidth: document.documentElement.scrollWidth, width: innerWidth, overflow, charts,
                            jargon: visible.match(/Pipeline|Agent\s+\d+|品質 gate|\b(?:short_term_market_context|peer_context|data_trust|free_cash_flow_raw_non_positive|no_executable_direction)\b/g) || [],
                            warnings: document.querySelector('.report-reading-notice')?.innerText,
                            direction: document.querySelector('.verdict-main')?.innerText,
                            shortPlan: document.querySelector('#section-24 .reader-analysis')?.innerText,
                            brief: document.querySelector('.reader-brief')?.innerText };
                    });
                    assert(observation.scrollWidth <= width + 1, `${mode}/${name}: horizontal overflow`);
                    assert.equal(observation.jargon.length, 0, `${mode}/${name}: engineering terms visible`);
                    assert(await page.locator('.reader-facts > div').count() > 0, `${mode}/${name}: missing decision fields`);
                    if (mode === 'v4') assert(!/交易方向[：:]\s*(?:中性|Neutral)/i.test(observation.shortPlan || ''), `${mode}/${name}: ambiguous direction in original-format analysis`);
                    await page.screenshot({ path: path.join(output, `${mode}-${name}.png`) });
                    await page.locator('.report-agent-sections .section, .content .section').first().scrollIntoViewIfNeeded();
                    await page.screenshot({ path: path.join(output, `${mode}-${name}-analysis.png`) });
                    if (mode === 'v4' && await page.locator('#section-24').count()) {
                        await page.locator('#section-24').scrollIntoViewIfNeeded();
                        await page.screenshot({ path: path.join(output, `${mode}-${name}-decision.png`) });
                    }
                    results.push({ mode, viewport: name, ...observation });
                }
                await page.emulateMedia({ media: 'print' });
                assert(await page.locator('.hero > .report-reading-notice').isVisible());
                assert(await page.locator('.reader-limits').isVisible());
                assert(!(await page.locator('#reader-audit').isVisible()));
                await page.pdf({ path: path.join(output, `${mode}-print.pdf`), format: 'A4', printBackground: true });
            }
        }
        assert.equal(errors.length, 0, errors.join('\n'));
        const result = { results, errors, deniedRequests: [...new Set(requests)] };
        if (output) fs.writeFileSync(path.join(output, 'browser-results.json'), JSON.stringify(result, null, 2));
        console.log(JSON.stringify({ checks: results.length, errors, resultsPath: output && path.join(output, 'browser-results.json') }));
    } finally {
        await browser.close();
    }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
