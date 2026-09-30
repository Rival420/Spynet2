# Common tasks. `make help` lists them.
PI ?= pi@raspberrypi.local
REMOTE_DIR ?= ~/spynet
PY ?= .venv/bin/python

.PHONY: help venv build dev-api dev-ui run deploy clean

help:
	@echo "make venv      create .venv and install Python deps"
	@echo "make build     build the dashboard into spynet/dist"
	@echo "make run       run the server locally (needs sudo for ARP)"
	@echo "make dev-ui    run the Vite dev server with hot reload"
	@echo "make deploy    build, copy to the Pi and (re)install the service   PI=$(PI)"

venv:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

build:
	cd spynet && npm install --no-audit --no-fund && npm run build

run:
	sudo $(PY) server.py

dev-api:
	sudo $(PY) server.py

dev-ui:
	cd spynet && npm run dev

deploy: build
	rsync -az --delete \
	  --exclude .git --exclude node_modules --exclude .venv --exclude '*.db*' --exclude __pycache__ \
	  ./ $(PI):$(REMOTE_DIR)/
	ssh -t $(PI) 'sudo $(REMOTE_DIR)/deploy/install.sh'

clean:
	rm -rf spynet/dist spynet/node_modules .venv __pycache__
