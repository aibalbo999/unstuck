(function () {
    const tabButtons = (root = document) => Array.from(root.querySelectorAll('[data-home-tab]'));

    function activate(tabName, options = {}) {
        tabButtons().forEach(button => {
            const selected = button.dataset.homeTab === tabName;
            button.classList.toggle('is-active', selected);
            button.setAttribute('aria-selected', selected ? 'true' : 'false');
            button.tabIndex = selected ? 0 : -1;
        });
        document.querySelectorAll('.home-tab-panel').forEach(panel => {
            const selected = panel.id === `home-panel-${tabName}`;
            panel.classList.toggle('is-active', selected);
            panel.hidden = !selected;
        });
        if (typeof options.onActivate === 'function') options.onActivate(tabName);
    }

    function focusButton(button, options) {
        activate(button.dataset.homeTab, options);
        button.focus();
    }

    function activateNextTab(currentButton, direction, options) {
        const tablist = currentButton.closest('[role="tablist"]');
        const buttons = tabButtons(tablist || document);
        const index = buttons.indexOf(currentButton);
        if (index >= 0) focusButton(buttons[(index + direction + buttons.length) % buttons.length], options);
    }

    function bind(options = {}) {
        const moves = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 };
        tabButtons().forEach(button => {
            button.tabIndex = button.classList.contains('is-active') ? 0 : -1;
            button.addEventListener('click', () => activate(button.dataset.homeTab, options));
            button.addEventListener('keydown', event => {
                if (Object.prototype.hasOwnProperty.call(moves, event.key)) {
                    event.preventDefault();
                    activateNextTab(button, moves[event.key], options);
                } else if (event.key === 'Home' || event.key === 'End') {
                    const tablist = button.closest('[role="tablist"]');
                    const buttons = tabButtons(tablist || document);
                    event.preventDefault();
                    focusButton(buttons[event.key === 'Home' ? 0 : buttons.length - 1], options);
                }
            });
        });
    }

    window.StockAgentHomeTabs = { activate, bind };
})();
