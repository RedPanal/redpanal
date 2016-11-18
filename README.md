
RedPanal
========
Somos una comunidad **autogestiva libre, colaborativa, abierta y participativa**. Nuestro principal objetivo es promover el uso de herramientas que nos permitan crear, remixar y compartir nuestras producciones. Para eso hemos desarrollado una plataforma diseñada para que lxs músicxs puedan interactuar y producir música de manera colaborativa. La URL de nuestro sitio es [RedPanal.org](http://redpanal.org)


Workflow [ES]
================
Para colaborar podés instalarte el sitio en tu computadora, siguiendo los pasos de instalación descriptos mas abajo, luego podés hacer las modificaciones y enviarlas para que las integremos en la plataforma on-line.

Para enviarlas podés hacer un pull-request , el cual será probado y subido on-line en la próxima release del sitio.

Para estar en contacto con nuestra comunidad de usuarios y desarrolladores, podés suscribirte a la siguiente lista de correo en la siguiente dirección: redpanal@listas.ulsa.org.ar


Instalación [ES]
================

En una terminal podés seguir los siguientes pasos, para poder tener el sitio de forma local:

1) Clonar el repositorio:

    git clone https://github.com/RedPanal/redpanal.git

2) Crear virtualenv:
    
    sudo apt-get install virtualenv
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


Licencia
=============

El software está bajo licencia [GNU Affero General Public License V3.0](https://www.gnu.org/licenses/agpl-3.0.html)

