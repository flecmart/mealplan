FROM python:3.8-slim-buster
WORKDIR /app
# set environment
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
# install requirements
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
EXPOSE 5000
COPY . .
CMD ["flask", "run"]