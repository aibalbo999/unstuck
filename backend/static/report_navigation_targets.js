(function () {
    function targetForItem(doc, sections, item, index) {
        const href = item.getAttribute('href') || '';
        const id = href.startsWith('#') ? href.slice(1) : '';
        return id ? doc.getElementById(id) : sections[index] || null;
    }

    function labelForTarget(target) {
        if (target.id === 'overview') return '概覽總覽';
        return (target.querySelector('.section-title')?.textContent || '').trim();
    }

    function ensureLabel(item) {
        let label = item.querySelector('.nav-label');
        if (label) return label;
        const num = item.querySelector('.nav-num');
        label = item.ownerDocument.createElement('span');
        label.className = 'nav-label';
        Array.from(item.childNodes).forEach(node => {
            if (node !== num) node.remove();
        });
        item.appendChild(label);
        return label;
    }

    window.StockAgentReportNavigationTargets = { ensureLabel, labelForTarget, targetForItem };
})();
