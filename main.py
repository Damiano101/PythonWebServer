#!/usr/bin/env python
import sys
import base64
import hashlib
from pathlib import Path
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from resources import ResourceProvider


# Defines the GET request handle
class RequestHandler(BaseHTTPRequestHandler):
    # The server resource shared by the handles
    resources = None

    def __path_is_index(self, path):
        return path == "/" or path == "/index.html" or path == "/index.htm"

    def __try_get_html(self, page):
        path = self.path.lower()
        if self.__path_is_index(path):
            index = RequestHandler.resources.get_index()
            return (200, index, "text/html", "inline")
        else:
            page = RequestHandler.resources.get_page(path[1:])
            if page:
                return (200, page, "text/html", "inline")
            else:
                return None

    def __try_get_file(self, path):
        file = RequestHandler.resources.get_file("." + path)
        if file:
            return (200, file, "application/octet-stream", "attachment")
        else:
            return None

    def __get_not_found(self, path):
        err = RequestHandler.resources.get_error(path)
        return (404, err, "text/html", "inline")

    # Dispatch the given url to the appropiate resource, if any
    def __dispatch(self, path):
        html = self.__try_get_html(path)
        if html:
            return html
        else:
            # Try interpreting the path as a file path
            file = self.__try_get_file(path)
            if file:
                return file
            else:
                return self.__get_not_found(path)

    def __client_is_authenticated(self):
        if "Authorization" in self.headers:
            encoded_cred = str(self.headers["Authorization"]).split()[1]
            credentials = str(base64.b64decode(encoded_cred), encoding="utf-8").split(":")

            name = credentials[0]
            passwd_sha = hashlib.sha256(credentials[1].encode("utf-8")).hexdigest()

            return RequestHandler.resources.is_user_authenticated(name, passwd_sha)
        return False

    def __request_authentication(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", "Basic realm=\"" + RequestHandler.resources.get_authentication_realm() + "\"")
        self.end_headers()

    def __handle_GET(self):
        # The http return code, resource access object, resoruce type and how should the browser
        # handle the view
        (code, resource, content_type, disposition) = self.__dispatch(self.path)

        self.send_response(code)
        # Set if the response if a binary file or text
        self.send_header("Content-type", content_type)
        # Set how long the response content will be
        self.send_header("Content-length", resource.length)
        # Set the suggested name
        self.send_header("Content-Disposition", disposition + "; filename=\"" + resource.name + "\"")
        self.end_headers()

        self.wfile.write(resource.stream.read())
        resource.stream.close()

    def do_GET(self):
        if self.__client_is_authenticated():
            self.__handle_GET()
        else:
            self.__request_authentication()


# Initialize a server at the given port with the given config
def get_server(port, config_path):
    RequestHandler.resources = ResourceProvider(config_path)

    server = ThreadingHTTPServer(("", port), RequestHandler)
    # Wait for all connections to close before exiting.
    server.daemon_threads = False
    server.allow_reuse_address = True
    return server

# Get the command line arguments parser
def get_parser():
    parser = ArgumentParser(description="Run a simple http server.")
    parser.add_argument("-p", "--port", type=int, help="Set the server port. Defaults to 8081", default=8081)
    parser.add_argument("-c", "--config", type=Path, help="Path to the configuration file. Defaults to './config.json'", default="./config.json")
    return parser


args = get_parser().parse_args()

# Serves until a keyboard interrupt is raised, then closes the server.
print("Starting server at port " + str(args.port))
server = get_server(args.port, args.config)
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("Keyboard interrupt, shutting down the server")
finally:
    server.server_close()

