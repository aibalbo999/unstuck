(function () {
    function buttonForScope(scope, buttons) {
        if (scope === 'mode_b') return buttons.modeB;
        if (scope === 'full_report') return buttons.full;
        return buttons.final;
    }

    function setButtonLabel(button, text) {
        const label = button ? button.querySelector('span') : null;
        if (label) label.textContent = text;
    }

    function disableButtons(buttons, disabled) {
        [buttons.final, buttons.full, buttons.modeB].forEach(button => {
            if (!button) return;
            button.disabled = disabled;
        });
    }

    function configureCancelButton(button, visible, handler) {
        if (!button) return;
        button.hidden = !visible;
        button.disabled = false;
        button.onclick = handler || null;
    }

    function setStatus(statusEl, message) {
        if (!statusEl) return;
        statusEl.textContent = message || '';
        statusEl.hidden = !message;
    }

    window.StockAgentReportRerunControls = { buttonForScope, setButtonLabel, disableButtons, configureCancelButton, setStatus };
})();
