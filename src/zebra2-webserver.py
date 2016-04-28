#!/bin/env python
from malcolm.imalcolm import IMalcolmServer
from malcolm.devices.zebra2.zebra2 import Zebra2

ims = IMalcolmServer(prefix="ws://")
ims.create_device(Zebra2, "Z", hostname="localhost", port=8888)
ims.interact()
