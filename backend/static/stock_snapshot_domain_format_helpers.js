(function () {
    const domainMethods = {
        compact(value) {
            if (value === null || value === undefined || value === '') return '-';
            const number = Number(value);
            if (!Number.isFinite(number)) return String(value ?? '-');
            if (Math.abs(number) >= 100000000) return `${this.compactScaled(number, 100000000)}億`;
            if (Math.abs(number) >= 10000) return `${this.compactScaled(number, 10000)}萬`;
            return number.toLocaleString();
        },
        compactScaled(value, divisor) {
            return (Number(value) / divisor).toLocaleString(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 });
        },
        financialValueLabel(value) {
            return Number.isFinite(Number(value)) ? `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })}B` : '-';
        },
        lotsLabel(value) {
            const number = Math.abs(Number(value));
            if (!Number.isFinite(number)) return '-';
            const digits = Number.isInteger(number) ? 0 : 1;
            return `${number.toLocaleString(undefined, { maximumFractionDigits: digits, minimumFractionDigits: digits })}張`;
        },
        flowWord(value) {
            const number = Number(value);
            return !Number.isFinite(number) || number === 0 ? '持平' : (number > 0 ? '買超' : '賣超');
        },
        coverageLabel(value) {
            const number = Number(value);
            return Number.isFinite(number) ? `${number.toFixed(1)}x` : '-';
        }
    };
    window.StockAgentStockSnapshotDomainFormatHelpers = { domainMethods };
})();
