"""
General file system methods.

.. moduleauthor:: Jaisen Mathai <jaisen@jmathai.com>
"""
from __future__ import print_function

from json import dumps

from elodie import constants


def debug(message):
    _print_debug(message)


def debug_json(payload):
    _print_debug(dumps(payload))


def info(message):
    _print(message)


def info_json(payload):
    _print(dumps(payload))


def progress(message='.', new_line=False):
    if not new_line:
        print(message, end="")
    else:
        print(message)


def warn(message):
    _print(message)


def warn_json(payload):
    _print(dumps(payload))


def error(message):
    _print(message)


def error_json(payload):
    _print(dumps(payload))


def _print(string):
    print(string)
    constants.log_output += string + '\n'


def _print_debug(string):
    if constants.debug is True:
        print(string)

    constants.log_output += string + '\n'


def write(path):
    try:
        with open(path, 'w') as f:
            f.write(constants.log_output)
        print("[*] Wrote log out to {}".format(path))
        return True
    except:
        print("[!] Unable to write log out to {}".format(path))
        return False