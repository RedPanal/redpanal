# Levantar RedPanal backend localmente

## Requisitos

- Python 3.11+
- ffmpeg (necesario para procesamiento de audio con pydub)
- Docker + Docker Compose (opcional, recomendado)

---

## Sin Docker

### 1. Clonar el repo

```bash
git clone https://github.com/RedPanal/redpanal.git
cd redpanal
```

### 2. Instalar ffmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu / Debian:**
```bash
sudo apt-get install ffmpeg
```

**Windows:** Descargar desde https://ffmpeg.org/download.html y agregar al PATH.

### 3. Crear entorno virtual e instalar dependencias

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# setuptools<58 es necesario para instalar pydub correctamente
pip install "setuptools<58"
pip install -r requirements.txt
```

### 4. Aplicar migraciones

```bash
cd redpanal
python manage.py migrate
```

> `local_settings.py` es opcional. Sin él, Django usa SQLite en `redpanal/redpanal/db.sqlite3`
> y el `SECRET_KEY` definido en `settings.py`, suficiente para desarrollo.

### 5. Crear superusuario

```bash
python manage.py createsuperuser
```

### 6. Levantar el servidor

```bash
python manage.py runserver
```

---

## Con Docker (recomendado)

### 1. Clonar el repo

```bash
git clone https://github.com/RedPanal/redpanal.git
cd redpanal
```

### 2. Levantar los contenedores

```bash
docker-compose up
```

Las migraciones se aplican automáticamente al iniciar.

### 3. Crear superusuario

En otra terminal, con los contenedores corriendo:

```bash
docker-compose exec web python manage.py createsuperuser
```

---

## Verificar que funciona

| URL | Qué ver |
|-----|---------|
| http://localhost:8000/api/audio/list/ | JSON con lista de audios (puede estar vacía) |
| http://localhost:8000/admin/ | Panel de administración de Django |
| http://localhost:8000/api/auth/login/ | `{"error":"Usuario y contraseña requeridos"}` (POST vacío) |

---

## Notas

- **Base de datos:** el proyecto usa SQLite por defecto. No se distribuye ningún archivo `.sqlite3` —
  el comando `migrate` crea la estructura vacía.
- **Archivos de media:** `uploaded_media/` no se distribuye. El directorio se crea solo cuando
  un usuario sube su primer archivo.
- **`local_settings.py`:** si necesitás sobreescribir configuración (ruta de BD, `MEDIA_ROOT`, claves de
  OAuth, etc.), creá `redpanal/redpanal/local_settings.py`. Ese archivo está en `.gitignore`
  y nunca se commitea.
