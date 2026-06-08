(function () {
    function activate(tabName) {
        document.querySelectorAll('[data-home-tab]').forEach(button => {
            const selected = button.dataset.homeTab === tabName;
            button.classList.toggle('is-active', selected);
            button.setAttribute('aria-selected', selected ? 'true' : 'false');
        });
        document.querySelectorAll('.home-tab-panel').forEach(panel => {
            const selected = panel.id === `home-panel-${tabName}`;
            panel.classList.toggle('is-active', selected);
            panel.hidden = !selected;
        });
    }

    function bind() {
        document.querySelectorAll('[data-home-tab]').forEach(button => {
            button.addEventListener('click', () => activate(button.dataset.homeTab));
        });
    }

    document.addEventListener('DOMContentLoaded', bind);
    window.StockAgentHomeTabs = { activate, bind };
})();
