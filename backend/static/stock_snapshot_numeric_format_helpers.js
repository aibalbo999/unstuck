(function () {
    const numericMethods = {
        priceLabel(value) {
            const number = Number(value);
            return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 2 }) : '-';
        },
        returnLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            const rounded = this.roundToOneDecimal(number);
            return `${rounded >= 0 ? '+' : ''}${rounded.toFixed(1)}%`;
        },
        signedPriceLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            return `${number >= 0 ? '+' : ''}${number.toFixed(2)}`;
        },
        volumeVsAvgLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            const rounded = this.roundToOneDecimal(number);
            return `${rounded >= 0 ? '+' : ''}${rounded.toFixed(1)}%`;
        },
        positionLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '';
            return `區間 ${number.toFixed(0)}%`;
        },
        percentDeltaLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            const rounded = this.roundToOneDecimal(number);
            return `${rounded >= 0 ? '+' : ''}${rounded.toFixed(1)}%`;
        },
        pointDeltaLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            return `${number >= 0 ? '+' : ''}${number.toFixed(1)}pp`;
        },
        percentLabel(value) {
            return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '-';
        },
        multipleLabel(value) {
            return Number.isFinite(Number(value)) ? Number(value).toFixed(1) : '-';
        },
        numericLabel(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return '-';
            return Number.isInteger(number) ? number.toLocaleString() : number.toFixed(1);
        },
        roundToOneDecimal(value) {
            const number = Number(value);
            if (!Number.isFinite(number)) return number;
            return Math.sign(number || 1) * Math.round(Math.abs(number) * 10) / 10;
        },
        returnClass(value) {
            return Number.isFinite(Number(value)) ? (Number(value) >= 0 ? 'is-positive' : 'is-negative') : '';
        }
    };
    window.StockAgentStockSnapshotNumericFormatHelpers = { numericMethods };
})();
