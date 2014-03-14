import redpanal

def git_hash(request):
    return {'GIT_SHORT_VERSION': redpanal.VERSION}
