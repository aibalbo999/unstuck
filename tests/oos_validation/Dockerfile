FROM python@sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285
WORKDIR /work
ENV PYTHONPATH=/work/backend
COPY backend/oos_research /work/backend/oos_research
COPY backend/decision_backtest.py backend/trade_path_backtest.py backend/trade_execution_contract.py backend/trade_price_inputs.py /work/backend/
COPY backend/recommendation_labels.py backend/data_trust_values.py backend/mapping_fields.py backend/mapping_sequence_items.py /work/backend/
COPY tests/test_oos_research.py /work/tests/test_oos_research.py
COPY tests/oos_validation /work/tests/oos_validation
ENTRYPOINT ["python", "-m", "tests.oos_validation.entrypoint"]
