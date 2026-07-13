(function () {
    const RECENT_TICKERS_KEY = 'stockAgent.stockSnapshot.recentTickers';

    const inputMethods = {
        renderShortcuts() {
            const root = this.elements.shortcutsRoot;
            if (!root) return;
            const recent = this.getRecentTickers();
            const common = this.defaultShortcuts
                .map(ticker => this.normalizeTickerInput(ticker))
                .filter(Boolean)
                .filter((ticker, index, list) => list.indexOf(ticker) === index && !recent.includes(ticker))
                .slice(0, 5);
            root.innerHTML = `<div class="stock-snapshot-shortcuts-row">${this.shortcutGroup('最近', recent)}${this.shortcutGroup('常用', common)}</div>`;
        },

        shortcutGroup(label, tickers) {
            const e = this.escapeHtml;
            if (!Array.isArray(tickers) || !tickers.length) return '';
            return `<div class="stock-snapshot-shortcuts-group"><span>${e(label)}</span>${tickers.map(ticker => `<button type="button" data-stock-snapshot-shortcut="${e(ticker)}">${e(ticker)}</button>`).join('')}</div>`;
        },

        getRecentTickers() {
            try {
                const storage = window.localStorage;
                if (!storage) return [];
                const parsed = JSON.parse(storage.getItem(RECENT_TICKERS_KEY) || '[]');
                if (!Array.isArray(parsed)) return [];
                return parsed
                    .map(ticker => this.normalizeTickerInput(ticker))
                    .filter(Boolean)
                    .filter((ticker, index, list) => list.indexOf(ticker) === index)
                    .slice(0, 5);
            } catch (_) {
                return [];
            }
        },

        rememberTicker(ticker) {
            const normalized = this.normalizeTickerInput(ticker);
            if (!normalized) return;
            try {
                const storage = window.localStorage;
                if (!storage) return;
                const tickers = [normalized, ...this.getRecentTickers().filter(item => item !== normalized)].slice(0, 5);
                storage.setItem(RECENT_TICKERS_KEY, JSON.stringify(tickers));
            } catch (_) {
                // Browser privacy settings can block localStorage; shortcuts still work without recents.
            }
        },

        normalizeTickerInput(value) {
            const ticker = String(value || '').trim().toUpperCase();
            if (!ticker) return '';
            if (/^\d{4}$/.test(ticker)) return `${ticker}.TW`;
            return ticker.replace(/\s+/g, '');
        },

        setTickerInput(ticker) {
            if (this.elements.tickerInput) this.elements.tickerInput.value = ticker;
        },
    };

    window.StockAgentStockSnapshotInputHelpers = { inputMethods };
})();
