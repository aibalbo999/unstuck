(function () {
    const loadMethods = {
        async loadFromInput() {
            const ticker = this.normalizeTickerInput(this.elements.tickerInput?.value);
            if (!ticker) {
                this.notify.error('請輸入股票代號。');
                return;
            }
            this.setTickerInput(ticker);
            await this.load(ticker);
        },

        async load(ticker) {
            if (!this.apiClient || typeof this.apiClient.fetchStockSnapshot !== 'function') return;
            const normalizedTicker = this.normalizeTickerInput(ticker);
            if (!normalizedTicker) return;
            this.currentTicker = normalizedTicker;
            this.setTickerInput(normalizedTicker);
            this.setLoading(true);
            try {
                const snapshot = await this.apiClient.fetchStockSnapshot(normalizedTicker);
                this.rememberTicker(snapshot?.ticker || normalizedTicker);
                this.renderShortcuts();
                this.render(snapshot);
            } catch (err) {
                this.renderError(err);
            } finally {
                this.setLoading(false);
            }
        },

        setLoading(value) {
            const button = this.elements.loadButton;
            if (!button) return;
            button.disabled = Boolean(value);
            const label = button.querySelector('span');
            if (label) label.textContent = value ? '載入中' : '股票快照';
        },
    };

    window.StockAgentStockSnapshotLoadHelpers = { loadMethods };
})();
