from datetime import datetime


def timestamp_string():
    return datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
