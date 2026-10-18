/* Read-only browser replay of every indexed HTML, with the real fixed-script CSP. */
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_NODE_MODULE || 'playwright');
const args = process.argv.slice(2);
const value = name => args[args.indexOf(name) + 1];
const manifest = JSON.parse(fs.readFileSync(value('--manifest'), 'utf8'));
const headers = JSON.parse(fs.readFileSync(value('--headers'), 'utf8'));
delete headers['content-length'];
const output = value('--result');
const root = path.resolve(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'backend/templates/includes/report_reader_script.html.j2'), 'utf8').replace(/\r?\n$/, '');
const style = fs.readFileSync(path.join(root, 'backend/templates/includes/report_reader_styles.html.j2'), 'utf8');
const layouts = { v1: 'research', v2: 'trading', v3: 'contrarian', v4: 'event-swing' };
const selected = args.includes('--failed') ? new Set(JSON.parse(fs.readFileSync(value('--failed'), 'utf8')).failures.map(item => item.filename)) : null;

async function main() {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const results = [];
    const failures = [];
    let current = '';
    await context.route('**/*', route => {
        if (route.request().url() === 'https://reader.test/inventory') return route.fulfill({ status: 200, headers, body: current });
        if (route.request().url() === 'https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js') return route.fulfill({ path: value('--chart-js'), contentType: 'application/javascript' });
        return route.abort();
    });
    const page = await context.newPage();
    let errors = [];
    page.on('pageerror', error => errors.push(error.message));
    try {
        for (const item of manifest.reports) {
            if (selected && !selected.has(item.filename)) continue;
            const original = fs.readFileSync(path.join(manifest.output, item.key), 'utf8');
            const observations = original.match(/<script id="report-reader-observations" type="application\/json">[\s\S]*?<\/script>/)?.[0] || '';
            const base = original.replace(/<!-- onstock-reader:start:v1 -->[\s\S]*?<!-- onstock-reader:end:v1 -->/, '');
            current = base.replace(/<\/body>\s*<\/html>\s*$/i, () => `${observations}<style>${style}</style><script id="report-reader-script">${script}</script></body></html>`);
            errors = [];
            try {
                await page.goto('https://reader.test/inventory', { waitUntil: 'load', timeout: 10000 });
                await page.waitForFunction(() => document.body.dataset.readerVersion === '1', null, { timeout: 3000 });
                const observed = await page.evaluate(() => ({
                    layout: document.querySelector('main').dataset.reportLayout,
                    fields: document.querySelectorAll('.reader-facts > div').length,
                    overflow: document.documentElement.scrollWidth > innerWidth + 1,
                    visibleJargon: document.body.innerText.match(/Pipeline|Agent\s+\d+|品質 gate|_results|\b(?:short_term_market_context|peer_context|data_trust|free_cash_flow_raw_non_positive|no_executable_direction)\b/g) || [],
                    canvasCount: document.querySelectorAll('canvas').length,
                    auditAvailable: !!document.querySelector('#reader-audit'),
                    originalSections: document.querySelectorAll('.analysis-card > .reader-original').length,
                    visibleSections: document.querySelectorAll('.analysis-card > .reader-analysis').length,
                    factValues: [...document.querySelectorAll('.reader-facts > div')].map(row => ({ label: row.querySelector('dt').textContent, value: row.querySelector('dd').textContent })),
                    direction: document.querySelector('.verdict-main')?.textContent.trim(),
                    ambiguousBodyDirection: /交易方向[：:]\s*(?:中性|Neutral)/i.test(document.body.innerText),
                    details: [...document.querySelectorAll('main *')].filter(node => {
                        if (node.children.length || node.closest('details:not([open])')) return false;
                        const r = node.getBoundingClientRect();
                        return r.width && r.height && (r.right > innerWidth + 1 || /Pipeline|Agent\s+\d+|品質 gate|data_trust|short_term_market_context/.test(node.innerText));
                    }).slice(0, 12).map(node => ({tag: node.tagName, class: node.className, text: node.innerText.slice(0, 300), parent: node.parentElement.className})),
                }));
                const expectedCanvas = (base.match(/<canvas\b/g) || []).length;
                const unclassified = observed.factValues.filter(row => /^資料不足|^(?:N\/?A|未提供|未評估|未驗證|未估計|未確認|事件日期未確認|--)(?:\/10)?$/i.test(row.value.trim()));
                const ambiguousDirection = item.pipeline_id === 'v4' && (/^(?:Neutral|中性(?:\s+Neutral)?)$/i.test(observed.direction || '') || observed.ambiguousBodyDirection);
                const ok = observed.layout === layouts[item.pipeline_id] && observed.fields > 0 && !observed.overflow && !observed.visibleJargon.length && observed.canvasCount === expectedCanvas && observed.auditAvailable && observed.originalSections === observed.visibleSections && !unclassified.length && !ambiguousDirection && errors.length === 0;
                const result = { filename: item.filename, pipeline_id: item.pipeline_id, ...observed, unclassified, ambiguousDirection, errors: [...errors], passed: ok };
                results.push(result);
                if (!ok) failures.push(result);
            } catch (error) {
                const result = { filename: item.filename, passed: false, error: String(error), errors: [...errors] };
                results.push(result);
                failures.push(result);
            }
            if (results.length % 100 === 0) console.log(JSON.stringify({ checked: results.length, failed: failures.length }));
        }
        const result = { total: results.length, passed: results.length - failures.length, failures, reports: results };
        fs.writeFileSync(output, JSON.stringify(result, null, 2));
        console.log(JSON.stringify({ total: result.total, passed: result.passed, failures: failures.length, output }));
        process.exitCode = failures.length ? 1 : 0;
    } finally { await browser.close(); }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
