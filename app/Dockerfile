FROM python:3.8-alpine3.10
WORKDIR /app
# set environment
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
# update apk repo
RUN echo "http://dl-4.alpinelinux.org/alpine/v3.10/main" >> /etc/apk/repositories \
&& echo "http://dl-4.alpinelinux.org/alpine/v3.10/community" >> /etc/apk/repositories
# install build environment & requirements
COPY requirements.txt requirements.txt
RUN apk update --no-cache \
&& apk add build-base postgresql-dev libpq libxml2-dev libxslt-dev jpeg-dev zlib-dev --no-cache --virtual .build-deps \
&& pip install --no-cache-dir --upgrade pip \
&& pip install --no-cache-dir -r requirements.txt \
&& apk del .build-deps
# install dependant libs
RUN apk add postgresql-libs libpq libxslt chromium chromium-chromedriver --no-cache
# download nltk data for natural language processing
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('averaged_perceptron_tagger')"
EXPOSE 5000
COPY . .
CMD ["flask", "run"]