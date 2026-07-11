(function () {
    const eventMethods = {
        bindEvents() {
            const button = this.elements.loadButton;
            if (button) button.addEventListener('click', () => this.loadFromInput());
            this.elements.tickerInput?.addEventListener('keydown', event => {
                if (event.key !== 'Enter' || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return undefined;
                event.preventDefault?.();
                event.stopPropagation?.();
                event.stopImmediatePropagation?.();
                return this.loadFromInput();
            });
            this.elements.shortcutsRoot?.addEventListener('click', event => {
                const shortcutButton = event.target.closest('[data-stock-snapshot-shortcut]');
                if (!shortcutButton) return;
                const ticker = this.normalizeTickerInput(shortcutButton.dataset.stockSnapshotShortcut);
                if (!ticker) return;
                this.setTickerInput(ticker);
                this.load(ticker);
            });
            this.renderShortcuts();
            this.elements.root?.addEventListener('click', event => {
                const watchlistButton = event.target.closest('[data-stock-snapshot-watchlist]');
                if (watchlistButton) return this.addToWatchlist(watchlistButton.dataset.stockSnapshotWatchlist);
                const alertButton = event.target.closest('[data-stock-snapshot-alert]');
                if (alertButton) return this.applyAlertSuggestion(Number(alertButton.dataset.stockSnapshotAlert));
                const rangeButton = event.target.closest('[data-stock-snapshot-range]');
                if (rangeButton) return this.selectPerformanceRange(rangeButton.dataset.stockSnapshotRange);
                const button = event.target.closest('[data-stock-snapshot-pipeline]');
                if (!button) return undefined;
                return this.onSelectPipeline(button.dataset.stockSnapshotPipeline);
            });
        },
    };

    window.StockAgentStockSnapshotEventHelpers = { eventMethods };
})();
