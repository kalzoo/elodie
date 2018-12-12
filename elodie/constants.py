"""
Settings used by Elodie.
"""

from os import path
from sys import version_info

#: If True, debug messages will be printed.
debug = False

#: Directory in which to store Elodie settings.
application_directory = '{}/.elodie'.format(path.expanduser('~'))

#: File in which to store details about media Elodie has seen.
hash_db = '{}/hash.json'.format(application_directory)

#: File in which to store geolocation details about media Elodie has seen.
location_db = '{}/location.json'.format(application_directory)

#: Elodie installation directory.
script_directory = path.dirname(path.dirname(path.abspath(__file__)))

#: Path to Elodie's ExifTool config file.
exiftool_config = path.join(script_directory, 'configs', 'ExifTool_config')

# How many files to read into ExifTool batch mode at once. Larger batches == faster import, more memory consumption
exiftool_batch_size = 50

#: Accepted language in responses from MapQuest
accepted_language = 'en'

# check python version, required in filesystem.py to trigger appropriate method
python_version = version_info.major
