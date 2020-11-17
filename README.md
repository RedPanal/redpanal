
# RedPanal

Somos una comunidad **autogestiva libre, colaborativa, abierta y participativa**. Nuestro principal
objetivo es promover el uso de herramientas que nos permitan crear, remixar y compartir nuestras producciones.
Para eso hemos desarrollado una plataforma diseñada para que lxs músicxs puedan interactuar y producir música de
manera colaborativa. La URL de nuestro sitio es [RedPanal.org](http://redpanal.org)


## Workflow

Para colaborar podés instalarte el sitio en tu computadora, siguiendo los pasos de instalación descriptos mas abajo,
luego podés hacer las modificaciones y enviarlas para que las integremos en la plataforma on-line.

Para enviarlas podés hacer un pull-request, el cual será probado y subido on-line en la próxima release del sitio.

Para estar en contacto con nuestra comunidad de usuarios y desarrolladores, podés suscribirte a la siguiente
lista de correo en la siguiente dirección: http://listas.usla.org.ar/cgi-bin/mailman/listinfo/redpanal


## Instalación

En una terminal podés seguir los siguientes pasos, para poder tener el sitio de forma local:

0) Es necesario que tengas instalados los siguientes programas:

    sudo apt-get install virtualenv git ffmpeg libavcodec-extra

1) Clonar el repositorio:

    git clone https://github.com/RedPanal/redpanal.git

2) Crear virtualenv:

    virtualenv --python=python3 redpanal_venv

3) Entrar en virtualenv:

    source redpanal_venv/bin/activate

4) Instalar los requerimientos:

    cd redpanal

    pip install -r requirements.txt

5) Entrar al directorio redpanal y ejecutar:

    cd redpanal

    python manage.py makemigrations

    python manage.py migrate --fake-initial

    python manage.py runserver

6)  Ingresar a 127.0.0.1:8000 desde un browser para ver la versión local del sitio

## Cómo colaborar

Nos organizamos colectivamente dentro de este repositorio de github a través de issues y pull requests. 
Cualquier tipo de colaboración es muy muy bienvenida :) 
Si queres participar pero no sabes por donde empezar podes mirar el lista do de issues abiertos, además hay una etiqueta good-first-issue (https://github.com/RedPanal/redpanal/issues?q=is%3Aissue+is%3Aopen+label%3Agood-first-issue) donde están marcados algunos que pueden ser un buen punto de entrada al proyecto.

## API

RedPanal cuenta con una API HTTP que permite, entre otras cosas, listar y subir audios usando JSON.

### Listar y filtrar audios

* `GET /api/audio/list/`: Lista todos los audios.

Parámetros de la query permitidos: [user, genre, instrument, use_type, tag, positioned, page, page_size]
El resultado está paginado, por defecto se muestra la primer página, equivalente a `?page=1&page_size=100`.

Ejemplos:

* `GET /api/audio/list/?user=redpanal`: Lista los audios del usuario redpanal
* `GET /api/audio/list/?user=redpanal&page=2`: Segunda página.
* `GET /api/audio/list/?page=1&page_size=250`: Primera página, 250 resultados por página.
* `GET /api/audio/list/?genre=rock`: Lista los audios de rock
* `GET /api/audio/list/?genre=rock&use_type=loop&tag=awesome`: Lista los audios de `rock`, que son
de tipo `loop` y que continen en tag `#awesome`.
* `GET /api/audio/list/?tag=metal&tag=picante`: Lista los audios que tienen los tags `#metal` y `#picante`.
* `GET /api/audio/list/?positioned`: Lista de audios que están geo-localizados.


### Detalle de audio

`GET /api/audio/{id}/`: Información de un audio con un `id` específico.

### Crear audio (subir)

`POST /api/audio/`

POST data:

* name (required)
* audio (required): Multipart audio file
* description (required)
* use_type (required): Opciones `["track", "loop", "song", "sample", "other"]`
* genre (required): Opciones `["pop", "rock", "jazz", "blues", "folklore", "electronic", "other"]`
* instrument (required): Opciones `["voice", "guitar", "electric guitar", "bass", "drums", `
    `"saxophone", "piano", "sinthesizer", "electronic", "strings", "woodwind", "brass", "multiple", "other"]`
* tags (required): Una lista de tags, ejemplo `'["foo", "bar"]'`. Si no se quieren agregar tags usar `'[]'`.
* license: Opciones `["CC-BY-SA-4.0"]`
* position_lat
* position_long

Para crear un audio se debe estar logeado usando una sesión (con cookies) o usando Basic auth.

Ejemplo para subir un audio desde la terminal usando `cURL`:

    $ curl -X POST -u myuser:mypassword -F "name=tracktest" -F "licence=CC-BY-SA-4.0" \
      -F "description=This is a test" -F "use_type=track" -F "genre=other" -F "instrument=other" \
      -F 'tags=["untag", "otrotag"]' -F "audio=@/path/to/the/audio.mp3" \
       https://redpanal.org/api/audio/


## Licencia

El software está bajo licencia [GNU Affero General Public License V3.0](https://www.gnu.org/licenses/agpl-3.0.html)
