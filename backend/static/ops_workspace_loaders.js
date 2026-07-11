(function () {
    function fail(summaryEl, listEl, message) {
        if (summaryEl) summaryEl.textContent = message;
        if (listEl) listEl.innerHTML = '<span class="provider-sla-chip is-warning">請稍後重試</span>';
    }

    async function loadPanel({ summaryEl, listEl, refreshEl, fetchPayload, renderPayload, failureMessage, errorLabel }) {
        if (!summaryEl || !listEl) return;
        try {
            if (refreshEl) refreshEl.disabled = true;
            renderPayload(await fetchPayload());
        } catch (err) {
            console.error(`Failed to load ${errorLabel}`, err);
            fail(summaryEl, listEl, failureMessage);
        } finally {
            if (refreshEl) refreshEl.disabled = false;
        }
    }

    window.StockAgentOpsWorkspaceLoaders = { loadPanel };
})();
