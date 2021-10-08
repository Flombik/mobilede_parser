FROM python:3.9-slim as builder

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

# Upgrading pip and installing project requirements
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN python -m pip install --upgrade pip && \
    pip install psycopg2-binary gunicorn
COPY requirements.txt /code/
RUN pip install -r requirements.txt

FROM python:3.9-slim

COPY --from=builder /opt/venv /opt/venv

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

ENV PATH="/opt/venv/bin:$PATH"

# Updating packages list and installing some requirements
RUN apt update && \
    apt install -y --no-install-recommends netcat wget unzip gnupg2 && \
    apt clean

# Google Chrome Installation
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    sh -c 'echo "deb [arch=amd64] https://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' && \
    apt update && \
    apt install -y --no-install-recommends google-chrome-stable && \
    apt clean

# Chrome Driver Installation
RUN CHROME_VERSION=$(echo `google-chrome --version` | grep -Eio '[0-9]+' | head -1) && \
    LATEST_CHROME_DRIVER_VERSION=$(wget -qO- https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}) && \
    wget https://chromedriver.storage.googleapis.com/${LATEST_CHROME_DRIVER_VERSION}/chromedriver_linux64.zip && \
    unzip chromedriver_linux64.zip && \
    mv chromedriver /usr/bin/chromedriver && \
    chown root:root /usr/bin/chromedriver && \
    chmod +x /usr/bin/chromedriver && \
    rm chromedriver_linux64.zip

# Coping entrypoint scripts
COPY web-entrypoint.sh /code/web-entrypoint.sh

COPY . /code