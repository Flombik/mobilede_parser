FROM python:3.9

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /code

# Updating packages list and install some requirements
RUN apt update 
RUN apt install -y netcat wget unzip

# Chromium and Chrome Driver Installation
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list'

RUN apt update
RUN apt install -y google-chrome-stable

RUN wget https://chromedriver.storage.googleapis.com/93.0.4577.63/chromedriver_linux64.zip
RUN unzip chromedriver_linux64.zip
RUN mv chromedriver /usr/bin/chromedriver
RUN chown root:root /usr/bin/chromedriver
RUN chmod +x /usr/bin/chromedriver

# Cleaning up
RUN rm chromedriver_linux64.zip
RUN apt clean

COPY requirements.txt /code/
RUN python -m pip install --upgrade pip
RUN pip install psycopg2-binary gunicorn
RUN pip install -r requirements.txt

COPY web-entrypoint.sh /code/web-entrypoint.sh

COPY . /code