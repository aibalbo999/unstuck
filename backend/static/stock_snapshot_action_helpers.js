(function () {
    const actionMethods = {
        async addToWatchlist(ticker) {
            const normalizedTicker = String(ticker || this.currentTicker || '').trim().toUpperCase();
            if (!normalizedTicker || !this.apiClient || typeof this.apiClient.saveWatchlistItem !== 'function') {
                this.notify.error('追蹤清單目前無法使用。');
                return;
            }
            this.setWatchlistLoading(true);
            try {
                const pipeline = this.resolveWatchlistPipeline();
                await this.apiClient.saveWatchlistItem({
                    ticker: normalizedTicker,
                    pipeline,
                    enabled: true,
                    schedule_slots: ['pre_market'],
                    triggers: []
                });
                this.notify.success?.(`${normalizedTicker} 已加入追蹤清單。`);
                await this.onWatchlistUpdated();
            } catch (err) {
                this.notify.error(`加入追蹤失敗：${err.message || err}`);
            } finally {
                this.setWatchlistLoading(false);
            }
        },

        async applyAlertSuggestion(index) {
            const suggestion = this.lastSnapshot?.alert_suggestions?.suggestions?.[index];
            const ticker = String(this.lastSnapshot?.ticker || this.currentTicker || '').trim().toUpperCase();
            const triggers = Array.isArray(suggestion?.triggers) ? suggestion.triggers : [];
            if (!ticker || !suggestion || !triggers.length || !this.apiClient || typeof this.apiClient.saveWatchlistItem !== 'function') {
                this.notify.error('提醒建議目前無法套用。');
                return;
            }
            this.setAlertLoading(true);
            try {
                await this.apiClient.saveWatchlistItem({
                    ticker,
                    pipeline: suggestion.pipeline || this.resolveWatchlistPipeline(),
                    enabled: true,
                    schedule_slots: Array.isArray(suggestion.schedule_slots) && suggestion.schedule_slots.length ? suggestion.schedule_slots : ['pre_market'],
                    triggers,
                    trigger_source: 'stock_snapshot_suggestion'
                });
                this.notify.success?.(`${ticker} 已套用「${suggestion.label || '提醒'}」。`);
                await this.onWatchlistUpdated();
            } catch (err) {
                this.notify.error(`套用提醒失敗：${err.message || err}`);
            } finally {
                this.setAlertLoading(false);
            }
        },

        resolveWatchlistPipeline() {
            const selected = String(this.getSelectedPipeline() || '').trim();
            if (selected) return selected;
            const suggestions = Array.isArray(this.lastSnapshot?.mode_suggestions) ? this.lastSnapshot.mode_suggestions : [];
            return suggestions[0]?.pipeline_id || 'v1';
        },

        setWatchlistLoading(value) {
            const root = this.elements.root;
            if (!root) return;
            root.querySelectorAll('[data-stock-snapshot-watchlist]').forEach(button => {
                button.disabled = Boolean(value);
                const label = button.querySelector('span');
                if (label) label.textContent = value ? '加入中' : '加入追蹤';
            });
        },

        setAlertLoading(value) {
            const root = this.elements.root;
            if (!root) return;
            root.querySelectorAll?.('[data-stock-snapshot-alert]').forEach(button => {
                button.disabled = Boolean(value);
            });
        },
    };

    window.StockAgentStockSnapshotActionHelpers = { actionMethods };
})();
