#!/usr/bin/env bash
template='{% raw admin_loader.load("nav.html").generate(active="panda-webcontrol", etc_loader=etc_loader, request=request) %}'

sed -e "s|</body>|$template</body>|" \
    -e 's|data-nav-height="0"|data-nav-height="45px"|' $1
