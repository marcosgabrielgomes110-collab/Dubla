SHELL := /bin/bash
API_PORT ?= 8000
WEB_PORT ?= 5173
RUN_DIR := .run
PY := .venv/bin/python

.DEFAULT_GOAL := help
.PHONY: help install build test all run-api run-frontend stop-api stop-frontend stop up up-prod restart status health logs logs-api logs-frontend clean

help: ## Show this help
	@printf "Dubla — make targets\n\n"
	@printf "  \033[1m%-18s\033[0m %s\n" "make up" "start API + Vite dev (background)"
	@printf "  \033[1m%-18s\033[0m %s\n" "make up-prod" "build frontend and serve it from the API"
	@printf "  \033[1m%-18s\033[0m %s\n" "make run-api" "start the FastAPI server (background, port $(API_PORT))"
	@printf "  \033[1m%-18s\033[0m %s\n" "make run-frontend" "start the Vite dev server (background, port $(WEB_PORT))"
	@printf "  \033[1m%-18s\033[0m %s\n" "make stop" "stop API and frontend"
	@printf "  \033[1m%-18s\033[0m %s\n" "make stop-api" "stop the API"
	@printf "  \033[1m%-18s\033[0m %s\n" "make stop-frontend" "stop the Vite dev server"
	@printf "  \033[1m%-18s\033[0m %s\n" "make restart" "stop and start everything"
	@printf "  \033[1m%-18s\033[0m %s\n" "make status" "show PIDs and API health"
	@printf "  \033[1m%-18s\033[0m %s\n" "make health" "curl the API health endpoint"
	@printf "  \033[1m%-18s\033[0m %s\n" "make logs" "follow API + frontend logs"
	@printf "  \033[1m%-18s\033[0m %s\n" "make install" "install python + npm dependencies"
	@printf "  \033[1m%-18s\033[0m %s\n" "make build" "build the frontend (dist/)"
	@printf "  \033[1m%-18s\033[0m %s\n" "make test" "run pytest"
	@printf "  \033[1m%-18s\033[0m %s\n" "make all" "install + build + test"
	@printf "  \033[1m%-18s\033[0m %s\n" "make clean" "stop services and remove .run + frontend/dist"

install: ## Install python and npm dependencies
	@test -d .venv || python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements.txt
	@test -d frontend/node_modules || (cd frontend && npm install --no-audit --no-fund)
	@echo "dependencies ok"

build: ## Build the frontend into frontend/dist
	cd frontend && npm run build

test: ## Run the pytest suite
	$(PY) -m pytest -q

all: install build test ## Prepare everything (deps + build + tests)

run-api: ## Start the API in background
	@mkdir -p $(RUN_DIR)
	@if [ -f $(RUN_DIR)/api.pid ] && kill -0 $$(cat $(RUN_DIR)/api.pid) 2>/dev/null; then \
		echo "API already running (pid $$(cat $(RUN_DIR)/api.pid))"; \
	else \
		setsid bash -c 'echo $$$$ > $(CURDIR)/$(RUN_DIR)/api.pid; cd $(CURDIR) && exec $(CURDIR)/$(PY) -m src.Dubla_Api --port $(API_PORT)' > $(CURDIR)/$(RUN_DIR)/api.log 2>&1 & \
		sleep 1; \
		echo "API started: http://127.0.0.1:$(API_PORT) (pid $$(cat $(RUN_DIR)/api.pid))"; \
	fi

run-frontend: ## Start the Vite dev server in background
	@mkdir -p $(RUN_DIR)
	@if [ -f $(RUN_DIR)/frontend.pid ] && kill -0 $$(cat $(RUN_DIR)/frontend.pid) 2>/dev/null; then \
		echo "frontend already running (pid $$(cat $(RUN_DIR)/frontend.pid))"; \
	else \
		setsid bash -c 'echo $$$$ > $(CURDIR)/$(RUN_DIR)/frontend.pid; cd $(CURDIR)/frontend && exec npm run dev -- --host 127.0.0.1 --port $(WEB_PORT)' > $(CURDIR)/$(RUN_DIR)/frontend.log 2>&1 & \
		sleep 1; \
		echo "frontend started: http://127.0.0.1:$(WEB_PORT) (pid $$(cat $(RUN_DIR)/frontend.pid))"; \
	fi

stop-api: ## Stop the API
	@if [ -f $(RUN_DIR)/api.pid ]; then \
		pid=$$(cat $(RUN_DIR)/api.pid); \
		if kill -0 $$pid 2>/dev/null; then \
			kill -TERM -$$pid 2>/dev/null || kill -TERM $$pid 2>/dev/null; \
			sleep 1; \
			echo "API stopped (pid $$pid)"; \
		else \
			echo "API not running"; \
		fi; \
		rm -f $(RUN_DIR)/api.pid; \
	else \
		echo "API not running"; \
	fi

stop-frontend: ## Stop the Vite dev server
	@if [ -f $(RUN_DIR)/frontend.pid ]; then \
		pid=$$(cat $(RUN_DIR)/frontend.pid); \
		if kill -0 $$pid 2>/dev/null; then \
			kill -TERM -$$pid 2>/dev/null || kill -TERM $$pid 2>/dev/null; \
			sleep 1; \
			echo "frontend stopped (pid $$pid)"; \
		else \
			echo "frontend not running"; \
		fi; \
		rm -f $(RUN_DIR)/frontend.pid; \
	else \
		echo "frontend not running"; \
	fi

stop: stop-api stop-frontend ## Stop API and frontend

up: run-api run-frontend ## Start API + frontend dev
	@sleep 1
	@$(MAKE) --no-print-directory status

up-prod: build ## Build the frontend and serve it from the API
	@$(MAKE) --no-print-directory stop-frontend || true
	@$(MAKE) --no-print-directory stop-api || true
	@$(MAKE) --no-print-directory run-api
	@echo "UI: http://127.0.0.1:$(API_PORT)/"

restart: stop up ## Restart everything

status: ## Show running services and API health
	@for name in api frontend; do \
		file=$(RUN_DIR)/$$name.pid; \
		if [ -f $$file ] && kill -0 $$(cat $$file) 2>/dev/null; then \
			echo "$$name: running (pid $$(cat $$file))"; \
		else \
			echo "$$name: stopped"; \
		fi; \
	done
	@curl -fsS http://127.0.0.1:$(API_PORT)/api/v1/health 2>/dev/null && echo || echo "API health: unreachable"

health: ## Curl the API health endpoint
	@curl -fsS http://127.0.0.1:$(API_PORT)/api/v1/health && echo

logs: ## Follow API + frontend logs
	@mkdir -p $(RUN_DIR)
	@touch $(RUN_DIR)/api.log $(RUN_DIR)/frontend.log
	tail -n 60 -f $(RUN_DIR)/api.log $(RUN_DIR)/frontend.log

logs-api: ## Follow the API log
	@mkdir -p $(RUN_DIR); touch $(RUN_DIR)/api.log
	tail -n 80 -f $(RUN_DIR)/api.log

logs-frontend: ## Follow the frontend log
	@mkdir -p $(RUN_DIR); touch $(RUN_DIR)/frontend.log
	tail -n 80 -f $(RUN_DIR)/frontend.log

clean: stop ## Stop services and remove build/run artifacts
	rm -rf $(RUN_DIR) frontend/dist
	@echo "cleaned .run and frontend/dist (Data/ preserved)"
