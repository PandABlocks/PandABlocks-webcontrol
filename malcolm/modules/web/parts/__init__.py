# Expose a nice namespace
from malcolm.core import submodule_all

from .guiserverpart import GuiServerPart, www_dir
from .websocketserverpart import WebsocketServerPart

__all__ = submodule_all(globals())
