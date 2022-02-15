unexport VIRTUAL_ENV
ORG := README.org
YANG := labn-munet-config.yang
SCHEMA := test-schema.json
JDATA := test-data.json
LOG_CLI := # --log-cli

all: ci-lint test $(YANG) yang-test

lint:
	pylint ./munet $(shell find ./tests/*/* -name '*.py')

ci-lint:
	pylint --disable="fixme" ./munet ./tests

test:
	sudo env PATH="$(PATH)" poetry run pytest -s -v --cov=munet --cov-report=xml tests

clean:
	rm  *.yang coverage.xml err.out ox-rfc.el

run:
	sudo -E poetry run python3 -m munet

install:
	poetry install

# ====
# YANG
# ====

# -------------------------
# YANG from source ORG file
# -------------------------

export DOCKRUN ?= docker run --user $(shell id -u) --network=host -v $$(pwd):/work labn/org-rfc
EMACSCMD := $(DOCKRUN) emacs -Q --batch --eval '(setq-default indent-tabs-mode nil)' --eval '(setq org-confirm-babel-evaluate nil)' -l ./ox-rfc.el

$(YANG): $(ORG)
	$(EMACSCMD) $< --eval '(org-sbe test-validate-module)' 2>&1

run-yang-test: $(ORG) ox-rfc.el
	$(EMACSCMD) $< -f ox-rfc-run-test-blocks 2>&1

yang-test: $(ORG) ox-rfc.el
	@echo Testing $<
	@result="$$($(EMACSCMD) $< -f ox-rfc-run-test-blocks 2>&1)"; \
	if [ -n "$$(echo \"$$result\"| grep FAIL)" ]; then \
		echo "$$result" | grep RESULT || true; \
		exit 1; \
	else \
		echo "$$result" | grep RESULT || true; \
	fi;

ox-rfc.el:
	curl -fLO 'https://raw.githubusercontent.com/choppsv1/org-rfc-export/master/ox-rfc.el'

# --------------------
# YANG data validation
# --------------------

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

$(YANG_SCHEMA): $(YANG)
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
