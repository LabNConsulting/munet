ORG := README.org
YANG := labn-munet-config.yang
YANG_SCHEMA := munet/munet-schema.json
SCHEMA := test-schema.json
LOG_CLI := # --log-cli
TMP := .testtmp

POETRY := env PATH="$(PATH)" poetry
POETRYRUN := $(POETRY) run

MAKE_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

all: $(TMP) $(YANG) $(YANG_SCHEMA) doc ci-lint test yang-test

.PHONY: doc
doc:
	$(POETRYRUN) $(MAKE) -C doc html

doc-start:
	sudo podman run -it --rm -p 8088:80 -d --volume $(MAKE_DIR)/doc/build/html:/usr/share/nginx/html --name sphinx docker.io/nginx

doc-stop:
	sudo podman stop sphinx

# We hand craft this to keep things cleaner
doc-apidoc:
	$(POETRYRUN) sphinx-apidoc -f --module-first --ext-doctest --extensions sphinx-prompt -o doc/source/apidoc munet

prepare-publish: $(YANG_SCHEMA)

lint:
	$(POETRYRUN) pydocstyle ./munet
	$(POETRYRUN) pylint ./munet $(shell find ./tests/*/* -name '*.py')

ci-lint:
	$(POETRYRUN) pydocstyle ./munet
	$(POETRYRUN) pylint --disable="fixme" ./munet ./tests

test: test-validate ci-lint
	sudo -E $(POETRYRUN) mutest tests
	sudo -E $(POETRYRUN) pytest -s -v --cov=munet --cov-report=xml tests

clean:
	rm -f *.yang coverage.xml err.out ox-rfc.el
	rm -rf .testtmp/schema

run:
	sudo -E $(POETRYRUN) python3 -m munet

install:
	$(POETRY) install

# ====
# YANG
# ====

# -------------------------
# YANG from source ORG file
# -------------------------

ajv = $(or $(and $(shell which ajv),ajv $(1)),)
y2j = $(POETRYRUN) python -c 'import sys; import json; import yaml; json.dump(yaml.safe_load(sys.stdin), sys.stdout, indent=2)' < $(1) > $(2)

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

$(YANG_SCHEMA): $(YANG)
	$(POETRYRUN) pyang --plugindir .venv/src/pyang-json-schema-plugin/jsonschema/jsonschema.py --format jsonschema  -o $@ $<

$(TMP):
	mkdir -p .testtmp

KINDS_DATA := .testtmp/kinds.json

.testtmp/%.json: munet/%.yaml $(TMP)
	$(call y2j,$<,$@)

.testtmp/basic.json: tests/basic/munet.yaml $(TMP)
	$(call y2j,$<,$@)

test-validate: $(YANG_SCHEMA) $(KINDS_DATA) .testtmp/basic.json $(TMP)
	@echo "testing basic with yang generated schema"
	$(call ajv,--spec=draft2020 -d .testtmp/basic.json -s $(YANG_SCHEMA))
	$(POETRYRUN) jsonschema --instance .testtmp/basic.json $(YANG_SCHEMA)

	@echo "testing kinds with yang generated schema"
	$(call ajv,--spec=draft2020 -d .testtmp/kinds.json -s $(YANG_SCHEMA))
	$(POETRYRUN) jsonschema --instance .testtmp/kinds.json $(YANG_SCHEMA)
