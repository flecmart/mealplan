# Makefile
## 🌶 flask and hot-reload
flask:
	docker-compose run --rm -e FLASK_APP=app.py -e FLASK_DEBUG=0 --service-ports app flask run --host 0.0.0.0

flaskdebug:
	docker-compose run --rm -e DEBUGGER=True -e FLASK_APP=app.py -e FLASK_DEBUG=1 --service-ports app flask run --host 0.0.0.0