import hashlib
import os.path
import pymongo

import Image
import StringIO

import numpy as np
import oct2py

import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.web

from tornado.options import define, options
define('port', default=5897, help='run on the given port', type=int)


class Application(tornado.web.Application):

    def __init__(self):
        base_dir = os.path.dirname(__file__)
        settings = {
            'static_path': os.path.join(base_dir, 'static'),
            'template_path': os.path.join(base_dir, 'templates'),
            'default_handler_class': ErrorHandler,
            'default_handler_args': dict(status_code=404),
            'debug': True,
        }

        handlers = [
            (r'/', ListHandler),
            (r'/upload', UploadHandler),
            (r'/upload/(\w+)', PrepareHandler),
            (r'/api/add', ApiAddHandler),
            (r'/api/mix', ApiMixHandler),
        ]

        self.db = pymongo.MongoClient().facemorph
        self.db.faces.create_index('hash')

        oct2py.octave.addpath(settings['static_path'])

        tornado.web.Application.__init__(self, handlers, **settings)


class BaseHandler(tornado.web.RequestHandler):

    @property
    def db(self):
        return self.application.db

    @property
    def face_dir(self):
        return os.path.join(self.settings['static_path'], 'img', 'faces')

    def write_error(self, status_code, **kwargs):
        self.render('error.html', status_code=status_code)

    def hashify(self, text):
        return hashlib.sha256(text).hexdigest()[:12]


class ErrorHandler(tornado.web.ErrorHandler, BaseHandler):
    pass


class ListHandler(BaseHandler):

    def get(self):
        items = list(self.db.faces.find())
        self.render('list.html', items=items)


class UploadHandler(BaseHandler):

    def get(self):
        self.render('upload.html')

    def post(self):
        body = self.request.files['image'][0]['body']
        img = Image.open(StringIO.StringIO(body)).resize((300, 300))
        hash = self.hashify(img.tobytes())
        path = os.path.join(self.face_dir, '%s.png' % hash)
        img.save(path)
        self.redirect('/upload/%s' % hash)


class PrepareHandler(BaseHandler):

    def get(self, hash):
        self.render('prepare.html', hash=hash)


class ApiAddHandler(BaseHandler):

    def post(self):
        hash = self.get_argument('hash', '')
        points = tornado.escape.json_decode(self.get_argument('points', '[]'))

        if self.db.faces.find_one({'hash': hash}):
            self.write(tornado.escape.json_encode({
                'error': True,
                'error_reason': 'Hash `%s` already exists.' % hash,
            }))

        elif len(points) != 31:
            self.write(tornado.escape.json_encode({
                'error': True,
                'error_reason': 'The number of feature points is not correct.',
            }))

        else:
            self.db.faces.insert({
                'hash': hash,
                'points': points,
                'parent': None,
                'ratio': None,
            })

            self.write(tornado.escape.json_encode({
                'error': False,
                'error_reason': None,
            }))


class ApiMixHandler(BaseHandler):

    def post(self):
        hash1 = self.get_argument('hash1', '')
        hash2 = self.get_argument('hash2', '')
        if hash1 > hash2:
            hash1, hash2 = hash2, hash1
        item1 = self.db.faces.find_one({'hash': hash1})
        item2 = self.db.faces.find_one({'hash': hash2})

        if (not item1) or (not item2):
            self.write(tornado.escape.json_encode({
                'error': True,
                'error_reason': 'The given hash does not exist.',
            }))

        else:
            infile1 = os.path.join(self.face_dir, '%s.png' % hash1)
            infile2 = os.path.join(self.face_dir, '%s.png' % hash2)
            points1 = np.array(item1['points'], dtype=float)
            points2 = np.array(item2['points'], dtype=float)

            for i in xrange(1, 10):
                ratio = 0.1 * i
                hash3 = self.hashify(hash1 + hash2 + str(i))

                if not self.db.faces.find_one({'hash': hash3}):
                    outfile = os.path.join(self.face_dir, '%s.png' % hash3)
                    oct2py.octave.facemorph(infile1, infile2, outfile,
                                            points1, points2, ratio)
                    points3 = points1 + ratio * (points2 - points1)

                    self.db.faces.insert({
                        'hash': hash3,
                        'points': points3.tolist(),
                        'parent': [hash1, hash2],
                        'ratio': ratio,
                    })

            self.write(tornado.escape.json_encode({
                'error': False,
                'error_reason': None,
            }))


if __name__ == '__main__':
    options.parse_command_line()
    httpserver = tornado.httpserver.HTTPServer(Application())
    httpserver.listen(options.port)
    tornado.ioloop.IOLoop().instance().start()
