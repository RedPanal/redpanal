"""
Starter fabfile for deploying a Django project.

Designed for Webfaction, but should work on any similar hosting system.

Change all the things marked CHANGEME. Other things can be left at their
defaults if you are happy with the default layout.
"""

import posixpath
import datetime

from fabric import Connection

# CHANGEME:

USER = 'sanpiccinini'
HOST = 'redpanal.org'
APP_NAME = 'redpanal'
REPOSITORY = "ssh://git@github.com:RedPanal/redpanal.git"

PORT = 22232

# Directory where everything to do with this app will be stored on the server.
DJANGO_APP_ROOT = '/var/www/%s' % APP_NAME

# Directory where static sources should be collected.  This must equal the value
# of STATIC_ROOT in the settings.py that is used on the server.
STATIC_ROOT = '/var/www/%s/static/' % APP_NAME

# Subdirectory of DJANGO_APP_ROOT in which project sources will be stored
SRC_SUBDIR = 'src'

MANAGEPY_SUBDIR = '%s/%s/%s' % (DJANGO_APP_ROOT, SRC_SUBDIR, APP_NAME)

# Subdirectory of DJANGO_APP_ROOT in which virtualenv will be stored
VENV_SUBDIR = 'venv3'

# Python version
PYTHON_BIN = "python3.7"
PYTHON_PREFIX = "" # e.g. /usr/local  Use "" for automatic


SRC_DIR = posixpath.join(DJANGO_APP_ROOT, SRC_SUBDIR)
VENV_DIR = posixpath.join(DJANGO_APP_ROOT, VENV_SUBDIR)

WSGI_MODULE = '%s.wsgi' % APP_NAME

env = {}

def dir_exists(c, path):
    return c.run(f"test -d {path}", warn=True).ok == True

def test(c):
    c.run("uname -a")

def run_venv(c, command, **kwargs):
    """
    Runs a command in a virtualenv (which has been specified using
    the virtualenv context manager
    """
    c.run("source %s/bin/activate" % VENV_DIR + " && " + command, **kwargs)


def install_dependencies(c):
    ensure_virtualenv(c)
    run_venv(c, f"cd {SRC_DIR} && pip install -r requirements.txt")

def ensure_virtualenv(c):
    if dir_exists(c, VENV_DIR):
        return

    c.run(f"cd {DJANGO_APP_ROOT} && virtualenv --no-site-packages --python={PYTHON_BIN} {VENV_SUBDIR}")
    c.run(f"cd {DJANGO_APP_ROOT} && echo {SRC_DIR} > {VENV_SUBDIR}/lib/{PYTHON_BIN}/site-packages/projectsource.pth")


def ensure_src_dir(c):
    if not dir_exists(c, SRC_DIR):
        c.run(f"mkdir -p {SRC_DIR}")
        
    if not dir_exists(c, posixpath.join(SRC_DIR, '.git')):
        c.run(f"cd {SRC_DIR} && git init")

def push_sources(c):
    """
    Push source code to server.
    """
    ensure_src_dir(c)
    push_rev = getattr(env, 'push_rev', None)
    if push_rev is None:
        push_rev = c.local("git rev-parse HEAD").stdout.strip()

    c.local("git push ssh://%(user)s@%(host)s:%(port)s/%(path)s || true" %
            dict(host=HOST,
                 user=USER,
                 port=PORT,
                 path=SRC_DIR,
                 ))
    c.run(f"cd {SRC_DIR} && git checkout %s" % push_rev)



def webserver_stop(c):
    """
    Stop the webserver that is running the Django instance
    """
    c.sudo("systemctl stop uwsgi-app@redpanal.service")


def webserver_start(c):
    """
    Starts the webserver that is running the Django instance
    """
    c.sudo("systemctl start uwsgi-app@redpanal.service")


def webserver_restart(c):
    """
    Restarts the webserver that is running the Django instance
    """
    try:
        c.sudo("systemctl restart uwsgi-app@redpanal.service")
    except:
        webserver_start(c)


def build_static(c):
    
    if not dir_exists(c, STATIC_ROOT):
        c.run("mkdir -p %s" % STATIC_ROOT)

    run_venv(c, f"cd {MANAGEPY_SUBDIR} && {PYTHON_BIN} manage.py collectstatic --settings=redpanal.production_settings -v 0 --noinput --clear --link")

    c.run(f"chmod -R ugo+r {STATIC_ROOT}")

def clear_sessions(c):
    run_venv(c, f"cd {MANAGEPY_SUBDIR} && {PYTHON_BIN} manage.py clearsessions --settings=redpanal.production_settings")    


def first_deployment_mode(c):
    """
    Use before first deployment to switch on fake south migrations.
    """
    env.initial_deploy = True


def update_database(c):
    managepy = f"cd {MANAGEPY_SUBDIR} && {PYTHON_BIN} manage.py "
    if getattr(env, 'initial_deploy', False):
        run_venv(c, managepy + "migrate --fake-initial --noinput --settings=redpanal.production_settings")
    else:
        run_venv(c, managepy + "migrate --noinput --settings=redpanal.production_settings")


def backup_database(c):
    datestr = datetime.datetime.now().isoformat()
    c.run("cp /var/www/redpanal/db/db.sqlite3 ~/redpanal.db.sqlite3_%s" % datestr)
    c.run("gzip ~/redpanal.db.sqlite3_%s" % datestr)


def rebuild_index(c):
    managepy = "%s manage.py " % PYTHON_BIN
    c.sudo("chmod g+w /var/www/redpanal/whoosh_index/")
    run_venv(c, f'cd {MANAGEPY_SUBDIR} && ' + managepy + "rebuild_index --noinput --settings=redpanal.production_settings")
    c.sudo("chown -R www-data /var/www/redpanal/whoosh_index")

def deploy(c):
    """
    Deploy project.
    """
    webserver_stop(c)
    push_sources(c)
    install_dependencies(c)
    clear_sessions(c)
    backup_database(c)
    update_database(c)
    rebuild_index(c)
    build_static(c)
    webserver_start(c)


"""
anonymous data
sqlite> UPDATE "auth_user" SET "email" = 'foo@bar.com';
sqlite> UPDATE "auth_user" SET "password" = '';
sqlite> UPDATE "auth_user" SET "first_name" = '';
sqlite> UPDATE "auth_user" SET "last_name" = '';
sqlite> DROP table account_emailaddress;
"""

TASKS = {
    'test': test,
    'ensure_src_dir': ensure_src_dir,
    'push_sources': push_sources,
    'webserver_start': webserver_start,
    'webserver_stop': webserver_stop,
    'webserver_restart': webserver_stop,
    'rebuild_index': rebuild_index,
    'install_dependencies': install_dependencies,
    'clear_sessions': clear_sessions,
    'backup_database': backup_database,
    'update_database': update_database,
    'build_static': build_static,
    'deploy': deploy,
}

if __name__ == "__main__":
    from functools import partial
    import argparse
    parser = argparse.ArgumentParser(description='Redpanal deploys')

    parser.add_argument('cmd', choices=TASKS.keys())
    parser.add_argument('--revision', help="Use a specific git revision")
    args = parser.parse_args()

    task = TASKS[args.cmd]
    c = Connection(f'{USER}@{HOST}', port=PORT)
    c.run = partial(c.run, echo=True)
    c.sudo = partial(c.sudo, echo=True)
    task(c)
    
    
