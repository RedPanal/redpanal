#!/usr/bin/env python3
"""Publish a studio folder to a RedPanal work, like a commit.

Only files that changed since the last time are uploaded: stems become parts
of the work (aligned from 0:00), session files (.cpr, .ptx, .als, .dawproject,
MIDI, presets) travel as attachments. Needs only Python 3.8+, no extra packages.

    python redpanal_sync.py login --server https://redpanal.org
    python redpanal_sync.py works
    python redpanal_sync.py push "C:\\Musica\\Lluvia\\Stems" --work lluvia-en-pichincha --version "Bajo nuevo"
    python redpanal_sync.py push ./stems --work lluvia-en-pichincha --dry-run
"""
import argparse
import getpass
import hashlib
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid

CONFIG = os.environ.get("REDPANAL_SYNC_CONFIG") or os.path.join(os.path.expanduser("~"), ".redpanal-sync.json")
BATCH_BYTES = 200 * 1024 * 1024  # keep each request reasonable


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        sys.exit("Primero iniciá sesión:  python redpanal_sync.py login --server https://redpanal.org")


def request(method, url, token=None, data=None, headers=None):
    headers = dict(headers or {})
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode("utf-8") or "null")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"error": body[:300]}


def multipart(fields, files):
    """Encode a multipart/form-data body. files: list of (field, path)."""
    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields:
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (boundary, name, value)).encode("utf-8"))
    for name, path in files:
        filename = os.path.basename(path)
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        head = ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
                % (boundary, name, filename.replace('"', ""), ctype)).encode("utf-8")
        with open(path, "rb") as f:
            parts.append(head + f.read() + b"\r\n")
    parts.append(("--%s--\r\n" % boundary).encode("utf-8"))
    return b"".join(parts), "multipart/form-data; boundary=" + boundary


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cmd_login(args):
    server = args.server.rstrip("/")
    username = input("Usuario: ").strip()
    password = getpass.getpass("Contraseña: ")
    status, data = request("POST", server + "/api/auth/login/", data=json.dumps(
        {"username": username, "password": password}).encode(), headers={"Content-Type": "application/json"})
    if status != 200 or not data.get("token"):
        sys.exit("No se pudo iniciar sesión: %s" % (data or {}).get("error", status))
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump({"server": server, "token": data["token"], "username": data.get("username")}, f)
    try:
        os.chmod(CONFIG, 0o600)
    except OSError:
        pass
    print("Listo, sesión iniciada como %s." % data.get("username"))


def cmd_works(args):
    cfg = load_config()
    status, data = request("GET", cfg["server"] + "/api/works/?mine=1" if args.mine else cfg["server"] + "/api/works/",
                           token=cfg["token"])
    if status != 200:
        sys.exit("Error %s: %s" % (status, data))
    for w in data:
        print("%-40s %-10s %s%s" % (w["slug"], w["visibility"], w["name"], "" if w["can_contribute"] else "  (solo escucha)"))


def scan(folder, accepted):
    audio_ext, attach_ext = set(accepted["audio"]), set(accepted["attachments"])
    found = []
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in sorted(names):
            if name.startswith("."):
                continue
            ext = os.path.splitext(name)[1][1:].lower()
            if ext in audio_ext or ext in attach_ext:
                found.append((os.path.join(root, name), "audio" if ext in audio_ext else "attachment"))
    return found


def cmd_push(args):
    cfg = load_config()
    base = cfg["server"] + "/api/works/%s/" % args.work
    status, work = request("GET", base, token=cfg["token"])
    if status != 200:
        sys.exit("No se encontró la obra «%s» o no tenés acceso (%s)." % (args.work, status))
    if not work.get("can_contribute"):
        sys.exit("Podés ver «%s» pero no aportar. Pedí sumarte desde la web." % work["name"])

    known = set()
    for p in work.get("parts", []):
        known.update(p["sha256"])
    known.update(a["sha256"] for a in work.get("attachments", []))

    files = scan(args.folder, work["accepted_extensions"])
    if not files:
        sys.exit("No hay archivos de audio ni de sesión en %s." % args.folder)
    pending = [(path, kind) for path, kind in files if sha256(path) not in known]
    print("%d archivos en la carpeta, %d sin cambios, %d para subir." % (len(files), len(files) - len(pending), len(pending)))
    for path, kind in pending:
        print("  + %s%s" % (os.path.relpath(path, args.folder), "" if kind == "audio" else "  (archivo de sesión)"))
    if args.dry_run or not pending:
        if not pending:
            print("Nada nuevo para subir.")
        return

    if not work["is_owner"] and not args.accept_terms:
        sys.exit("Para aportar a una obra ajena tenés que aceptar que tus partes sigan la licencia de la obra: "
                 "agregá --accept-terms.")

    batches, current, size = [], [], 0
    for path, kind in pending:
        s = os.path.getsize(path)
        if current and size + s > BATCH_BYTES:
            batches.append(current); current, size = [], 0
        current.append(path); size += s
    batches.append(current)

    totals = {"added": [], "replaced": [], "attachments": [], "errors": []}
    for i, batch in enumerate(batches, 1):
        fields = [("note", args.note or "")]
        if args.accept_terms:
            fields.append(("accept_terms", "1"))
        body, ctype = multipart(fields, [("stems", p) for p in batch])
        print("Subiendo tanda %d de %d (%.1f MB)…" % (i, len(batches), len(body) / 1048576.0))
        status, data = request("POST", base + "stems/", token=cfg["token"], data=body, headers={"Content-Type": ctype})
        if status not in (200, 400):
            sys.exit("Error %s: %s" % (status, data))
        for key in totals:
            totals[key].extend(data.get(key, []))

    print("Partes nuevas: %d · reemplazadas por una toma nueva: %d · archivos de sesión: %d"
          % (len(totals["added"]), len(totals["replaced"]), len(totals["attachments"])))
    for e in totals["errors"]:
        print("  ! " + e)

    if args.version:
        if work["is_owner"]:
            status, data = request("POST", base + "versions/", token=cfg["token"],
                                   data=json.dumps({"message": args.version}).encode(),
                                   headers={"Content-Type": "application/json"})
            print("Versión %s guardada: %s%s" % (data.get("number"), cfg["server"], data.get("url")) if status == 201
                  else "No se pudo guardar la versión: %s" % data)
        else:
            print("Solo quien creó la obra guarda versiones; tus partes quedaron como aportes propuestos.")


def main():
    parser = argparse.ArgumentParser(description="Publicar la carpeta del estudio en una obra de RedPanal.")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("login", help="iniciar sesión y guardar el token")
    p.add_argument("--server", default="https://redpanal.org")
    p.set_defaults(func=cmd_login)
    p = sub.add_parser("works", help="listar obras")
    p.add_argument("--mine", action="store_true", help="solo las mías")
    p.set_defaults(func=cmd_works)
    p = sub.add_parser("push", help="subir lo que cambió en una carpeta")
    p.add_argument("folder")
    p.add_argument("--work", required=True, help="identificador de la obra (lo que va después de /p/ en la dirección)")
    p.add_argument("--version", help="guardar una versión con este mensaje (solo quien creó la obra)")
    p.add_argument("--note", help="nota para quien creó la obra")
    p.add_argument("--accept-terms", action="store_true", help="aceptar que tus partes sigan la licencia de la obra")
    p.add_argument("--dry-run", action="store_true", help="mostrar qué se subiría, sin subir")
    p.set_defaults(func=cmd_push)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
