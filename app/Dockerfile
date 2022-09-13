FROM python:3.10
WORKDIR /app
# set environment
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
# Adding trusting keys to apt for repositories
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
# Install chromium
RUN sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
RUN sh -c 'echo "deb [arch=arm64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
RUN apt-get update \
&& apt-get install -y google-chrome-stable
# Install Unzip
RUN apt-get install -yqq unzip
# Download the Chrome Driver
RUN wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/`curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE`/chromedriver_linux64.zip
# Set display port as an environment variable
ENV DISPLAY=:99
# Unzip the Chrome Driver into /usr/local/bin directory
RUN unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/
# install build environment & requirements
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir -r requirements.txt
# download nltk data for natural language processing
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('averaged_perceptron_tagger')"
EXPOSE 5000
COPY . .
CMD ["flask", "run"]
