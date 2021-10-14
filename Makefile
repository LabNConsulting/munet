unexport VIRTUAL_ENV
LOG_CLI := # --log-cli

lint:
	pylint ./munet $(shell find ./tests/*/* -name '*.py')

test:
	sudo -E poetry run pytest -v -s $(LOG_CLI) --full-trace
	# sudo -E poetry run pytest -v -s $(LOG_CLI) --cli-on-error --full-trace

run:
	sudo -E poetry run python3 -m munet

install:
	poetry install
