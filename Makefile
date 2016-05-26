MALCOLMJS = /home/tmc43/common/malcolmjs
PYMALCOLM = /home/tmc43/common/python/malcolm
SITEPACKAGES = build/lib/python2.7/site-packages
WEBSERVER = build/share/webserver
CSS = $(WEBSERVER)/css
JS = $(WEBSERVER)/js
BIN = build/bin
ETC = build/etc

ZPKG_NAME = zebra2-webserver
VERSION := $(shell git describe --abbrev=7 --dirty --always --tags)

webserver: clean
	mkdir -p $(SITEPACKAGES) $(WEBSERVER) $(CSS) $(JS) $(BIN) $(ETC)/init.d

	# Copy server
	cp src/zebra2-webserver.py $(BIN)
	cp -rf $(PYMALCOLM)/malcolm/wstransport/static/icons $(WEBSERVER)
	cp -rf $(PYMALCOLM)/prefix/lib/python2.7/site-packages/malcolm*/malcolm $(SITEPACKAGES)

	# Copy client
	cp src/index.html $(WEBSERVER)
	cp -rf $(MALCOLMJS)/bundle.js $(JS)
	cp -rf $(MALCOLMJS)/js/theGraphDiamondCustomEvents.js $(JS)
	cp -rf $(MALCOLMJS)/js/views/dropdownMenuLessStylesheet $(CSS)/dropdownMenuLessStylesheet.css
	cp -rf $(MALCOLMJS)/index.css $(CSS)
	cp -rf font-awesome-4.6.1 $(WEBSERVER)
	cp -rf $(MALCOLMJS)/js/views/treeview.css $(CSS)
	cp -rf $(MALCOLMJS)/js/views/toggleButton.css $(CSS)
	cp -rf $(MALCOLMJS)/node_modules/less/dist/less.js $(JS)

	# Copy startup script
	cp src/zebra2-webserver $(ETC)/init.d
	mkdir -p $(ETC)/rc.d
	ln -s ../init.d/zebra2-webserver $(ETC)/rc.d/S400zebra2-webserver
	ln -s ../init.d/zebra2-webserver $(ETC)/rc.d/K100zebra2-webserver

	# Tar the result up
	tar czf $(ZPKG_NAME)@$(VERSION).zpg -C build .



clean:
	rm -rf build *.zpg
