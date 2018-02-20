import logging.handlers
import code
import argparse

from tornado.web import RequestHandler
from tornado.template import Loader

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    "--hostname", default="localhost",
    help="Hostname of the PandA TCP server to connect to")
parser.add_argument(
    "--port", default=8888, type=int,
    help="Port of the PandA TCP server to connect to")
parser.add_argument(
    "--wsport", default=8008, type=int,
    help="Websocket port to run the webserver on")
parser.add_argument(
    "--configdir", default="/opt/share/panda-webcontrol/designs",
    help="Config directory to save and load designs")
parser.add_argument(
    "--templatedir", default="/opt/share/panda-webcontrol/templates",
    help="Directory to get templated html files from")
parser.add_argument(
    "--admindir", default="/usr/share/web-admin/templates",
    help="Directory to get web-admin templates like nav.template from")
parser.add_argument(
    "--etcdir", default="/opt/etc/www",
    help="Directory to get nav elements from")
parser.add_argument(
    "--mri", default="PANDABOX",
    help="MRI of the base PandA Block that the webserver hosts")
parser.add_argument(
    "--logfile", default="",
    help="Log file that will be logged to, if not present then stdout")
args = parser.parse_args()

if args.logfile:
    # Create an extended formatted logger and log to file
    extended_formatter = logging.Formatter(
        """%(asctime)s - %(levelname)6s - %(name)s
    %(message)s""")
    file_handler = logging.handlers.RotatingFileHandler(
            args.logfile, maxBytes=1000000, backupCount=4)
    file_handler.setFormatter(extended_formatter)
    file_handler.setLevel(logging.INFO)
    # Attach it to the root logger
    logging.root.addHandler(file_handler)
    logging.root.setLevel(logging.INFO)
else:
    logging.basicConfig(level=logging.INFO)

logging.info("Importing malcolm")

# Import the right things
from malcolm.core import Process, Part, Hook
from malcolm.modules import builtin, pandablocks, web


# Make a template handler
class TemplateHandler(RequestHandler):
    etc_loader = Loader(args.etcdir)
    admin_loader = Loader(args.admindir)

    def get_template_path(self):
        return args.templatedir

    def get(self, path):
        if not path:
            path = "index.html"
        self.render(path, etc_loader=self.etc_loader,
                    admin_loader=self.admin_loader)


class TemplateHandlerPart(Part):
    def on_hook(self, hook):
        # type: (Hook) -> None
        if isinstance(hook, web.hooks.ReportHandlersHook):
            hook(self.report_handlers)

    def report_handlers(self):
        return [web.infos.HandlerInfo(r"/(|.*\.html)", TemplateHandler)]


# Make the top level process
process = Process("Process")

# Add the websocket server
controller = web.controllers.HTTPServerComms(port=args.wsport, mri="WS")
controller.add_part(web.parts.WebsocketServerPart())
controller.add_part(TemplateHandlerPart(name="TEMPLATES"))
controller.add_part(web.parts.FileServerPart())
process.add_controller(controller)

# Add the PandABox
controller = pandablocks.controllers.PandABlocksManagerController(
    config_dir=args.configdir, hostname=args.hostname,
    port=args.port, mri=args.mri, use_git=False)
controller.add_part(builtin.parts.TitlePart(value="PandABox"))
process.add_controller(controller)

# Start the server
process.start()

# Wait for completion
header = "Welcome to PandA"
code.interact(header, local=locals())

# If we stop with CTRL-D then do an orderly shutdown
process.stop(timeout=1)
