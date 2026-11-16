# Estadísticas de visitas (Umami)

RedPanal cuenta visitas con [Umami](https://umami.is), alojado en el mismo servidor. Las estadísticas son solo para quienes administran el sitio: no hay panel público.

## Qué se cuenta y qué no

- **Se cuenta:** páginas vistas (solo la dirección, sin lo que va después de `?`), de dónde llega la gente, país, dispositivo e idioma.
- **Eventos:**

  | Evento | Cuándo |
  |---|---|
  | `play` | Escuchar un sonido (`kind: sound`) o un proyecto (`kind: project`) |
  | `download` | Bajar un archivo, las partes de un proyecto o su mezcla |
  | `upload` | Subir un archivo |
  | `contribute` | Sumar una pista a un proyecto, que crea una versión |
  | `signup` | Crear una cuenta |
  | `follow` | Seguir a alguien |
  | `post` | Publicar algo |

- **Nunca se envía:**
  - quién es la persona: ni usuario, ni IP (Umami no la guarda), ni cookies;
  - lo que alguien buscó;
  - nada de las páginas privadas. Estudio, Ajustes, Avisos, Crear, los proyectos y sonidos privados o con link secreto, lo oculto por moderación y las búsquedas filtradas no se cuentan. Si en una de esas páginas pasa un evento, se registra sin dirección ni título.
- **"No rastrear":** si el navegador lo tiene activado, no se envía nada.

El código está en `redpanal/core/analytics.py` (servidor) y `redpanal/redpanal/static/js/rp-analytics.js` (navegador).

## Instalación

1. **Secretos:** copiá `docker/umami/.env.example` a `docker/umami/.env` y completá los dos valores con cadenas largas al azar, por ejemplo `openssl rand -hex 32`. El archivo `.env` no se versiona.
2. **Levantar Umami:**
   ```
   docker compose -f docker/umami/compose.yaml up -d
   ```
   Queda escuchando en `127.0.0.1:3000`. Antes de producción, fijá la imagen a la versión que probaste en lugar de `latest`.
3. **Publicarlo** como `https://stats.redpanal.org` desde el servidor web (proxy hacia `127.0.0.1:3000`), con HTTPS.
4. **Entrar a Umami** (usuario inicial `admin`, contraseña `umami`) y **cambiar la contraseña enseguida**. Crear una cuenta para cada persona que administra el sitio.
5. **Agregar el sitio** `redpanal.org` en Umami y copiar su *Website ID*.
6. **Configurar RedPanal** con variables de entorno (o en `local_settings.py`):
   ```
   UMAMI_SCRIPT_URL=https://stats.redpanal.org/script.js
   UMAMI_WEBSITE_ID=<el Website ID>
   UMAMI_DOMAINS=redpanal.org
   ```
   `UMAMI_DOMAINS` hace que solo se cuente en el dominio real, no en staging ni en desarrollo. Sin estas variables, las estadísticas quedan apagadas.
7. Reiniciar RedPanal y abrir el sitio: la visita aparece en Umami en tiempo real.

## Mantenimiento

- Los datos están en el volumen `umami-db`. Conviene incluirlo en los backups.
- Umami no borra datos viejos solo. Si se quiere guardar, por ejemplo, un año, se puede borrar lo anterior desde su panel.
