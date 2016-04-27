MALCOLMJS = /home/tmc43/common/malcolmjs
PYMALCOLM = /home/tmc43/common/python/malcolm
SITEPACKAGES = build/lib/python2.7/site-packages
STATIC = build/webserver/static
CSS = $(STATIC)/css
JS = $(STATIC)/js

webserver: clean
	mkdir -p $(SITEPACKAGES)
	mkdir -p $(STATIC)
	mkdir -p $(CSS)
	mkdir -p $(JS)

	# Copy server
	cp src/zebra2-webserver.py build/webserver
	cp -rf $(PYMALCOLM)/malcolm/wstransport/static/icons $(STATIC)
	cp -rf $(PYMALCOLM)/prefix/lib/python2.7/site-packages/malcolm*/malcolm $(SITEPACKAGES)

	# Copy client
	cp src/index.html $(STATIC)
	cp -rf $(MALCOLMJS)/bundle.js $(JS)
	cp -rf $(MALCOLMJS)/js/theGraphDiamondCustomEvents.js $(JS)
	cp -rf $(MALCOLMJS)/dropdownMenuLessStylesheet $(CSS)/dropdownMenuLessStylesheet.css
	cp -rf $(MALCOLMJS)/index.css $(CSS)
	cp -rf font-awesome-4.6.1 $(STATIC)
	cp -rf $(MALCOLMJS)/js/views/treeview.css $(CSS)
	cp -rf $(MALCOLMJS)/js/views/toggleButton.css $(CSS)
	cp -rf $(MALCOLMJS)/node_modules/less/dist/less.js $(JS)



clean:
	rm -rf build
