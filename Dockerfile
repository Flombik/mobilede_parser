FROM python:3.9-slim as builder

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /build

# Upgrading pip and installing project requirements
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN python -m pip install --upgrade pip && \
    pip install psycopg2-binary gunicorn
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM python:3.9-slim

COPY --from=builder /opt/venv /opt/venv

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

ENV PATH="/opt/venv/bin:$PATH"

# Updating packages list and installing some requirements
RUN apt update && \
    apt install -y --no-install-recommends netcat && \
    apt clean

COPY . .