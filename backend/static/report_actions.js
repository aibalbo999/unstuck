(function () {
    function downloadReport(filename, format) {
        if (!filename) return;
        window.location.href = `/api/report/${encodeURIComponent(filename)}/download/${format}`;
    }

    function bindDownloads(options) {
        const getFilename = options.getFilename;
        const bindings = [
            [options.htmlBtn, 'html'],
            [options.mdBtn, 'md'],
            [options.dataBtn, 'data']
        ];

        bindings.forEach(([button, format]) => {
            if (!button) return;
            button.addEventListener('click', () => {
                downloadReport(getFilename(), format);
            });
        });
    }

    function setReportTitle(options) {
        if (!options.titleEl) return;
        options.titleEl.textContent = `${options.ticker} ${options.pipelineMeta(options.pipelineId).reportSuffix}`;
    }

    window.StockAgentReportActions = {
        bindDownloads,
        downloadReport,
        setReportTitle
    };
})();
