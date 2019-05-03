# Top level make file for building PandA webcontrol

TOP := $(CURDIR)

# Build defaults that can be overwritten by the CONFIG file if present
ANNOTYPES = $(error Define ANNOTYPES in CONFIG file)
PYMALCOLM = $(error Define PYMALCOLM in CONFIG file)
PANDA_ROOTFS = $(error Define PANDA_ROOTFS in CONFIG file)
PANDA_ROOT = $(error Define PANDA_ROOT in CONFIG file)
MAKE_ZPKG = $(PANDA_ROOTFS)/make-zpkg
MAKE_GITHUB_RELEASE = $(PANDA_ROOTFS)/make-github-release.py
PYTHON = $(PANDA_ROOT)/targets/rootfs/toolkit/bin/python2
BUILD_DIR = $(TOP)/build

DEFAULT_TARGETS = zpkg

# The CONFIG file is required.  If not present, create by copying CONFIG.example
# and editing as appropriate.
include CONFIG

default: $(DEFAULT_TARGETS)

# The cut down malcolm package we build
MALCOLM_BUILD = $(BUILD_DIR)/malcolm
ANNOTYPES_BUILD = $(BUILD_DIR)/annotypes
MALCOLMJS_BUILD = $(BUILD_DIR)/malcolmjs_docs

# Where we find static html files
WEB_ADMIN = $(PANDA_ROOTFS)/rootfs/web-admin

# A tag for our zpkg suffix
export GIT_VERSION := $(shell git describe --abbrev=7 --dirty --always --tags)

# The zpkg file that will be built
WEBSERVER_ZPKG = $(BUILD_DIR)/panda-webcontrol@$(GIT_VERSION).zpg

# The .py files we depend on to build our cut down distribution
MALCOLM_SOURCES := $(shell find $(PYMALCOLM)/malcolm -name \*.py)
ANNOTYPES_SOURCES := $(shell find $(ANNOTYPES)/annotypes -name \*.py)
MALCOLMJS_SOURCES := $(shell find $(MALCOLMJS)/docs/source)

# The other sources
SOURCES = $(wildcard $(TOP)/etc/*) $(wildcard $(TOP)/src/*)

# The built html templates
TEMPLATES = $(BUILD_DIR)/templates

$(MALCOLM_BUILD): $(MALCOLM_SOURCES)
	rm -rf $@
	mkdir -p $@/modules
	# Add some custom bits
	cp -rf $(PYMALCOLM)/malcolm/core $@
	cp -rf $(PYMALCOLM)/malcolm/modules/*.py $@/modules
	cp -rf $(PYMALCOLM)/malcolm/modules/builtin $@/modules
	cp -rf $(PYMALCOLM)/malcolm/modules/pandablocks $@/modules
	cp -rf $(PYMALCOLM)/malcolm/modules/web $@/modules
	rm -rf $@/modules/web/blocks $@/modules/builtin/docs
	rm $@/modules/web/www/index.html
	cp $(WEB_ADMIN)/static/favicon.ico $@/modules/web/www
	./make_settings.py "$(GIT_VERSION)" > $@/modules/web/www/settings.json
	cp $(PYMALCOLM)/malcolm/*.py $@
	find $@ -name '*.pyc' -delete
	$(PYTHON) -m compileall $@

$(ANNOTYPES_BUILD): $(ANNOTYPES_SOURCES)
	rm -rf $@
	mkdir -p $@
	cp $(ANNOTYPES)/annotypes/*.py $@
	$(PYTHON) -m compileall $@

$(MALCOLMJS_BUILD): $(MALCOLMJS_SOURCES)
	rm -rf $@
	cp -rf $(MALCOLMJS)/docs/source $@
	rm -rf $@/SMG $@/userguide/getting_started.rst
	cp $(TOP)/src/docs_contents.rst $@/contents.rst
	cp $(TOP)/src/docs_index.rst $@/index.rst
	cp $(WEB_ADMIN)/static/favicon.ico $@
	cp $(WEB_ADMIN)/static/PandA-logo-for-black-background.svg $@
	./change_theme.sh $@/conf.py $@/_static/theme_overrides.css
	sphinx-build -b html $@ $@/html
	sed -i 's|<a href="genindex.html">Index</a>||' \
	    $@/html/*.html $@/html/*/*.html

$(TEMPLATES): $(MALCOLM_BUILD) $(ANNOTYPES_BUILD) $(MALCOLMJS_BUILD)
	rm -rf $@
	mkdir -p $@
	cp $(PYMALCOLM)/malcolm/modules/web/www/index.html $@/withoutnav.html
	./add_nav.sh $@/withoutnav.html > $@/index.html

$(WEBSERVER_ZPKG): $(SOURCES) $(TEMPLATES)
	rm -f $(BUILD_DIR)/*.zpg
	$(MAKE_ZPKG) -t $(TOP) -b $(BUILD_DIR) -d $(BUILD_DIR) \
		$(TOP)/etc/panda-webcontrol.list $(GIT_VERSION)
	$(MAKE_ZPKG) -t $(TOP) -b $(BUILD_DIR) -d $(BUILD_DIR) \
		$(TOP)/etc/panda-webcontrol-no-subnet-validation.list $(GIT_VERSION)

zpkg: $(WEBSERVER_ZPKG)

# Push a github release
github-release: $(BUILD_DIR)/*.zpg
	$(MAKE_GITHUB_RELEASE) PandABlocks-webcontrol $(GIT_VERSION) $^

clean:
	rm -rf $(BUILD_DIR)

rebuild:
	make clean
	make default

.PHONY: clean zpkg rebuild github-release

print_admin_dir:
	echo $(WEB_ADMIN)/templates
