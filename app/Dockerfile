FROM python:3.10
WORKDIR /app
# set environment
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
# Install chromium
RUN apt-get update \
&& apt-get install -y chromium chromium-driver
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir -r requirements.txt
# download nltk data for natural language processing
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('averaged_perceptron_tagger')"
EXPOSE 5000
COPY . .
CMD ["python", "wsgi.py"]
