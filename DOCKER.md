# Entorno Docker seguro de RedPanal

## Requisitos (una sola vez)
1. Instalar WSL 2 (en PowerShell como administrador): `wsl --install`, y reiniciar.
2. Instalar Docker Desktop desde https://www.docker.com/products/docker-desktop/ (backend WSL 2).

## Uso
```
docker compose up --build                                  # construir, migrar y levantar → http://localhost:8000
docker compose exec web python manage.py createsuperuser   # crear admin (con el server corriendo)
docker compose exec web bash                               # entrar al contenedor
docker compose down                                        # apagar
docker compose run --rm offline python manage.py test      # tests SIN red
```
Docker avisa que hay dos archivos compose: usa `compose.yaml` (este, endurecido).
El `docker-compose.yml` original del repo queda intacto, pero corre como root y expone el puerto a toda la red.

Para comprobar que funciona: http://localhost:8000/api/audio/list/ y http://localhost:8000/admin/

## Qué protege
| Medida | Efecto |
|---|---|
| Solo se monta esta carpeta | El contenedor no ve tu disco, documentos ni credenciales |
| Usuario `dev` sin sudo | No hay root dentro del contenedor |
| `cap_drop: ALL` + `no-new-privileges` | No puede escalar privilegios ni usar capacidades del kernel |
| Raíz de solo lectura | Solo se puede escribir en `/app`, el home (volumen) y `/tmp` (noexec) |
| Dependencias fijas en la imagen | Nada en ejecución puede instalar o modificar paquetes de Python |
| Puerto en `127.0.0.1` | El servidor de desarrollo no queda expuesto a tu red |
| Límites de RAM/CPU/procesos | Un proceso descontrolado no tumba la PC |
| Servicio `offline` | Sin ningún acceso a red |

## Datos de demostración
```
docker compose exec web python manage.py seed_demo
```
Crea dos cuentas de prueba (`lucia_demo` y `tincho_demo`), una obra con pedidos y un aporte pendiente,
para probar los flujos de colaboración. La contraseña compartida está en
`redpanal/project/management/commands/seed_demo.py`. Solo corre con `DEBUG = True`.

## Al desplegar los cambios de privacidad
```
docker compose exec web python manage.py migrate
docker compose exec web python manage.py secure_private_audio
```
El segundo comando mueve los audios de obras no públicas subidos antes del cambio a carpetas con nombre
aleatorio. Las rutas viejas (`uploads/audios/AÑO_MES/archivo`) se podían adivinar.

## Operación
- **Moderación:** quienes moderan son el staff y las personas del grupo `moderadores`. El grupo se crea desde
  `/admin/` › Grupos, y se suma gente desde ahí. El panel queda en `/moderacion/`.
- **Cuota de almacenamiento:** `RP_USER_QUOTA_MB` (por defecto 2000 MB por persona) y
  `RP_ATTACHMENT_MAX_MB` (500 MB por archivo de sesión), en `common_settings.py` o en `local_settings.py`.
- **Sincronizar la carpeta del estudio** desde la computadora: ver [tools/README.md](tools/README.md).
- **App instalable:** el service worker se sirve en `/sw.js`. Solo funciona con HTTPS (o en `localhost`).

## Traducciones
```
docker compose exec web python manage.py makemessages -l es -i uploaded_media -i whoosh_index -i static
docker compose exec web python manage.py compilemessages -l es -i uploaded_media
```

## Agregar dependencias
Editar `requirements.txt` y correr `docker compose build`.

## Límites a tener en cuenta
- Lo que se escriba en `/app` **sí** afecta a la carpeta real del proyecto.
- `settings.py` trae un `SECRET_KEY` público y `DEBUG = True`: sirve solo para desarrollo.
  Los secretos propios van en `redpanal/redpanal/local_settings.py` (está en `.gitignore`).
- Nunca montes `/var/run/docker.sock` ni actives `privileged`: anularía todo el aislamiento.
