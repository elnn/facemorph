#!/usr/bin/env python
import hashlib
import Image
import numpy
import oct2py
import os.path
import pymongo
import StringIO
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web

tornado.options.define("port", default=5897, help="run on the given port", type=int)


class Application(tornado.web.Application):
    def __init__(self):
        settings = {
            "cookie_secret": "younhaholic",
            "static_path": os.path.join(os.path.dirname(__file__), "static"),
            "template_path": os.path.join(os.path.dirname(__file__), "templates"),
        }
        handlers = [
            (r"/", MainHandler),
            (r"/view/(.*)", ViewHandler),
            (r"/list", ListHandler),
            (r"/upload", UploadHandler),
            (r"/prepare/(.*)", PrepareHandler),
            (r"/mix", MixHandler),
        ]
        tornado.web.ErrorHandler = ErrorHandler
        tornado.web.Application.__init__(self, handlers, **settings)
        self.mongo = pymongo.Connection().elnn


class BaseHandler(tornado.web.RequestHandler):
    @property
    def db(self):
        return self.application.mongo

    def get_error_html(self, status_code, **kwargs):
        return self.render_string("error.html", status_code=status_code)


class ErrorHandler(BaseHandler):
    def __init__(self, application, request, status_code):
        tornado.web.RequestHandler.__init__(self, application, request)
        self.set_status(status_code)

    def prepare(self):
        raise tornado.web.HTTPError(self._status_code)


class MainHandler(BaseHandler):
    @tornado.web.addslash
    def get(self):
        self.redirect("/list")


class ViewHandler(BaseHandler):
    def get(self, hash):
        item = self.db.faces.find_one({"hash": hash})
        if not item:
            raise tornado.web.HTTPError(404)
        else:
            self.render("view.html", item=item)


class ListHandler(BaseHandler):
    def get(self):
        items = self.db.faces.find()
        self.render("list.html", items=items)


class UploadHandler(BaseHandler):
    def get(self):
        self.render("upload.html")

    def post(self):
        body = self.request.files["image"][0]["body"]
        img = Image.open(StringIO.StringIO(body)).resize((400, 400))
        hash = hashlib.md5(body).hexdigest()[:8]
        path = os.path.join(self.settings["static_path"], "faces", "%s.jpg" % hash)
        img.save(path)
        self.redirect("/prepare/%s" % hash)


class PrepareHandler(BaseHandler):
    def get(self, hash):
        if self.db.faces.find_one({"hash": hash}):
            self.redirect("/view/%s" % hash)
        else:
            self.render("prepare.html", hash=hash)

    def post(self, hash):
        if not self.db.faces.find_one({"hash": hash}):
            points = tornado.escape.json_decode(self.get_argument("points"))
            self.db.faces.insert({"hash": hash,
                                  "points": points,
                                  "parent": None})
        self.redirect("/view/%s" % hash)


class MixHandler(BaseHandler):
    def post(self):
        hash1 = self.get_argument("hash1")
        hash2 = self.get_argument("hash2")
        if hash1 > hash2:
            hash1, hash2 = hash2, hash1
        hash = hashlib.md5(hash1 + hash2).hexdigest()[:8]
        if not self.db.faces.find_one({"hash": hash}):
            item1 = self.db.faces.find_one({"hash": hash1})
            item2 = self.db.faces.find_one({"hash": hash2})
            if (not item1) or (not item2):
                raise tornado.web.HTTPError(404)
            infile1 = os.path.join(self.settings["static_path"], "faces", "%s.jpg" % hash1)
            infile2 = os.path.join(self.settings["static_path"], "faces", "%s.jpg" % hash2)
            outfile = os.path.join(self.settings["static_path"], "faces", "%s.jpg" % hash)
            points1 = numpy.array(item1["points"], dtype=float)
            points2 = numpy.array(item2["points"], dtype=float)
            ratio = 0.5
            oct2py.octave.call('facemorph', infile1, infile2, outfile, points1, points2, ratio)
            p = points1 + ratio * (points2 - points1)
            self.db.faces.insert({"hash": hash,
                                  "points": p.tolist(),
                                  "parent": [hash1, hash2]})
        self.redirect("/view/%s" % hash)


def main():
    tornado.options.parse_command_line()
    httpserver = tornado.httpserver.HTTPServer(Application())
    httpserver.listen(tornado.options.options.port)
    tornado.ioloop.IOLoop().instance().start()

if __name__ == "__main__":
    main()
