(function () {
    const DEFAULT_SHORTCUT_TICKERS = ['2330.TW', '2317.TW', '2454.TW', 'AAPL', 'NVDA'];
    const helpers = window.StockAgentStockSnapshotHelpers;
    const inputHelpers = window.StockAgentStockSnapshotInputHelpers;
    const loadHelpers = window.StockAgentStockSnapshotLoadHelpers;
    const actionHelpers = window.StockAgentStockSnapshotActionHelpers;
    const summaryHelpers = window.StockAgentStockSnapshotSummaryHelpers;
    const sections = window.StockAgentStockSnapshotSections;
    const overviewSections = window.StockAgentStockSnapshotOverviewSections;
    const researchSections = window.StockAgentStockSnapshotResearchSections;
    const signalSections = window.StockAgentStockSnapshotSignalSections;
    const supplementalSections = window.StockAgentStockSnapshotSupplementalSections;
    const interactionHelpers = window.StockAgentStockSnapshotInteractionHelpers;
    const renderHelpers = window.StockAgentStockSnapshotRenderHelpers;
    const eventHelpers = window.StockAgentStockSnapshotEventHelpers;

    function create(options) {
        return new StockSnapshotPanel(options || {});
    }

    class StockSnapshotPanel {
        constructor(options) {
            this.apiClient = options.apiClient;
            this.ui = options.ui || {};
            this.notify = options.notify || { error: () => {} };
            this.elements = options.elements || {};
            this.onSelectPipeline = options.onSelectPipeline || (() => {});
            this.onWatchlistUpdated = options.onWatchlistUpdated || (() => {});
            this.getSelectedPipeline = options.getSelectedPipeline || (() => '');
            this.escapeHtml = this.ui.escapeHtml || (value => String(value ?? ''));
            this.currentTicker = '';
            this.lastSnapshot = null;
            this.defaultShortcuts = Array.isArray(options.defaultShortcuts) && options.defaultShortcuts.length
                ? options.defaultShortcuts
                : DEFAULT_SHORTCUT_TICKERS;
        }

    }

    Object.assign(StockSnapshotPanel.prototype, helpers?.panelMethods || {});
    Object.assign(StockSnapshotPanel.prototype, helpers?.fragmentMethods || {});
    Object.assign(StockSnapshotPanel.prototype, inputHelpers?.inputMethods || {});
    Object.assign(StockSnapshotPanel.prototype, loadHelpers?.loadMethods || {});
    Object.assign(StockSnapshotPanel.prototype, actionHelpers?.actionMethods || {});
    Object.assign(StockSnapshotPanel.prototype, summaryHelpers?.summaryMethods || {});
    Object.assign(StockSnapshotPanel.prototype, sections?.sectionMethods || {});
    Object.assign(StockSnapshotPanel.prototype, overviewSections?.overviewSectionMethods || {});
    Object.assign(StockSnapshotPanel.prototype, researchSections?.researchSectionMethods || {});
    Object.assign(StockSnapshotPanel.prototype, signalSections?.signalSectionMethods || {});
    Object.assign(StockSnapshotPanel.prototype, supplementalSections?.supplementalSectionMethods || {});
    Object.assign(StockSnapshotPanel.prototype, interactionHelpers?.interactionMethods || {});
    Object.assign(StockSnapshotPanel.prototype, renderHelpers?.renderMethods || {});
    Object.assign(StockSnapshotPanel.prototype, eventHelpers?.eventMethods || {});

    window.StockAgentStockSnapshotPanel = { create, StockSnapshotPanel };
})();
