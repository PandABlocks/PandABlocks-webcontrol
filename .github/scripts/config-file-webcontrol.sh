#!/bin/bash
# Generates and populates CONFIG file for webControl repo.

cat >> PandABlocks-webcontrol/CONFIG << 'EOL'

PYMALCOLM = $(GITHUB_WORKSPACE)/pymalcolm
ANNOTYPES = $(GITHUB_WORKSPACE)/annotypes
PANDA_ROOTFS = $(GITHUB_WORKSPACE)/PandABlocks-rootfs

EOL
