FROM --platform=linux/arm64 postgres:17.11-trixie@sha256:413da4542e091471785b7f18f1a2258df134bc6506ab4e1e53725aa8bcfdb650
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3.13=3.13.5-2+deb13u3 python3.13-venv=3.13.5-2+deb13u3 && python3.13 -m venv /opt/pg-test-venv
COPY backend/requirements.lock /opt/locks/backend.lock
COPY tests/pg_validation/binary.lock /opt/locks/binary.lock
RUN /opt/pg-test-venv/bin/python -m pip install --require-hashes -r /opt/locks/backend.lock -r /opt/locks/binary.lock
COPY backend /work/backend
COPY tests /work/tests
COPY prompts /work/prompts
COPY manifest.json /opt/validation-manifest.json
RUN install -d -o 999 -g 999 -m 0700 /results
ENV PATH="/opt/pg-test-venv/bin:${PATH}" PYTHONPATH="/work/tests:/work/backend" PYTHONDONTWRITEBYTECODE=1 PSYCOPG_IMPL=binary
USER 999:999
WORKDIR /work
ENTRYPOINT ["/opt/pg-test-venv/bin/python", "-B", "-m", "pg_validation.entrypoint"]
