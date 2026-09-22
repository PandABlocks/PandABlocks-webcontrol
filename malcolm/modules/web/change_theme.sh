#!/usr/bin/env bash

# Remove multiple lines to be changed. They are then replaced within the following command
sed -e "/if not on_rtd:.*/{n;N;N;N;N;N;d}" -i $1

sed -e "s|html_logo = .*|html_logo = 'PandA-logo-for-black-background.svg'|" \
    -e "s|html_favicon = .*|html_favicon = 'favicon.ico'|" \
    -e "s|project = .*|project = 'PandABlocks-webcontrol'|" \
    -e "s|if not on_rtd:.*|try:\n    import sphinx_rtd_theme\n    html_theme = 'sphinx_rtd_theme'\nexcept ImportError:\n    html_theme = 'default'\n    print('sphinx_rtd_theme not found, using default')|"\
    -i $1

cat << EOF > $2
/* override top left pane to be black */
.wy-side-nav-search {
  background-color: black;
  }
EOF
