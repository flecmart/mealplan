FROM python:3.8-alpine
WORKDIR /app
# set environment
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
# install requirements
COPY requirements.txt requirements.txt
RUN apk update --no-cache \
&& apk add build-base postgresql-dev libpq --no-cache --virtual .build-deps \
&& pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir -r requirements.txt \
&& apk del .build-deps
RUN apk add postgresql-libs libpq --no-cache
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('averaged_perceptron_tagger')"
EXPOSE 5000
COPY . .
CMD ["flask", "run"]