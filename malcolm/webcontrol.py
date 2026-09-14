#!/usr/bin/env python
import logging.handlers
import code
import argparse
import os

from tornado.web import RequestHandler
from tornado.template import Loader

# Import the right things
from malcolm.core import Process, Part, Hook
from malcolm.profiler import Profiler
from malcolm.modules import builtin, pandablocks, web


DEFAULT_TEMPLATE_DIR = web.parts.www_dir
DEFAULT_TEMPLATE_DESIGNS_DIR = os.path.join(web.parts.www_dir,
                                            "template_designs")


def parse_args():
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
        "--configdir", default="/opt/share/designs",
        help="Config directory to save and load designs")
    parser.add_argument(
        "--templatedesigns", default=DEFAULT_TEMPLATE_DESIGNS_DIR,
        help="Directory to get template designs for tutorials")
    parser.add_argument(
        "--templatedir", default=DEFAULT_TEMPLATE_DIR,
        help="Directory to get templated html files from")
    parser.add_argument(
        "--optionsdir", default="/opt/share/panda-webcontrol/options",
        help="Directory of options that can optionally be installed like"
             "no-subnet-check")
    parser.add_argument(
        "--admindir", default="/usr/share/web-admin/templates",
        help="Directory to get web-admin templates like nav.template from")
    parser.add_argument(
        "--etcdir", default="/opt/etc/www",
        help="Directory to get nav elements from")
    parser.add_argument(
        "--mri", default="PANDA",
        help="MRI of the base PandA Block that the webserver hosts")
    parser.add_argument(
        "--no-nav", action="store_true",
        help="Whether to disable the bottom nav bar")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO)

    class TemplateHandler(RequestHandler):
        etc_loader = Loader(args.etcdir)
        admin_loader = Loader(args.admindir)

        def initialize(self, path=None):
            # GuiServerPart passes this in, so handle it
            pass

        def get_template_path(self):
            # Return the directory we put our templated index.html in
            return args.templatedir

        def get(self, path):
            if path == "details" or args.no_nav:
                # /details/... shouldn't have bottom nav
                self.render("index.html")
            else:
                # /gui/... should have index.html, templated with nav
                self.render("index-nav.html", etc_loader=self.etc_loader,
                            admin_loader=self.admin_loader)


    class TemplatedGuiPart(web.parts.GuiServerPart):
        # Override the things that returns the GUI html to use
        # a templated version
        GuiHandler = TemplateHandler


    # Check the options
    if os.path.exists(args.optionsdir):
        options = sorted(os.listdir(args.optionsdir))
    else:
        options = []

    # Make a profiler
    profiler = Profiler()

    # Make the top level process
    process = Process("Process")

    # Add the websocket server
    controller = web.controllers.HTTPServerComms(port=args.wsport, mri="WS")
    controller.add_part(web.parts.WebsocketServerPart(
        subnet_validation="no-subnet-validation" not in options
    ))
    controller.add_part(TemplatedGuiPart())
    process.add_controller(controller)

    # Add the PandABox
    controller = pandablocks.controllers.PandAManagerController(
        config_dir=args.configdir, hostname=args.hostname,
        template_designs=args.templatedesigns, port=args.port, mri=args.mri,
        doc_url_base="/fpga_docs/", poll_period=0.1)
    process.add_controller(controller)

    # Start the server
    process.start()

    # Check if we are running under systemd and can't run interactively
    if 'INVOCATION_ID' in os.environ:
        import cothread
        cothread.WaitForQuit()
    else:
        header = "Welcome to PandA web control"
        code.interact(header, local=locals())

    # Do an orderly shutdown
    process.stop(timeout=1)


if __name__ == '__main__':
    main()
