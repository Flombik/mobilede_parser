FROM python:3.9

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

RUN apt-get update && \
    apt install -y netcat && \
    apt clean

RUN python -m pip install --upgrade pip
RUN pip install psycopg2-binary gunicorn
COPY requirements.txt /code/
RUN pip install -r requirements.txt

COPY web-entrypoint.sh /code/web-entrypoint.sh
COPY worker-entrypoint.sh /code/worker-entrypoint.sh
COPY beat-entrypoint.sh /code/beat-entrypoint.sh

COPY . /code