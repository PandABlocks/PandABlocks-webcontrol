#!/bin/env python
import json
import sys

s = json.dumps(dict(
    version=sys.argv[1],
    title="PandA Web Control",
    footerHeight=45), indent=2)

print s

