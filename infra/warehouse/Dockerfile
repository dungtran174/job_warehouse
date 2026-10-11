FROM python:3.12-slim-bookworm

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src

# Install only the warehouse extra. The crawler package/dependencies are not copied.
COPY pyproject.toml /app/pyproject.toml
RUN python -c "import subprocess, tomllib; f=open('pyproject.toml','rb'); deps=tomllib.load(f)['project']['optional-dependencies']['warehouse']; subprocess.check_call(['python','-m','pip','install','--no-cache-dir',*deps])"
COPY src/job_warehouse /app/src/job_warehouse

ENTRYPOINT ["python", "-m", "job_warehouse.cli"]
