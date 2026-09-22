# ------------------------------------------------------------------------------
# Documentation
#
# Docs are built with MyST (mystmd), run through npx so no global install is
# needed; pin the version with MYSTMD_VERSION (see CONFIG.example).  `make docs`
# mirrors `myst build --html --strict` and `make docs-dev` mirrors `myst start`,
# matching the docs/ task runner.  MyST writes its output into docs/_build/html.
# --strict exits non-zero on any error-severity message (e.g. an unresolved
# cross-repo xref) so CI fails rather than publishing broken links.

MYST = npx --yes --package mystmd@$(MYSTMD_VERSION) myst

docs:
	cd docs && $(MYST) build --html --strict

docs-dev:
	cd docs && $(MYST) start

clean-docs:
	rm -rf $(TOP)/docs/_build

.PHONY: docs docs-dev clean-docs
