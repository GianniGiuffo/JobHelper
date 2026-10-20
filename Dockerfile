FROM python:3.11.17-slim-bookworm@sha256:0a310eeecf4e1f5a0743f9a6520c90c88d089c903ca5fd283f501e3a805f5f89
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY requirements.lock ./
COPY job_hunter ./job_hunter
COPY prompts ./prompts
COPY config/search-vocabulary.txt ./config/search-vocabulary.txt
RUN pip install --no-cache-dir -c requirements.lock . && useradd --uid 10001 --create-home hunter && mkdir /data && chown hunter /data
USER hunter
EXPOSE 8000
CMD ["uvicorn", "job_hunter.api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--log-level", "critical"]
