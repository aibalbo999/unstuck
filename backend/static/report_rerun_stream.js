(function () {
    function statusForPayload(payload) {
        if (payload.type === 'status') return payload.message || '報告重跑中...';
        if (payload.type === 'progress') {
            const name = payload.name ? `：${payload.name}` : '';
            return `報告重跑中${name}`;
        }
        if (payload.type === 'report_done') return '新報告已產生，正在整理列表...';
        return '';
    }

    function open(options) {
        return new Promise((resolve, reject) => {
            const eventSource = new EventSource(options.streamUrl);
            eventSource.onmessage = (event) => {
                let payload = {};
                try {
                    payload = JSON.parse(event.data);
                } catch (err) {
                    return;
                }

                const status = statusForPayload(payload);
                if (status) {
                    options.onStatus(status);
                    return;
                }
                if (payload.type === 'done') {
                    eventSource.close();
                    resolve(payload);
                    return;
                }
                if (payload.type === 'error') {
                    eventSource.close();
                    reject(new Error(payload.message || '報告重跑失敗'));
                }
            };
            eventSource.onerror = () => {
                options.onStatus('重跑連線暫時中斷，瀏覽器正在自動接續...');
            };
        });
    }

    window.StockAgentReportRerunStream = { open };
})();
