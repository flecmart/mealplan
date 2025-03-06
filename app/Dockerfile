FROM python:3.12
RUN groupadd -r mealplan && useradd -r -m -g mealplan mealplan
WORKDIR /home/mealplan
# Install chromium
RUN apt-get update \
&& apt-get install -y chromium chromium-driver
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir -r requirements.txt
USER mealplan
# download nltk data for natural language processing
RUN python -c "import nltk; nltk.download('punkt_tab'); nltk.download('averaged_perceptron_tagger_eng')"
EXPOSE 5000
COPY . .
CMD ["waitress-serve", "--port", "5000", "wsgi:app"]
