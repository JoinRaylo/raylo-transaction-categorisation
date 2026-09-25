FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY raylo_txncat-*.whl /tmp/
RUN pip install --no-cache-dir --disable-pip-version-check /tmp/raylo_txncat-*.whl

COPY benchmark_authority_live_proof.py ./

EXPOSE 8080
CMD ["python", "benchmark_authority_live_proof.py", "serve"]
