#!/usr/bin/env bash
sed -e "s|html_logo = .*|html_logo = 'PandA-logo-for-black-background.svg'|" \
    -e "s|html_favicon = .*|html_favicon = 'favicon.ico'|" \
    -e "s|project = .*|project = 'PandABlocks-webcontrol'|" \
    -i $1

cat << EOF > $2
/* override top left pane to be black */
.wy-side-nav-search {
  background-color: black;
  }
EOF
