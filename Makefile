# matamata dev tasks. Run `make` (or `make help`) for the list.
#
# Every recipe runs with the project venv first on PATH, so pytest/mkdocs and the
# lint tools resolve without activating it (this also satisfies the pre-commit hook,
# which needs the venv on PATH). The heavy doc-asset regeneration lives in
# scripts/regen-docs.sh — Make is just the tidy entrypoint to it.

SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help

# Local machine config (VENV, ...) lives in .env, not hardcoded here. The same file is
# also sourced by scripts/regen-docs.sh; copy .env.example to .env to set it up.
-include .env
ifndef VENV
$(error VENV is not set — copy .env.example to .env and adjust it for your machine)
endif
export PATH := $(VENV):$(PATH)

.PHONY: help test regen lint fix docs serve check gallery \
        assets png png-hosts png-tables png-apply

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

## --- quality gate -----------------------------------------------------------

test: ## Run the test suite
	pytest -q

regen: ## Regenerate the golden SVG/HTML snapshots (review the diff!)
	PD_REGEN=1 pytest -q tests/test_render.py

lint: ## isort/black --check + mypy + pylint
	./lint.sh

fix: ## Auto-fix imports/formatting (isort + black), then git add -u
	./lint.sh fix

docs: ## Build the docs with mkdocs --strict (link check)
	mkdocs build --strict

serve: ## Live-preview the docs locally
	mkdocs serve

check: test lint docs ## The full release gate: tests + lint + strict docs

## --- regenerated, committed assets (keep in sync after a render change) ------

gallery: ## Rebuild the committed dev preview gallery (examples/gallery.html)
	cd examples && PYTHONPATH=../src python gallery.py

png: ## Regenerate the base-loader CLI doc previews (docs/*.png)
	scripts/regen-docs.sh cli

png-hosts: ## Regenerate the host-rendered SVG previews (world-cup, libertadores, copa-rio)
	scripts/regen-docs.sh hosts

png-tables: ## Regenerate the HTML-table screenshots (copa-rio + knockout-8 light/dark)
	scripts/regen-docs.sh tables

png-apply: ## Regenerate the apply_results before/after JSON + previews
	scripts/regen-docs.sh apply

assets: gallery ## Rebuild EVERYTHING on the sync list (gallery + all PNGs)
	scripts/regen-docs.sh all
