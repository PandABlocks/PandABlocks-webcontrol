# Top level make file for building PandA webcontrol

TOP := $(CURDIR)

# Build defaults that can be overwritten by the CONFIG file if present
ANNOTYPES = $(error Define ANNOTYPES in CONFIG file)
PYMALCOLM = $(error Define PYMALCOLM in CONFIG file)
PANDA_ROOTFS = $(error Define PANDA_ROOTFS in CONFIG file)
PANDA_ROOT = $(error Define PANDA_ROOT in CONFIG file)
MAKE_ZPKG = $(PANDA_ROOTFS)/make-zpkg
PYTHON = $(PANDA_ROOT)/targets/rootfs/toolkit/bin/python2
BUILD_DIR = $(TOP)/build

DEFAULT_TARGETS = zpkg

# The CONFIG file is required.  If not present, create by copying CONFIG.example
# and editing as appropriate.
include CONFIG

default: $(DEFAULT_TARGETS)

# This is the generated zpkg list file
ZPKG_LIST = $(TOP)/etc/panda-webcontrol.list

# The cut down malcolm package we build
MALCOLM_BUILD = $(BUILD_DIR)/malcolm
ANNOTYPES_BUILD = $(BUILD_DIR)/annotypes

# A tag for our zpkg suffix
export GIT_VERSION := $(shell git describe --abbrev=7 --dirty --always --tags)

# The zpkg file that will be built
WEBSERVER_ZPKG = $(BUILD_DIR)/panda-webcontrol@$(GIT_VERSION).zpg

# The .py files we depend on to build our cut down distribution
MALCOLM_SOURCES := $(shell find $(PYMALCOLM)/malcolm -name \*.py)
ANNOTYPES_SOURCES := $(shell find $(ANNOTYPES)/annotypes -name \*.py)

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
	cp $(PANDA_ROOTFS)/rootfs/web-admin/static/favicon.ico $@/modules/web/www
	cp $(PYMALCOLM)/malcolm/*.py $@
	find $@ -name '*.pyc' -delete
	$(PYTHON) -m compileall $@

$(ANNOTYPES_BUILD): $(ANNOTYPES_SOURCES)
	rm -rf $@
	mkdir -p $@
	cp $(ANNOTYPES)/annotypes/*.py $@
	$(PYTHON) -m compileall $@

$(TEMPLATES): $(MALCOLM_BUILD) $(ANNOTYPES_BUILD)
	rm -rf $@
	mkdir -p $@
	cp $(PYMALCOLM)/malcolm/modules/web/www/index.html $@/withoutnav.html
	./add_nav.sh $@/withoutnav.html > $@/index.html

$(WEBSERVER_ZPKG): $(ZPKG_LIST) $(SOURCES) $(TEMPLATES)
	rm -f $(BUILD_DIR)/*.zpg
	$(MAKE_ZPKG) -t $(TOP) -b $(BUILD_DIR) -d $(BUILD_DIR) $< $(GIT_VERSION)

zpkg: $(WEBSERVER_ZPKG)

clean:
	rm -rf $(BUILD_DIR)

rebuild:
	make clean
	make default

.PHONY: clean zpkg rebuild

print_admin_dir:
	echo $(PANDA_ROOTFS)/rootfs/web-admin/templates
