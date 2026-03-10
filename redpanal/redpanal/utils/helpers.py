import os

def get_file_extension(filename):
    return os.path.splitext(filename)[1][1:].lower()

def get_git_revision_short_hash():
    import subprocess
    try:
        short_hash = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                                    capture_output=True).stdout.strip().decode()
    except:
        short_hash = ""
    return short_hash

def is_ajax(request):
    return request.META.get('HTTP_X_REQUESTED_WITH') == 'XMLHttpRequest'
