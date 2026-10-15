# redpanal_sync: publicar la carpeta del estudio

Sube a una obra de RedPanal lo que cambió en una carpeta, como un *commit*:

- Los archivos de audio (WAV, FLAC, MP3, OGG, M4A…) pasan a ser partes de la obra, alineadas desde 0:00.
- Los archivos de sesión (`.cpr`, `.ptx`, `.als`, `.rpp`, `.flp`, `.dawproject`), el MIDI y los presets viajan como adjuntos.
- Lo que no cambió no se vuelve a subir. Un archivo con el mismo nombre que una parte ya incluida cuenta como toma nueva: la anterior queda como alternativa.

Solo necesita Python 3.8 o más nuevo, sin paquetes extra.

```
python redpanal_sync.py login --server https://redpanal.org
python redpanal_sync.py works --mine
python redpanal_sync.py push "C:\Musica\Zamba\Stems" --work zamba-del-puerto --dry-run
python redpanal_sync.py push "C:\Musica\Zamba\Stems" --work zamba-del-puerto --version "Bajo nuevo"
```

- `--work` es lo que aparece después de `/p/` en la dirección de la obra.
- `--version` guarda una versión con ese mensaje. Solo puede hacerlo quien creó la obra.
- Para aportar a la obra de otra persona hace falta `--accept-terms`: tus partes siguen la licencia de la obra.
- La sesión se guarda en `~/.redpanal-sync.json`. Se puede cambiar con la variable `REDPANAL_SYNC_CONFIG`.

Recomendación: exportá los stems desde el compás 1, todos con el mismo inicio, así quedan alineados en cualquier programa.
