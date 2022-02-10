unexport VIRTUAL_ENV
SCHEMA := test-schema.json
JDATA := test-data.json
LOG_CLI := # --log-cli


lint:
	pylint ./munet $(shell find ./tests/*/* -name '*.py')

test:
	sudo -E poetry run pytest -v -s $(LOG_CLI) --full-trace
	# sudo -E poetry run pytest -v -s $(LOG_CLI) --cli-on-error --full-trace

clean:
	rm err.out

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
	jsonschema --instance $(JDATA) $(SCHEMA)

CANON_SCHEMA := tests/schema/munet-schema.json
YANG_SCHEMA := tests/schema/yang-schema.json
KINDS_DATA := tests/schema/kinds.json

tests/schema/%.json: munet/%.yaml
	remarshal -p --indent=2 --if yaml --of json $< $@

tests/schema/basic.json: tests/basic/munet.yaml
	remarshal -p --indent=2 --if yaml --of json $< $@

$(YANG_SCHEMA): labn-munet-config.yang
	pyang --plugindir /home/chopps/w/pyang-json-schema-plugin/jsonschema --format jsonschema  -o $@ $<

test-valid: $(CANON_SCHEMA) $(YANG_SCHEMA) $(KINDS_DATA) tests/schema/basic.json
	@echo "testing kinds with canonical schema"
	ajv --spec=draft2020 -d tests/schema/kinds.json -s tests/schema/munet-schema.json
	jsonschema --instance tests/schema/kinds.json tests/schema/munet-schema.json

	@echo "testing basic with canonical schema"
	ajv --spec=draft2020 -d tests/schema/basic.json -s tests/schema/munet-schema.json
	jsonschema --instance tests/schema/basic.json tests/schema/munet-schema.json

	@echo "testing basic with yang generated schema"
	ajv --spec=draft2020 -d tests/schema/basic.json -s tests/schema/yang-schema.json
	jsonschema --instance tests/schema/basic.json tests/schema/yang-schema.json

	@echo "testing kinds with yang generated schema"
	ajv --spec=draft2020 -d tests/schema/kinds.json -s tests/schema/yang-schema.json
	jsonschema --instance tests/schema/kinds.json tests/schema/yang-schema.json
