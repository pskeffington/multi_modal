PYTHON ?= python3

.PHONY: build check run install-user

build:
	$(PYTHON) -m compileall -q src

check: build
	sh -n scripts/launch.sh scripts/install-user.sh
	@if command -v desktop-file-validate >/dev/null 2>&1; then \
		tmp=$$(mktemp -d); \
		trap 'rm -rf "$$tmp"' EXIT; \
		XDG_DATA_HOME="$$tmp/data" sh scripts/install-user.sh >/dev/null; \
		desktop-file-validate "$$tmp/data/applications/multi-modal-router.desktop"; \
	else \
		echo "desktop-file-validate unavailable; desktop entry validation skipped"; \
	fi

run:
	sh scripts/launch.sh

install-user:
	sh scripts/install-user.sh
