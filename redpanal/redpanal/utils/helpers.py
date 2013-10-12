import os

def get_file_extension(filename):
    return os.path.splitext(filename)[1][1:].lower()
