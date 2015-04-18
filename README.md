
RedPanal
========

## [ES] ##

Somos una comunidad **autogestiva libre, colaborativa, abierta y participativa**. Nuestro principal objetivo es promover el uso de herramientas que nos permitan crear, remixar y compartir nuestras producciones. Para eso hemos desarrollado una plataforma diseñada para que lxs músicxs puedan interactuar y producir música de manera colaborativa. Actualmente tenemos una nueva versión del sitio en fase beta, que podés probar ingresando acá: [Beta.RedPanal.org](http://beta.redpanal.org)

## [EN] ##

We are a community **Free self-management, collaborative, open and participatory**. Our main objective is to promote the use of tools that allow us to create, remix and share our productions. For this we have developed a platform designed for vegan músicxs can interact and produce music collaboratively. Currently we have a new version of the site in beta, you can try entering here:  [Beta.RedPanal.org](http://beta.redpanal.org)

Instalación [ES]
================

1) Clonar el repositorio:

    git clone https://github.com/RedPanal/redpanal.git

2) Crear virtualenv:

    virtualenv --system-site-packages redpanal_venv

3) Entrar en virtualenv:

    source redpanal_venv/bin/activate

4) Instalar timeside 0.4.4:

    sudo apt-get install python-imaging
    pip install numpy mutagen
    pip install timeside==0.4.4 --no-dependencies

5) Instalar requerimientos:

    pip install -r requirements.txt

6) Entrar a redpanal y ejecutar:

    python manage.py syncdb --all
    python manage.py migrate --fake
    python manage.py runserver

Install[EN]
===========

1) Clone this repository: 

    git clone https://github.com/RedPanal/redpanal.git

2) Create virtualenv

    virtualenv --system-site-packages redpanal_venv

3) Enter virtualenv

    source redpanal_venv/bin/activate
   
4)  Install timeside 0.4.4:

    sudo apt-get install python-imaging
    pip install numpy mutagen
    pip install timeside==0.4.4 --no-dependencies

5) Install requeriments: 

    pip install -r requirements.txt
   
6) Enter inside redpanal dir and run:

    python manage.py syncdb --all
    python manage.py migrate --fake
    python manage.py runserver

Licencia [ES]
=============

El software está bajo licencia [GNU Affero General Public License V3.0](https://www.gnu.org/licenses/agpl-3.0.html)

License [EN]
============

This software is licensed under [GNU Affero General Public License V3.0](https://www.gnu.org/licenses/agpl-3.0.html)
