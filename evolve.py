import hashlib
import os.path
import pymongo

import numpy as np
import oct2py


db = pymongo.MongoClient().facemorph
base_dir = os.path.dirname(__file__)
face_dir = os.path.join(base_dir, 'static', 'img', 'faces')
oct2py.octave.addpath(os.path.join(base_dir, 'static'))


def get_random_face():
    n_faces = db.faces.count()
    index = int(np.random.random() * n_faces)
    face = db.faces.find().skip(index)
    return face[0]


def get_random_ratio():
    ratio = int(np.random.random() * 9) * 0.1 + 0.1
    return ratio


def hashify(text):
    return hashlib.sha256(text).hexdigest()[:12]


def mix(face1, face2, ratio):
    hash1 = face1['hash']
    hash2 = face2['hash']
    assert(hash1 != hash2)
    index = str(int(ratio * 10))
    hash3 = hashify(min(hash1, hash2) + max(hash1, hash2) + index)

    if not db.faces.find_one({'hash': hash3}):
        infile1 = os.path.join(face_dir, '%s.png' % hash1)
        infile2 = os.path.join(face_dir, '%s.png' % hash2)
        outfile = os.path.join(face_dir, '%s.png' % hash3)
        pts1 = np.array(face1['points'], dtype=float)
        pts2 = np.array(face2['points'], dtype=float)
        pts3 = pts1 + ratio * (pts2 - pts1)
        oct2py.octave.facemorph(infile1, infile2, outfile, pts1, pts2, ratio)
        db.faces.insert({
            'hash': hash3,
            'points': pts3.tolist(),
            'parent': [hash1, hash2],
            'ratio': ratio,
        })


def evolve(n_steps=100):
    for step in xrange(n_steps):
        print('step: %d' % step)
        face1 = get_random_face()
        face2 = get_random_face()
        ratio = get_random_ratio()
        if face1['hash'] != face2['hash']:
            mix(face1, face2, ratio)


if __name__ == '__main__':
    evolve()
