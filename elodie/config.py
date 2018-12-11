import json
import os


class Config:

    def __init__(self):
        self.fields = {}

    def load_from_file(self, path):
        if not os.path.isfile(path):
            raise Exception("Configuration file does not exist!")
        _, extension = os.path.splitext(path)
        if extension != ".json":
            raise Exception("Configuration file must be JSON. Got: {}".format(extension))

        with open(path, 'r') as f:
            self.fields = json.load(f)

        return self.fields



