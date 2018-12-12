"""
General file system methods.

.. moduleauthor:: Jaisen Mathai <jaisen@jmathai.com>
"""
from __future__ import print_function
from builtins import object

import hashlib
import os
import re
import shutil
import time

from elodie import compatability
# from elodie import geolocation
from elodie import log
# from elodie.config import load_config
from elodie.manifest import Manifest
from elodie.media.base import Base, get_all_subclasses


# For some reason, this was an instance method on Db/manifest.
# TODO: should be a utility or class method somewhere.
def checksum(file_path, blocksize=65536):
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


class FileSystem(object):
    """A class for interacting with the file system."""

    def __init__(self):
        # The default folder path is along the lines of 2015-01-Jan/Chicago
        self.default_folder_path_definition = {
            'date': '%Y-%m-%b',
            'location': '%city',
            'full_path': '%date/'
        }
        self.cached_folder_path_definition = None
        self.default_parts = ['album', 'city', 'state', 'country', 'origin']

    def create_directory(self, directory_path):
        """Create a directory if it does not already exist.

        :param str directory_name: A fully qualified path of the
            to create.
        :returns: bool
        """
        try:
            if os.path.exists(directory_path):
                return True
            else:
                os.makedirs(directory_path)
                return True
        except OSError:
            # OSError is thrown for cases like no permission
            pass

        return False

    def delete_directory_if_empty(self, directory_path):
        """Delete a directory only if it's empty.

        Instead of checking first using `len([name for name in
        os.listdir(directory_path)]) == 0`, we catch the OSError exception.

        :param str directory_name: A fully qualified path of the directory
            to delete.
        """
        try:
            os.rmdir(directory_path)
            return True
        except OSError:
            pass

        return False

    def get_all_files(self, path, extensions=None, check_extensions=False):
        """Recursively get all files which match a path and extension.

        :param str path string: Path to start recursive file listing
        :param tuple(str) extensions: File extensions to include (whitelist)
        :param check_extensions boolean: whether to check extensions or to just get files regardless
        :returns: generator
        """
        # If extensions is None then we get all supported extensions
        if not extensions:
            extensions = set()
            subclasses = get_all_subclasses(Base)
            for cls in subclasses:
                extensions.update(cls.extensions)

        for dirname, dirnames, filenames in os.walk(path):
            for filename in filenames:
                if check_extensions:
                    # If file extension is in `extensions` then append to the list
                    if os.path.splitext(filename)[1][1:].lower() in extensions:
                        yield os.path.join(dirname, filename)
                    else:
                        log.warn("Ignored extension found at {}".format(os.path.join(dirname, filename)))
                else:
                    yield os.path.join(dirname, filename)

    def get_current_directory(self):
        """Get the current working directory.

        :returns: str
        """
        return os.getcwd()

    def get_file_name(self, metadata, target_config):
        """Generate file name for a photo or video using its metadata.

        We use an ISO8601-like format for the file name prefix. Instead of
        colons as the separator for hours, minutes and seconds we use a hyphen.
        https://en.wikipedia.org/wiki/ISO_8601#General_principles

        :param media: A Photo or Video instance
        :type media: :class:`~elodie.media.photo.Photo` or
            :class:`~elodie.media.video.Video`
        :returns: str or None for non-photo or non-videos
        """
        # if(not media.is_valid()):
        #     return None
        #
        # metadata = media.get_metadata()
        if metadata is None:
            return None

        # First we check if we have metadata['original_name'].
        # We have to do this for backwards compatibility because
        #   we original did not store this back into EXIF.
        if 'original_name' in metadata and metadata['original_name']:
            base_name = os.path.splitext(metadata['original_name'])[0]
        else:
            # If the file has EXIF title we use that in the file name
            #   (i.e. my-favorite-photo-img_1234.jpg)
            # We want to remove the date prefix we add to the name.
            # This helps when re-running the program on file which were already
            #   processed.
            base_name = re.sub(
                '^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-',
                '',
                metadata['base_name']
            )
            if(len(base_name) == 0):
                base_name = metadata['base_name']

        if(
            'title' in metadata and
            metadata['title'] is not None and
            len(metadata['title']) > 0
        ):
            title_sanitized = re.sub('\W+', '-', metadata['title'].strip())
            base_name = base_name.replace('-%s' % title_sanitized, '')
            base_name = '%s-%s' % (base_name, title_sanitized)

        file_name_parts = []

        if metadata['date_taken'] is not None:
            file_name_parts.append(time.strftime('%Y-%m-%d_%H-%M-%S', metadata['date_taken']))

        if metadata["origin"] is not None:
            file_name_parts.append(metadata['origin'])
        # Alternative: the camera model could be the origin - but that would add a lot of repetitive data to the manifest
        elif metadata["camera_model"] is not None:
            file_name_parts.append(metadata['camera_model'])

        file_name_parts.append(base_name)

        return "{}.{}".format('-'.join(file_name_parts), metadata['extension']).lower()

    def get_folder_path_definition(self, pattern):
        """Returns a list of folder definitions.

        Each element in the list represents a folder.
        Fallback folders are supported and are nested lists.
        Return values take the following form.
        [
            ('date', '%Y-%m-%d'),
            [
                ('location', '%city'),
                ('album', ''),
                ('"Unknown Location", '')
            ]
        ]

        :returns: list
        """
        # If we've done this already then return it immediately without
        # incurring any extra work
        # TODO: This needs to be adapted for multiple targets
        if self.cached_folder_path_definition is not None:
            return self.cached_folder_path_definition

        # If Directory is in the config we assume full_path and its
        #  corresponding values (date, location) are also present
        # config_directory = self.default_folder_path_definition
        # if('Directory' in config):
        #     config_directory = config['Directory']

        # Find all subpatterns of full_path that map to directories.
        #  I.e. %foo/%bar => ['foo', 'bar']
        #  I.e. %foo/%bar|%example|"something" => ['foo', 'bar|example|"something"']
        path_parts = re.findall(
                         '(\%[^/]+)',
                         pattern
                     )

        if not path_parts or len(path_parts) == 0:
            raise Exception("Bad folder path definition: {}".format(pattern))
            # return self.default_folder_path_definition

        self.cached_folder_path_definition = []
        for part in path_parts:
            part = part.replace('%', '')
            # if part in config_directory:
            #     self.cached_folder_path_definition.append(
            #         [(part, config_directory[part])]
            #     )
            if part in self.default_parts:
                self.cached_folder_path_definition.append(
                    [(part, '')]
                )
            else:
                this_part = []
                for p in part.split('|'):
                    this_part.append(
                        (p, "%{}".format(p))
                    )
                self.cached_folder_path_definition.append(this_part)

        return self.cached_folder_path_definition

    def get_folder_path(self, metadata, target_config):
        """Given a media's metadata this function returns the folder path as a string.

        :param metadata dict: Metadata dictionary.
        :returns: str
        """
        path_parts = self.get_folder_path_definition(target_config["file_path_pattern"])
        path = []
        flag_undated = False
        for path_part in path_parts:
            # We support fallback values so that
            #  'album|city|"Unknown Location"
            #  %album|%city|"Unknown Location" results in
            #  My Album - when an album exists
            #  Sunnyvale - when no album exists but a city exists
            #  Unknown Location - when neither an album nor location exist
            for this_part in path_part:
                part, mask = this_part
                if part in ('date', 'day', 'month', 'year', 'Y', 'm', 'd'):
                    if metadata['date_taken'] is not None:
                        path.append(
                            time.strftime(mask, metadata['date_taken'])
                        )
                    else:
                        if not flag_undated:  # This prevents a chain of /undated/undated/undated directories
                            path.append(
                                'undated'
                            )
                        flag_undated = True
                    break
                elif part in ('album', 'camera_make', 'camera_model', 'origin'):
                    if metadata[part]:
                        path.append(metadata[part])
                        break
                elif part.startswith('"') and part.endswith('"'):
                    path.append(part[1:-1])

        return os.path.join(*path)

    def generate_manifest(self, file_path, target_config, metadata_dict, media):
        metadata = media.get_metadata(metadata_dict)
        metadata_entry = {
            "sources": {
                file_path: {}
            },
            "target": {
                "path": self.get_folder_path(metadata, target_config),
                "name": self.get_file_name(metadata, target_config)
            },
        }

        # Don't include null values (significantly reduces size of manifest)
        if metadata["date_taken"] is not None: metadata_entry["sources"][file_path]["date_taken"] = metadata["date_taken"],
        if metadata["camera_make"] is not None: metadata_entry["sources"][file_path]["camera_make"] = metadata["camera_make"]
        if metadata["camera_model"] is not None: metadata_entry["sources"][file_path]["camera_model"] = metadata["camera_model"]
        if metadata["album"] is not None: metadata_entry["sources"][file_path]["album"] = metadata["album"]
        if metadata["title"] is not None: metadata_entry["sources"][file_path]["title"] = metadata["title"]
        if metadata["origin"] is not None: metadata_entry["sources"][file_path]["origin"] = metadata["origin"]

        return metadata_entry

    # TODO: check that the file found at destination has the expected checksum
    def execute_manifest(self, source_path, manifest_entry, base_path):
        # Check if file is already present at the target.
        # If it is, return
        target_manifest = manifest_entry["target"]
        destination = os.path.join(base_path, target_manifest["path"], target_manifest["name"])
        # If there's already a file there...
        if os.path.isfile(destination):
            # Check that it's the same file. situations: a) edited but kept same name, b) corrupted
            if checksum(destination) == checksum(source_path):
                log.info("[ ] File {} already exists at {} and is intact; skipping".format(source_path, destination))
            else:
                target_name, target_ext = os.path.splitext(target_manifest["name"])
                target_name_with_hash = ''.join([target_name, '.', checksum(source_path), target_ext])
                destination_name_with_hash = os.path.join(base_path, target_manifest["path"], target_name_with_hash)
                shutil.copy(source_path, destination_name_with_hash)
                log.info("[ ] File {} already exists at {} but is corrupt or edited; copying with hash: {}".format(
                    source_path,
                    destination,
                    target_name_with_hash
                ))
            return True
        else:
            try:
                if os.path.isfile(source_path):
                    self.create_directory(os.path.join(base_path, target_manifest["path"]))
                    shutil.copy(source_path, destination)
                    log.info("[*] File {} copied to {}".format(source_path, destination))
                    return True
                else:
                    log.info("[*] File {} not found at source".format(source_path))
            except Exception as e:
                log.warn("[!] Exception copying {} to {}: {}".format(source_path, destination, e))
                return False

    def process_file(self, _file, destination, media, manifest, **kwargs):
        move = False
        if('move' in kwargs):
            move = kwargs['move']

        allow_duplicate = False
        if('allowDuplicate' in kwargs):
            allow_duplicate = kwargs['allowDuplicate']

        # This has no value for me
        # if(not media.is_valid()):
        #     print('%s is not a valid media file. Skipping...' % _file)
        #     return

        # I don't want anything touching the originals
        # media.set_original_name()
        metadata = media.get_metadata()

        directory_name = self.get_folder_path(metadata)

        dest_directory = os.path.join(destination, directory_name)
        file_name = self.get_file_name(media)
        dest_path = os.path.join(dest_directory, file_name)

        db = manifest
        checksum = db.checksum(_file)
        if(checksum is None):
            log.info('Could not get checksum for %s. Skipping...' % _file)
            return

        # If duplicates are not allowed then we check if we've seen this file
        #  before via checksum. We also check that the file exists at the
        #   location we believe it to be.
        # If we find a checksum match but the file doesn't exist where we
        #  believe it to be then we write a debug log and proceed to import.
        checksum_file = db.get_hash(checksum)
        if(allow_duplicate is False and checksum_file is not None):
            if(os.path.isfile(checksum_file)):
                log.info('%s already exists at %s. Skipping...' % (
                    _file,
                    checksum_file
                ))
                return
            else:
                log.info('%s matched checksum but file not found at %s. Importing again...' % (  # noqa
                    _file,
                    checksum_file
                ))

        # If source and destination are identical then
        #  we should not write the file. gh-210
        if(_file == dest_path):
            print('Final source and destination path should not be identical')
            return

        self.create_directory(dest_directory)

        if(move is True):
            stat = os.stat(_file)
            shutil.move(_file, dest_path)
            os.utime(dest_path, (stat.st_atime, stat.st_mtime))
        else:
            compatability._copyfile(_file, dest_path)
            self.set_utime_from_metadata(media.get_metadata(), dest_path)

        db.add_hash(checksum, dest_path)
        db.update_hash_db()

        return dest_path

    def set_utime_from_metadata(self, metadata, file_path):
        """ Set the modification time on the file based on the file name.
        """

        # Initialize date taken to what's returned from the metadata function.
        # If the folder and file name follow a time format of
        #   YYYY-MM-DD_HH-MM-SS-IMG_0001.JPG then we override the date_taken
        date_taken = metadata['date_taken']
        base_name = metadata['base_name']
        year_month_day_match = re.search(
            '^(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})',
            base_name
        )
        if(year_month_day_match is not None):
            (year, month, day, hour, minute, second) = year_month_day_match.groups()  # noqa
            date_taken = time.strptime(
                '{}-{}-{} {}:{}:{}'.format(year, month, day, hour, minute, second),  # noqa
                '%Y-%m-%d %H:%M:%S'
            )

            os.utime(file_path, (time.time(), time.mktime(date_taken)))
        else:
            # We don't make any assumptions about time zones and
            # assume local time zone.
            if date_taken is not None:
                date_taken_in_seconds = time.mktime(date_taken)
                os.utime(file_path, (time.time(), (date_taken_in_seconds)))
