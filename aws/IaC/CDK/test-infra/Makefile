
SHELL := /bin/bash

# Lint python codes
lint:
	black -r ./

# Entry-point for cdk logging with a fresh new virtual environment
cdk-verify:
	( \
		python3 -m venv .venv; \
		source .venv/bin/activate; \
		pip3 install -r requirements.txt; \
		echo "To validate if dev environment works:"; \
		cdk synth; \
	)
