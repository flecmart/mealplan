# Makefile
## 🌶 flask and hot-reload
flask:
	docker-compose -f docker-compose.dev.yml build
	docker-compose -f docker-compose.dev.yml run --rm  -e FLASK_APP=app.py -e FLASK_DEBUG=0 --service-ports app

flaskdebug:
	docker-compose -f docker-compose.dev.yml build
	docker-compose -f docker-compose.dev.yml run --rm  -e DEBUGGER=True -e FLASK_APP=app.py -e FLASK_DEBUG=1 --service-ports app

down:
	docker-compose -f docker-compose.dev.yml down