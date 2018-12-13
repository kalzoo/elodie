#!/usr/bin/env python

import itertools
import os
import re
import sys
import time
from datetime import datetime

import click
from send2trash import send2trash

# Verify that external dependencies are present first, so the user gets a
# more user-friendly error instead of an ImportError traceback.
from elodie.dependencies import verify_dependencies
if not verify_dependencies():
    sys.exit(1)

from elodie.config import Config
from elodie import constants
from elodie import log
from elodie.compatability import _decode
from elodie.filesystem import FileSystem
from elodie.manifest import Manifest
from elodie.media.base import Base, get_all_subclasses
from elodie.media.media import Media
from elodie.media.text import Text
from elodie.media.audio import Audio
from elodie.media.photo import Photo
from elodie.media.video import Video
from elodie.result import Result

from elodie.dependencies import get_exiftool
from elodie.external.pyexiftool import ExifTool


FILESYSTEM = FileSystem()


def import_file(file_path, config, manifest, metadata_dict, allow_duplicates=False, dryrun=False):

    """Set file metadata and move it to destination.
    """
    if not os.path.exists(file_path):
        log.warn('Could not find %s' % file_path)
        print('{"source":"%s", "error_msg":"Could not find %s"}' % \
            (file_path, file_path))
        return

    target = config["targets"][0]
    target_base_path = target["base_path"]

    # Check if the source, _file, is a child folder within destination
    #   .... this is not the right time to be checking for that. Lots of unnecessary checks
    # elif destination.startswith(os.path.abspath(os.path.dirname(_file))+os.sep):
    #     print('{"source": "%s", "destination": "%s", "error_msg": "Source cannot be in destination"}' % (_file, destination))
    #     return

    # Creates an object of the right type, using the file extension ie .jpg -> photo
    media = Media.get_class_by_file(file_path, get_all_subclasses())
    if not media:
        log.warn('Not a supported file (%s)' % file_path)
        print('{"source":"%s", "error_msg":"Not a supported file"}' % file_path)
        return

    # if album_from_folder:
    #     media.set_album_from_folder()

    checksum = manifest.checksum(file_path)

    if not allow_duplicates and checksum in manifest.entries:
        log.info("[ ] File {} already present in manifest; allow_duplicates is false; skipping".format(file_path))
        return True
    else:
        manifest_entry = FILESYSTEM.generate_manifest(file_path, target, metadata_dict, media)
        manifest.merge({checksum: manifest_entry})

    if dryrun:
        log.info("Generated manifest: {}".format(file_path))
        return manifest_entry is not None
    else:
        result = FILESYSTEM.execute_manifest(file_path, manifest_entry, target_base_path)
        # if dest_path:
        #     print('%s -> %s' % (_file, dest_path))
        # if trash:
        #     send2trash(_file)

        return result


@click.command('import')
@click.option('--source', type=click.Path(file_okay=False),
              help='Add an optional source directory to the configuration.')
@click.option('-c', '--config', 'config_path', type=click.Path(file_okay=True),
              required=True, help='Import configuration file.')
@click.option('-m', '--manifest', 'manifest_path', type=click.Path(file_okay=True),
              help='The database/manifest used to store file sync information.')
@click.option('-i', '--indent-manifest', 'indent_manifest', is_flag=True,
              help='Whether to indent the manifest for easier reading (roughly doubles file size)')
@click.option('--overwrite-manifest', 'overwrite_manifest', is_flag=True,
              help='Whether to overwrite the input manifest (not recommended for safety)')
# @click.option('--trash', default=False, is_flag=True,
#               help='After copying files, move the old files to the trash.')
@click.option('--allow-duplicates', default=False, is_flag=True,
              help='Import the file even if it\'s already been imported.')
@click.option('--dryrun', default=False, is_flag=True,
              help="Don't move files or save the manifest; just print the manifest to terminal")
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
# @click.argument('paths', nargs=-1, type=click.Path())
def _import(source, config_path, manifest_path, allow_duplicates, dryrun, debug, indent_manifest=False, overwrite_manifest=False):
    """Import files or directories by reading their EXIF and organizing them accordingly.
    """
    start_time = round(time.time())

    constants.debug = debug
    has_errors = False
    result = Result()

    # Load the configuration from the json file.
    config = Config().load_from_file(config_path)

    source = config["sources"][0]  # For now, only one.
    target = config["targets"][0]  # For now, only one target allowed...but data structure allows more

    source_file_path = source["file_path"]

    manifest = Manifest()

    if manifest_path is not None:
        manifest.load_from_file(manifest_path)

    original_manifest_key_count = len(manifest)

    # destination = _decode(destination)
    # destination = os.path.abspath(os.path.expanduser(destination))

    exiftool_addedargs = [
        # '-overwrite_original',
        u'-config',
        u'"{}"'.format(constants.exiftool_config)
    ]

    # This might not go well for huge directory scrapes. Will have to figure out how to batch it.
    # can use itertools.islice(generator, N) to get the next N entries.
    # TODO Next: (Working here): minor rewrite to use this^ to  prevent crashing on my HD

    file_generator = FILESYSTEM.get_all_files(source_file_path, None)
    source_file_count = 0

    with ExifTool(addedargs=exiftool_addedargs) as et:
        while True:
            file_batch = list(itertools.islice(file_generator, constants.exiftool_batch_size))
            if len(file_batch) == 0: break
            source_file_count += len(file_batch)
            metadata_list = et.get_metadata_batch(file_batch)
            if not metadata_list:
                raise Exception("Metadata scrape failed.")
            # Key on the filename to make for easy access,
            metadata_dict = dict((os.path.abspath(el["SourceFile"]), el) for el in metadata_list)
            for current_file in file_batch:
                # Don't import localized config files.
                if current_file.endswith("elodie.json"):  # Faster than a os.path.split
                    continue
                try:
                    result = import_file(current_file, config, manifest, metadata_dict, dryrun=dryrun, allow_duplicates=allow_duplicates)
                except Exception as e:
                    log.warn("[!] Error importing {}: {}".format(current_file, e))
                    result = False
                has_errors = has_errors or not result
        exiftool_waiting_time = et.waiting_time

    manifest.write(indent=indent_manifest, overwrite=overwrite_manifest)

    manifest_key_count = len(manifest)

    try:
        total_time = round(time.time() - start_time)
        print("Statistics:")
        print("Source: File Count {}".format(source_file_count))
        print("Manifest: New Hashes {}".format(manifest_key_count - original_manifest_key_count))
        print("Manifest: Total Hashes {}".format(manifest_key_count))
        print("Time: Total {}s".format(total_time))
        print("Time: Files/sec {}".format(round(source_file_count / total_time)))
        print("Time: Waiting on ExifTool {}s".format(round(exiftool_waiting_time)))
    except Exception as e:
        log.error("[!] Error generating statistics: {}".format(e))

    if has_errors:
        sys.exit(1)


@click.command('analyze')
@click.option('-m', '--manifest', 'manifest_path', type=click.Path(file_okay=True),
              help='The database/manifest used to store file sync information.')
def _analyze(manifest_path):
    manifest = Manifest()
    manifest.load_from_file(manifest_path)
    manifest_key_count = len(manifest)
    print("Statistics:")
    print("Manifest: Total Hashes {}".format(manifest_key_count))


@click.command('generate-db')
@click.option('--source', type=click.Path(file_okay=False),
              required=True, help='Source of your photo library.')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
def _generate_db(source, debug):
    """Regenerate the hash.json database which contains all of the sha256 signatures of media files. The hash.json file is located at ~/.elodie/.
    """
    constants.debug = debug
    result = Result()
    source = os.path.abspath(os.path.expanduser(source))

    if not os.path.isdir(source):
        log.error('Source is not a valid directory %s' % source)
        sys.exit(1)
        
    db = Manifest()
    db.backup_hash_db()
    db.reset_hash_db()

    for current_file in FILESYSTEM.get_all_files(source):
        result.append((current_file, True))
        db.add_hash(db.checksum(current_file), current_file)
        log.progress()
    
    db.update_hash_db()
    log.progress('', True)
    result.write()

@click.command('verify')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
def _verify(debug):
    constants.debug = debug
    result = Result()
    db = Manifest()
    for checksum, file_path in db.all():
        if not os.path.isfile(file_path):
            result.append((file_path, False))
            log.progress('x')
            continue

        actual_checksum = db.checksum(file_path)
        if checksum == actual_checksum:
            result.append((file_path, True))
            log.progress()
        else:
            result.append((file_path, False))
            log.progress('x')

    log.progress('', True)
    result.write()


def update_location(media, file_path, location_name):
    """Update location exif metadata of media.
    """
    location_coords = geolocation.coordinates_by_name(location_name)

    if location_coords and 'latitude' in location_coords and \
            'longitude' in location_coords:
        location_status = media.set_location(location_coords[
            'latitude'], location_coords['longitude'])
        if not location_status:
            log.error('Failed to update location')
            print(('{"source":"%s",' % file_path,
                '"error_msg":"Failed to update location"}'))
            sys.exit(1)
    return True


def update_time(media, file_path, time_string):
    """Update time exif metadata of media.
    """
    time_format = '%Y-%m-%d %H:%M:%S'
    if re.match(r'^\d{4}-\d{2}-\d{2}$', time_string):
        time_string = '%s 00:00:00' % time_string
    elif re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}\d{2}$', time_string):
        msg = ('Invalid time format. Use YYYY-mm-dd hh:ii:ss or YYYY-mm-dd')
        log.error(msg)
        print('{"source":"%s", "error_msg":"%s"}' % (file_path, msg))
        sys.exit(1)

    time = datetime.strptime(time_string, time_format)
    media.set_date_taken(time)
    return True


@click.command('update')
@click.option('--album', help='Update the image album.')
@click.option('--location', help=('Update the image location. Location '
                                  'should be the name of a place, like "Las '
                                  'Vegas, NV".'))
@click.option('--time', help=('Update the image time. Time should be in '
                              'YYYY-mm-dd hh:ii:ss or YYYY-mm-dd format.'))
@click.option('--title', help='Update the image title.')
@click.option('--debug', default=False, is_flag=True,
              help='Override the value in constants.py with True.')
@click.argument('paths', nargs=-1,
                required=True)
def _update(album, location, time, title, paths, debug):
    """Update a file's EXIF. Automatically modifies the file's location and file name accordingly.
    """
    constants.debug = debug
    has_errors = False
    result = Result()

    files = set()
    for path in paths:
        path = os.path.expanduser(path)
        if os.path.isdir(path):
            files.update(FILESYSTEM.get_all_files(path, None))
        else:
            files.add(path)

    for current_file in files:
        if not os.path.exists(current_file):
            has_errors = True
            result.append((current_file, False))
            log.warn('Could not find %s' % current_file)
            print('{"source":"%s", "error_msg":"Could not find %s"}' % \
                (current_file, current_file))
            continue

        current_file = os.path.expanduser(current_file)

        # The destination folder structure could contain any number of levels
        #  So we calculate that and traverse up the tree.
        # '/path/to/file/photo.jpg' -> '/path/to/file' ->
        #  ['path','to','file'] -> ['path','to'] -> '/path/to'
        current_directory = os.path.dirname(current_file)
        destination_depth = -1 * len(FILESYSTEM.get_folder_path_definition())
        destination = os.sep.join(
                          os.path.normpath(
                              current_directory
                          ).split(os.sep)[:destination_depth]
                      )

        media = Media.get_class_by_file(current_file, get_all_subclasses())
        if not media:
            continue

        updated = False
        if location:
            update_location(media, current_file, location)
            updated = True
        if time:
            update_time(media, current_file, time)
            updated = True
        if album:
            media.set_album(album)
            updated = True

        # Updating a title can be problematic when doing it 2+ times on a file.
        # You would end up with img_001.jpg -> img_001-first-title.jpg ->
        # img_001-first-title-second-title.jpg.
        # To resolve that we have to track the prior title (if there was one.
        # Then we massage the updated_media's metadata['base_name'] to remove
        # the old title.
        # Since FileSystem.get_file_name() relies on base_name it will properly
        #  rename the file by updating the title instead of appending it.
        remove_old_title_from_name = False
        if title:
            # We call get_metadata() to cache it before making any changes
            metadata = media.get_metadata()
            title_update_status = media.set_title(title)
            original_title = metadata['title']
            if title_update_status and original_title:
                # @TODO: We should move this to a shared method since
                # FileSystem.get_file_name() does it too.
                original_title = re.sub(r'\W+', '-', original_title.lower())
                original_base_name = metadata['base_name']
                remove_old_title_from_name = True
            updated = True

        if updated:
            updated_media = Media.get_class_by_file(current_file,
                                                    get_all_subclasses())
            # See comments above on why we have to do this when titles
            # get updated.
            if remove_old_title_from_name and len(original_title) > 0:
                updated_media.get_metadata()
                updated_media.set_metadata_basename(
                    original_base_name.replace('-%s' % original_title, ''))

            dest_path = FILESYSTEM.process_file(current_file, destination,
                updated_media, move=True, allowDuplicate=True)
            log.info(u'%s -> %s' % (current_file, dest_path))
            print('{"source":"%s", "destination":"%s"}' % (current_file,
                dest_path))
            # If the folder we moved the file out of or its parent are empty
            # we delete it.
            FILESYSTEM.delete_directory_if_empty(os.path.dirname(current_file))
            FILESYSTEM.delete_directory_if_empty(
                os.path.dirname(os.path.dirname(current_file)))
            result.append((current_file, dest_path))
            # Trip has_errors to False if it's already False or dest_path is.
            has_errors = has_errors is True or not dest_path
        else:
            has_errors = False
            result.append((current_file, False))

    result.write()
    
    if has_errors:
        sys.exit(1)


@click.group()
def main():
    pass


main.add_command(_analyze)
main.add_command(_import)
main.add_command(_update)
main.add_command(_generate_db)
main.add_command(_verify)


if __name__ == '__main__':
    main()
