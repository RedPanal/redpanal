"""
Starter fabfile for deploying a Django project.

Designed for Webfaction, but should work on any similar hosting system.

Change all the things marked CHANGEME. Other things can be left at their
defaults if you are happy with the default layout.
"""

import posixpath

from fabric.api import run, local, abort, env, put, settings, cd, task, sudo
from fabric.decorators import runs_once
from fabric.contrib.files import exists
from fabric.context_managers import cd, lcd, settings, hide

# CHANGEME:

USER = 'sanpiccinini'
HOST = 'panal.codigosur.com'
APP_NAME = 'redpanal'
REPOSITORY = "ssh://git@github.com:RedPanal/redpanal.git"

# Host and login username:
env.hosts = ['%s@%s' % (USER, HOST)]

# Directory where everything to do with this app will be stored on the server.
DJANGO_APP_ROOT = '/var/www/%s' % APP_NAME

# Directory where static sources should be collected.  This must equal the value
# of STATIC_ROOT in the settings.py that is used on the server.
STATIC_ROOT = '/var/www/%s/static/' % APP_NAME

# Subdirectory of DJANGO_APP_ROOT in which project sources will be stored
SRC_SUBDIR = 'src'

MANAGEPY_SUBDIR = '%s/%s/%s' % (DJANGO_APP_ROOT, SRC_SUBDIR, APP_NAME)

# Subdirectory of DJANGO_APP_ROOT in which virtualenv will be stored
VENV_SUBDIR = 'venv'

# Python version
PYTHON_BIN = "python2.7"
PYTHON_PREFIX = "" # e.g. /usr/local  Use "" for automatic


SRC_DIR = posixpath.join(DJANGO_APP_ROOT, SRC_SUBDIR)
VENV_DIR = posixpath.join(DJANGO_APP_ROOT, VENV_SUBDIR)

WSGI_MODULE = '%s.wsgi' % APP_NAME


def virtualenv(venv_dir):
    """
    Context manager that establishes a virtualenv to use.
    """
    return settings(venv=venv_dir)


def run_venv(command, **kwargs):
    """
    Runs a command in a virtualenv (which has been specified using
    the virtualenv context manager
    """
    run("source %s/bin/activate" % env.venv + " && " + command, **kwargs)


def install_dependencies():
    ensure_virtualenv()
    with virtualenv(VENV_DIR):
        with cd(SRC_DIR):
            run_venv("pip install -r requirements.txt")


def ensure_virtualenv():
    if exists(VENV_DIR):
        return

    with cd(DJANGO_APP_ROOT):
        run("virtualenv --no-site-packages --python=%s %s" %
            (PYTHON_BIN, VENV_SUBDIR))
        run("echo %s > %s/lib/%s/site-packages/projectsource.pth" %
            (SRC_DIR, VENV_SUBDIR, PYTHON_BIN))


def ensure_src_dir():
    if not exists(SRC_DIR):
        run("mkdir -p %s" % SRC_DIR)
    with cd(SRC_DIR):
        if not exists(posixpath.join(SRC_DIR, '.git')):
            run("git init")


@task
def push_rev(rev):
    """
    Use the specified revision for deployment, instead of the current revision.
    """
    env.push_rev = rev


def push_sources():
    """
    Push source code to server.
    """
    ensure_src_dir()
    push_rev = getattr(env, 'push_rev', None)
    if push_rev is None:
        push_rev = local("git rev-parse HEAD", capture=True).strip()

    local("git push ssh://%(user)s@%(host)s/%(path)s || true" %
          dict(host=env.host,
               user=env.user,
               path=SRC_DIR,
               ))
    with cd(SRC_DIR):
        run("git checkout %s" % push_rev)


@task
def webserver_stop():
    """
    Stop the webserver that is running the Django instance
    """
    sudo("/etc/init.d/uwsgi stop")

@task
def webserver_start():
    """
    Starts the webserver that is running the Django instance
    """
    sudo("/etc/init.d/uwsgi start")



@task
def webserver_restart():
    """
    Restarts the webserver that is running the Django instance
    """
    try:
        sudo("/etc/init.d/uwsgi restart")
    except:
        webserver_start()


def build_static():
    if not exists(STATIC_ROOT):
        run("mkdir -p %s" % STATIC_ROOT)
    with virtualenv(VENV_DIR):
        with cd(MANAGEPY_SUBDIR):
            run_venv("%s manage.py collectstatic --settings=redpanal.production_settings -v 1 --clear --link" % PYTHON_BIN)

    run("chmod -R ugo+r %s" % STATIC_ROOT)


@task
def first_deployment_mode():
    """
    Use before first deployment to switch on fake south migrations.
    """
    env.initial_deploy = True


def update_database():
    with virtualenv(VENV_DIR):
        with cd(MANAGEPY_SUBDIR):
            managepy = "%s manage.py " % PYTHON_BIN
            if getattr(env, 'initial_deploy', False):
                run_venv(managepy + "syncdb --all --settings=redpanal.production_settings")
                run_venv(managepy + "migrate --fake --noinput --settings=redpanal.production_settings")
            else:
                run_venv(managepy + "syncdb --noinput --settings=redpanal.production_settings")
                run_venv(managepy + "migrate --noinput --settings=redpanal.production_settings")


@task
def deploy():
    """
    Deploy project.
    """
    with settings(warn_only=True):
        webserver_stop()
    push_sources()
    install_dependencies()
    update_database()
    build_static()

    webserver_start()

