PYTHON ?= python3

.PHONY: build check run install-user install-gpu-optimizer

build:
	$(PYTHON) -m compileall -q src
	$(PYTHON) -m py_compile scripts/gpu_model_optimizer.py

check: build
	sh -n scripts/launch.sh scripts/install-user.sh scripts/install-gpu-optimizer.sh
	@if command -v desktop-file-validate >/dev/null 2>&1; then \
		tmp=$$(mktemp -d); \
		trap 'rm -rf "$$tmp"' EXIT; \
		mkdir -p "$$tmp/home"; \
		HOME="$$tmp/home" XDG_DATA_HOME="$$tmp/data" sh scripts/install-user.sh >/dev/null; \
		HOME="$$tmp/home" XDG_DATA_HOME="$$tmp/data" XDG_BIN_HOME="$$tmp/bin" XDG_CONFIG_HOME="$$tmp/config" sh scripts/install-gpu-optimizer.sh >/dev/null; \
		desktop-file-validate "$$tmp/data/applications/multi-modal-router.desktop"; \
		desktop-file-validate "$$tmp/data/applications/multi-modal-gpu-optimizer.desktop"; \
		desktop-file-validate "$$tmp/home/Desktop/Multi Modal GPU Optimizer.desktop"; \
	else \
		echo "desktop-file-validate unavailable; desktop entry validation skipped"; \
	fi

run:
	sh scripts/launch.sh

install-user:
	sh scripts/install-user.sh

install-gpu-optimizer:
	sh scripts/install-gpu-optimizer.sh
