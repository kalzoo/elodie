"""
Methods for interacting with information Elodie caches about stored media.
"""
from builtins import map
from builtins import object

import collections
from datetime import datetime
import hashlib
import json
import os
import time

from math import radians, cos, sqrt
from shutil import copyfile
from time import strftime

from elodie import constants


# https://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth
def deep_merge(d, u):
    if d is None: return u
    for k, v in u.items():
        if isinstance(d, collections.Mapping):
            if isinstance(v, collections.Mapping):
                r = deep_merge(d.get(k, {}), v)
                d[k] = r
            else:
                d[k] = u[k]
        else:
            d = {k: u[k]}
    return d


class Manifest(object):

    """A class for interacting with the JSON files created by Elodie."""

    def __init__(self):
        self.entries = {}
        self.file_path = os.path.join(os.getcwd(), 'manifest.json')

    def load_from_file(self, file_path):
        self.file_path = file_path  # To allow re-saving afterwards

        if not os.path.isfile(file_path):
            print("Specified manifest file does not exist, creating")
            with open(file_path, 'a') as f:
                json.dump({}, f)
                os.utime(file_path, None)

        with open(file_path, 'r') as f:
            self.entries = json.load(f)

    def merge(self, manifest_entry):
        self.entries = deep_merge(self.entries, manifest_entry)

    # TODO: Cut out any date that's already there
    def write(self, indent=False, overwrite=False):
        file_path, file_name = os.path.split(self.file_path)
        file_path, file_name = os.path.split(self.file_path)
        name, ext = os.path.splitext(file_name)

        if overwrite and self.file_path is not None:
            write_path = self.file_path
        else:
            write_name = "{}{}".format('_'.join([name, datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')]), ext)
            write_path = os.path.join(file_path, write_name)
        print("Writing manifest to {}".format(write_path))
        with open(write_path, 'w') as f:
            if indent:
                json.dump(self.entries, f, indent=2, separators=(',', ': '))
            else:
                json.dump(self.entries, f, separators=(',', ':'))
        print("Manifest written.")

    def __len__(self):
        return len(self.entries)

    def add_hash(self, key, value, write=False):
        """Add a hash to the hash db.

        :param str key:
        :param str value:
        :param bool write: If true, write the hash db to disk.
        """
        self.hash_db[key] = value
        if(write is True):
            self.update_hash_db()

    def backup_hash_db(self):
        """Backs up the hash db."""
        if os.path.isfile(constants.hash_db):
            mask = strftime('%Y-%m-%d_%H-%M-%S')
            backup_file_name = '%s-%s' % (constants.hash_db, mask)
            copyfile(constants.hash_db, backup_file_name)
            return backup_file_name

    def check_hash(self, key):
        """Check whether a hash is present for the given key.

        :param str key:
        :returns: bool
        """
        return key in self.hash_db

    def checksum(self, file_path, blocksize=65536):
        """Create a hash value for the given file.

        See http://stackoverflow.com/a/3431835/1318758.

        :param str file_path: Path to the file to create a hash for.
        :param int blocksize: Read blocks of this size from the file when
            creating the hash.
        :returns: str or None
        """
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            buf = f.read(blocksize)

            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(blocksize)
            return hasher.hexdigest()
        return None

    def get_hash(self, key):
        """Get the hash value for a given key.

        :param str key:
        :returns: str or None
        """
        if(self.check_hash(key) is True):
            return self.hash_db[key]
        return None

    def all(self):
        """Generator to get all entries from self.hash_db

        :returns tuple(string)
        """
        for checksum, path in self.hash_db.items():
            yield (checksum, path)

    def reset_hash_db(self):
        self.hash_db = {}

    def update_hash_db(self):
        """Write the hash db to disk."""
        with open(constants.hash_db, 'w') as f:
            json.dump(self.hash_db, f)

    def update_location_db(self):
        """Write the location db to disk."""
        with open(constants.location_db, 'w') as f:
            json.dump(self.location_db, f)
