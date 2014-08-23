========
RedPanal
========

Install
=======


* Clone this repository
 * git clone https://github.com/RedPanal/redpanal.git

* Create virtualenv
 * virtualenv --system-site-packages redpanal_venv

* Enter virtualenv
 * source redpanal_venv/bin/activate

* install timeside 0.4.4:
 * sudo apt-get install python-imaging
 * pip install numpy mutagen
 * pip install timeside==0.4.4 --no-dependencies

* pip install -r requirements.txt
* enter inside and run:

 * python manage.py syncdb --all
 * python manage.py migrate --fake
 * python manage.py runserver


License
=======

This software is licensed under AGPL.
