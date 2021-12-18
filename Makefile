unexport VIRTUAL_ENV
SCHEMA := test-schema.json
JDATA := test-data.json
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

$(SCHEMA): test-schema.yaml
	remarshal --if yaml --of json $< $@

$(JDATA): munet/kinds.yaml
	remarshal --if yaml --of json $< $@

validate: $(SCHEMA) $(JDATA)
	ajv --spec=draft2020 -d $(JDATA) -s $(SCHEMA)
	# jsonschema --instance $(JDATA) $(SCHEMA)
