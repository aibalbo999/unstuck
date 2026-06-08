(function () {
    function scrollBehavior(win) {
        return win.matchMedia && win.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
    }

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

    function activate(items, targetId) {
        items.forEach(item => item.classList.toggle('active', item.dataset.targetId === targetId));
    }

    function enhance(doc) {
        if (!doc) return false;
        const win = doc.defaultView || window;
        const sections = Array.from(doc.querySelectorAll('#overview, .section[id]'));
        const navItems = Array.from(doc.querySelectorAll('.nav-item'));
        if (!sections.length || !navItems.length) return false;

        navItems.forEach((item, index) => {
            const target = targetForItem(doc, sections, item, index);
            if (!target || !target.id) {
                item.hidden = true;
                item.setAttribute('aria-disabled', 'true');
                return;
            }
            item.hidden = false;
            item.removeAttribute('aria-disabled');
            item.dataset.targetId = target.id;
            item.setAttribute('href', `#${target.id}`);
            const label = labelForTarget(target);
            if (label) ensureLabel(item).textContent = label;
            if (item.dataset.navEnhanced === '1') return;
            item.dataset.navEnhanced = '1';
            item.addEventListener('click', event => {
                const currentTarget = doc.getElementById(item.dataset.targetId);
                if (!currentTarget) return;
                event.preventDefault();
                currentTarget.scrollIntoView({ behavior: scrollBehavior(win), block: 'start' });
                activate(navItems, currentTarget.id);
                if (win.history && win.history.pushState) win.history.pushState(null, '', `#${currentTarget.id}`);
            });
        });

        if (win.IntersectionObserver && doc.body?.dataset.reportNavObserver !== '1') {
            doc.body.dataset.reportNavObserver = '1';
            const observer = new win.IntersectionObserver(entries => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) activate(navItems, entry.target.id);
                });
            }, { rootMargin: '-15% 0px -60% 0px', threshold: 0.01 });
            sections.forEach(section => observer.observe(section));
        }
        return true;
    }

    function bind(iframe) {
        if (!iframe) return;
        const onLoad = () => {
            try {
                enhance(iframe.contentDocument);
            } catch (_) {
                // Ignore cross-origin or partially loaded iframe states.
            }
        };
        iframe.addEventListener('load', onLoad);
        onLoad();
    }

    window.StockAgentReportNavigation = { bind, enhance };
})();
