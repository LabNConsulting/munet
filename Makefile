unexport VIRTUAL_ENV
ORG := README.org
YANG := labn-munet-config.yang
SCHEMA := test-schema.json
JDATA := test-data.json
LOG_CLI := # --log-cli
TMP := .testtmp

all: $(TMP) ci-lint test $(YANG) yang-test

lint:
	pylint ./munet $(shell find ./tests/*/* -name '*.py')

ci-lint:
	env PATH="$(PATH)" poetry run pylint --disable="fixme" ./munet ./tests

test:
	sudo env PATH="$(PATH)" poetry run pytest -s -v --cov=munet --cov-report=xml tests

clean:
	rm -f *.yang coverage.xml err.out ox-rfc.el
	rm -rf .testtmp/schema

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

ajv = $(or $(and $(shell which ajv),ajv $(1)),)
y2j = python  -c 'import sys; import json; import yaml; json.dump(yaml.safe_load(sys.stdin), sys.stdout, indent=2)' < $(1) > $(2)

$(YANG): $(ORG)
	sed -n '/#+begin_src yang :exports code/,/^#+end_src/p' $< | sed '/^#/d' >$@


export DOCKRUN ?= docker run --user $(shell id -u) --network=host -v $$(pwd):/work labn/org-rfc
EMACSCMD := $(DOCKRUN) emacs -Q --batch --eval '(setq-default indent-tabs-mode nil)' --eval '(setq org-confirm-babel-evaluate nil)' -l ./ox-rfc.el

# $(YANG): $(ORG) ox-rfc.el
# 	$(EMACSCMD) $< --eval '(org-sbe test-validate-module)' 2>&1

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

$(TMP):
	mkdir -p .testtmp

$(SCHEMA): test-schema.yaml
	$(call y2j,$<,$@)

$(JDATA): munet/kinds.yaml
	$(call y2j,$<,$@)

validate: $(SCHEMA) $(JDATA) $(TMP)
	$(call ajv,--spec=draft2020 -d $(JDATA) -s $(SCHEMA))
	jsonschema --instance $(JDATA) $(SCHEMA)

CANON_SCHEMA := .testtmp/munet-schema.json
YANG_SCHEMA := .testtmp/yang-schema.json
KINDS_DATA := .testtmp/kinds.json

.testtmp/%.json: munet/%.yaml $(TMP)
	$(call y2j,$<,$@)

.testtmp/basic.json: tests/basic/munet.yaml $(TMP)
	$(call y2j,$<,$@)

$(YANG_SCHEMA): $(YANG) $(TMP)
	pyang --plugindir .venv/src/pyang-json-schema-plugin/jsonschema --format jsonschema  -o $@ $<

test-valid: $(CANON_SCHEMA) $(YANG_SCHEMA) $(KINDS_DATA) .testtmp/basic.json $(TMP)
	@echo "testing kinds with canonical schema"
	$(call ajv,--spec=draft2020 -d .testtmp/kinds.json -s .testtmp/munet-schema.json)
	jsonschema --instance .testtmp/kinds.json .testtmp/munet-schema.json

	@echo "testing basic with canonical schema"
	$(call ajv,--spec=draft2020 -d .testtmp/basic.json -s .testtmp/munet-schema.json)
	jsonschema --instance .testtmp/basic.json .testtmp/munet-schema.json

	@echo "testing basic with yang generated schema"
	$(call ajv,--spec=draft2020 -d .testtmp/basic.json -s .testtmp/yang-schema.json)
	jsonschema --instance .testtmp/basic.json .testtmp/yang-schema.json

	@echo "testing kinds with yang generated schema"
	$(call ajv,--spec=draft2020 -d .testtmp/kinds.json -s .testtmp/yang-schema.json)
	jsonschema --instance .testtmp/kinds.json .testtmp/yang-schema.json
