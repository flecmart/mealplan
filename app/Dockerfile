FROM python:3.11
WORKDIR /app
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
CMD ["waitress-serve", "--port", "5000", "wsgi:app"]
