import os

def get_file_extension(filename):
    return os.path.splitext(filename)[1][1:].lower()

def get_git_revision_short_hash():
    import subprocess
    try:
        out = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).strip()
    except:
        out = ""
    return out
