(function () {
    function create(options) {
        const viewMap = options.views || {};
        const transitionMs = options.transitionMs || 500;
        const views = Object.values(viewMap).filter(Boolean);

        function switchView(viewId) {
            views.forEach(view => {
                view.classList.remove('active');
                setTimeout(() => {
                    if (!view.classList.contains('active')) {
                        view.style.display = 'none';
                    }
                }, transitionMs);
            });

            const target = viewMap[viewId] || document.getElementById(viewId);
            if (!target) return;
            target.style.display = 'flex';
            void target.offsetWidth;
            target.classList.add('active');
        }

        return { switchView };
    }

    window.StockAgentViewController = { create };
})();
