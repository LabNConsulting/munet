unexport VIRTUAL_ENV
TEST_CLI_LEVEL := INFO

lint:
	pylint ./micronet $(shell find ./tests/*/* -name '*.py')

test:
	# sudo -E poetry run pytest -v -s --log-cli-level=$(TEST_CLI_LEVEL) --cli-on-error --full-trace
	sudo -E poetry run pytest -v -s --cli-on-error --full-trace

run:
	sudo -E poetry run python3 -m micronet

install:
	poetry install
