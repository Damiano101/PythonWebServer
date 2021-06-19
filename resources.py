import io
import os
import json
import hashlib


# Some kind of resource with a name and a url
class ResourceData:
    def __init__(self, name):
        self.name = name
        # The sha1 of the trimmed name is used as the url
        name_bytes = "".join(name.lower().split()).encode()
        self.url = hashlib.sha1(name_bytes).hexdigest()

# An HTML page about one a hostital service
class PageData(ResourceData):
    def __init__(self, name, corridor, room, times):
        super().__init__(name)
        self.corridor = corridor
        self.room = room
        self.times = times

# A downloadable file with it's path
class FileData(ResourceData):
    def __init__(self, name, path):
        if not os.path.exists(path):
            raise IOError("'" + path + "' file not found while initializing")
        super().__init__(name)
        self.path = os.path.normpath(path)

# A uniform interface to access dinamically generated html pages and files alike.
class ResourceAccess:
    def __init__(self, name, length, stream):
        self.name = name
        self.length = length
        # The underlying resource is accessed via a stream to optimize the cases where it would be
        # very heavy to load into memory and cause the server thread to stall
        self.stream = stream

    # Access an HTML string resource
    @classmethod
    def from_html(cls, name, html):
        return cls(name, len(html), io.BytesIO(html.encode(encoding="utf-8")))

    # Access a binary file resource
    @classmethod
    def from_file(cls, name, path):
        return cls(name, os.stat(path), open(path, "rb"))


# Provides the server resources for requested html pages and files
class ResourceProvider:
    def __draw_header(self, title):
        style = """body{margin:44px;auto;max-width:650px;line-height:1.8;font-size:16px;color:#444;padding:0;10px}h1{line-height:1.5}"""
        return """<html><head><title>{0}</title><style type="text/css">{1}</style></head><body><h1>{0}</h1>""".format(title, style)

    def __draw_footer(self):
        return "</body></html>"

    def __draw_index(self, title, data):
        body = "<p>{0}</p>".format(title)
        for d in data:
            body += """<p><a href="{0}">{1}</a></p>""".format(d.url, d.name)
        return body

    def __draw_page(self, page):
        body = """<p>Corridoio {0} stanza {1}</p><table border="2"><tr><th>Dalle</th><th>Alle</th>""".format(page.corridor, page.room)
        for seg in page.times:
            body += "<tr><td>{0}</td><td>{1}</td>".format(seg[0], seg[1])
        body += "</table>"
        return body

    # Converts from a list of dictionaries to a list of tuples.
    def __times_convert(self, dict_list):
        return [(d["start"], d["end"]) for d in dict_list]

    # Builds a PageData object from a page json object.
    def __json_page_to_data(self, json):
        return PageData(json["name"], json["corridor"], json["room"], self.__times_convert(json["times"]))

    def __json_user_to_dict(self, json):
        return {pair["name"]:pair["passwd_sha"] for pair in json}

    def __init__(self, path):
        with open(path, "r") as f:
            config = json.load(f)
            self.pages = [self.__json_page_to_data(p) for p in config["pages"]]
            self.files = [FileData(f["name"], f["path"]) for f in config["files"]]

            auth_data = config["authentication"]
            self.realm = auth_data["realm"]
            self.users = self.__json_user_to_dict(auth_data["users"])


    # Generate the site's index on the fly
    def get_index(self):
        html = self.__draw_header("Servizi ospedalieri") + self.__draw_index("Servizi", self.pages) + "<br/>" + self.__draw_index("Documenti", self.files) + self.__draw_footer()
        return ResourceAccess.from_html("Ospedale", html)

    # Get the ResourceAccess to a dinamically generated HTML page
    def get_page(self, url):
        for p in self.pages:
            if p.url == url:
                return ResourceAccess.from_html(p.name, self.__draw_header(p.name) + self.__draw_page(p) + self.__draw_footer())
        return None

    # Generate a HTML error page for pages not found
    def get_error(self, url):
        return ResourceAccess.from_html("Pagina sconosciuta", self.__draw_header("'{0}' non trovato".format(url)) + self.__draw_footer())

    # Get the ResourceAccess to a file
    def get_file(self, url):
        url = os.path.normpath(url)
        for f in self.files:
            if f.url == url:
                return ResourceAccess.from_file(f.name, f.path)
        return None

    # Returns the configured authentication realm
    def get_authentication_realm(self):
        return self.realm

    # Returns True if the user is in recognized and with a valid password
    def is_user_authenticated(self, name, passwd_sha):
        if name in self.users:
            return self.users[name] == passwd_sha
        return False