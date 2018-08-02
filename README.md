
RedPanal
========

Somos una comunidad **autogestiva libre, colaborativa, abierta y participativa**. Nuestro principal
objetivo es promover el uso de herramientas que nos permitan crear, remixar y compartir nuestras producciones.
Para eso hemos desarrollado una plataforma diseñada para que lxs músicxs puedan interactuar y producir música de
manera colaborativa. La URL de nuestro sitio es [RedPanal.org](http://redpanal.org)


Workflow
========

Para colaborar podés instalarte el sitio en tu computadora, siguiendo los pasos de instalación descriptos mas abajo,
luego podés hacer las modificaciones y enviarlas para que las integremos en la plataforma on-line.

Para enviarlas podés hacer un pull-request, el cual será probado y subido on-line en la próxima release del sitio.

Para estar en contacto con nuestra comunidad de usuarios y desarrolladores, podés suscribirte a la siguiente
lista de correo en la siguiente dirección: http://listas.usla.org.ar/cgi-bin/mailman/listinfo/redpanal


Instalación
===========

En una terminal podés seguir los siguientes pasos, para poder tener el sitio de forma local:

0) Es necesario que tengas instalados los siguientes programas:

    sudo apt-get install python-imaging virtualenv git

1) Clonar el repositorio:

    git clone https://github.com/RedPanal/redpanal.git

2) Crear virtualenv:

    virtualenv --system-site-packages redpanal_venv

3) Entrar en virtualenv:

    source redpanal_venv/bin/activate

4) Instalar los requerimientos:

    cd redpanal
    
    pip install -r requirements.txt

5) Entrar al directorio redpanal y ejecutar:

    cd redpanal
    
    python manage.py migrate --fake-initial
    
    python manage.py runserver
    
6)  Ingresar a 127.0.0.1:8000 desde un browser para ver la versión local del sitio 

Licencia
========

El software está bajo licencia [GNU Affero General Public License V3.0](https://www.gnu.org/licenses/agpl-3.0.html)

