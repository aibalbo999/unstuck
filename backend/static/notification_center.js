(function () {
    const focusableSelectors = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

    function create(options = {}) {
        const region = options.toastRegion || document.getElementById('toast-region');
        const dialog = options.dialog || document.getElementById('confirm-dialog');
        const titleEl = dialog ? dialog.querySelector('[data-confirm-title]') : null;
        const messageEl = dialog ? dialog.querySelector('[data-confirm-message]') : null;
        const cancelBtn = dialog ? dialog.querySelector('[data-confirm-cancel-button]') : null;
        const okBtn = dialog ? dialog.querySelector('[data-confirm-ok-button]') : null;
        const backdrop = dialog ? dialog.querySelector('[data-confirm-cancel]') : null;

        if (region) region.setAttribute('aria-live', 'polite');

        function removeToast(toast) {
            toast.classList.add('is-leaving');
            window.setTimeout(() => toast.remove(), 180);
        }

        function toast(message, tone) {
            if (!region || !message) return;
            const item = document.createElement('div');
            item.className = `toast-message is-${tone || 'info'}`;
            item.setAttribute('role', tone === 'error' ? 'alert' : 'status');
            const text = document.createElement('span');
            text.textContent = message;
            const close = document.createElement('button');
            close.type = 'button';
            close.className = 'toast-close';
            close.setAttribute('aria-label', '關閉通知');
            close.textContent = 'x';
            close.addEventListener('click', () => removeToast(item));
            item.append(text, close);
            region.appendChild(item);
            window.setTimeout(() => removeToast(item), 5200);
        }

        function confirm(message, settings = {}) {
            if (!dialog || !messageEl || !cancelBtn || !okBtn) return Promise.resolve(false);
            return new Promise(resolve => {
                const previousFocus = document.activeElement;
                const finish = value => {
                    dialog.hidden = true;
                    dialog.classList.remove('is-danger');
                    cancelBtn.removeEventListener('click', onCancel);
                    okBtn.removeEventListener('click', onOk);
                    if (backdrop) backdrop.removeEventListener('click', onCancel);
                    document.removeEventListener('keydown', onKeydown);
                    if (previousFocus && previousFocus.focus) previousFocus.focus();
                    resolve(value);
                };
                const onCancel = () => finish(false);
                const onOk = () => finish(true);
                const trapFocus = event => {
                    const isTabKey = event.key === 'Tab';
                    if (!isTabKey) return;
                    const focusable = Array.from(dialog.querySelectorAll(focusableSelectors))
                        .filter(element => !element.disabled && element.offsetParent !== null);
                    const firstFocusable = focusable[0];
                    const lastFocusable = focusable[focusable.length - 1];
                    if (!firstFocusable || !lastFocusable) return;
                    if (event.shiftKey && document.activeElement === firstFocusable) {
                        event.preventDefault();
                        lastFocusable.focus();
                    } else if (!event.shiftKey && document.activeElement === lastFocusable) {
                        event.preventDefault();
                        firstFocusable.focus();
                    }
                };
                const onKeydown = event => {
                    if (event.key === 'Escape') {
                        finish(false);
                        return;
                    }
                    trapFocus(event);
                };

                if (titleEl) titleEl.textContent = settings.title || '確認操作';
                messageEl.textContent = message;
                cancelBtn.textContent = settings.cancelLabel || '取消';
                okBtn.textContent = settings.confirmLabel || '確認';
                const isDanger = Boolean(settings.danger) || settings.confirmLabel === '刪除';
                dialog.classList.toggle('is-danger', isDanger);
                dialog.hidden = false;
                cancelBtn.addEventListener('click', onCancel);
                okBtn.addEventListener('click', onOk);
                if (backdrop) backdrop.addEventListener('click', onCancel);
                document.addEventListener('keydown', onKeydown);
                (isDanger ? cancelBtn : okBtn).focus();
            });
        }

        return {
            success: message => toast(message, 'success'),
            error: message => toast(message, 'error'),
            info: message => toast(message, 'info'),
            confirm
        };
    }

    window.StockAgentNotificationCenter = { create };
})();
