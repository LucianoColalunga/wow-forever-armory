"""Comandos de operación:  python -m app.cli <comando>

create-admin [--email E --name N] [--from-env]   crea el primer admin (contraseña por prompt o env)
sync-catalog                                     sincroniza instancias y fases del catálogo
seed-demo [--force] [--weeks N]                  genera e importa datos DEMO (sintéticos)
reset-demo                                       borra todos los datos DEMO
process-pending                                  procesa la cola de importación en este proceso
reprocess-all [--dataset real|demo]              reencola todos los reportes con el parser actual
rebuild-rankings [--dataset real|demo]           reconstruye la caché de rankings
export-openapi [--out PATH]                      escribe el esquema OpenAPI en JSON
"""

from __future__ import annotations

import argparse
import getpass
import io
import json
import sys
from pathlib import Path

from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.security import hash_password, validate_password_strength
from app.db.session import get_sessionmaker
from app.models import Character, Encounter, Guild, Report, SourceFile, User
from app.parser import PARSER_VERSION
from app.rankings import cache
from app.services.catalog import sync_catalog


def _create_admin(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.from_env:
        email, password = settings.admin_bootstrap_email, settings.admin_bootstrap_password
        name = args.name or "Admin"
        if not email or not password:
            print("Faltan ADMIN_BOOTSTRAP_EMAIL / ADMIN_BOOTSTRAP_PASSWORD.", file=sys.stderr)
            return 2
    else:
        email = args.email or input("Email del admin: ").strip()
        name = args.name or input("Nombre visible: ").strip() or "Admin"
        password = getpass.getpass("Contraseña (mín. 12, mayúsculas, minúsculas y números): ")
        if getpass.getpass("Repetí la contraseña: ") != password:
            print("Las contraseñas no coinciden.", file=sys.stderr)
            return 2
    if (err := validate_password_strength(password)) is not None:
        print(err, file=sys.stderr)
        return 2
    with get_sessionmaker()() as db:
        existing = db.scalar(select(User).where(func.lower(User.email) == email.lower()))
        if existing:
            print(f"Ya existe el usuario {email}; no se modificó.")
            return 0
        db.add(User(email=email.lower(), display_name=name, role="admin", password_hash=hash_password(password)))
        db.commit()
    print(f"Admin creado: {email}")
    return 0


def _sync_catalog(_: argparse.Namespace) -> int:
    with get_sessionmaker()() as db:
        print(json.dumps(sync_catalog(db)))
    return 0


def _reset_demo(_: argparse.Namespace | None = None) -> int:
    with get_sessionmaker()() as db:
        source_ids = list(db.scalars(select(Report.source_file_id).where(Report.dataset == "demo")))
        db.execute(delete(Report).where(Report.dataset == "demo"))
        db.execute(delete(Character).where(Character.dataset == "demo"))
        db.execute(delete(Guild).where(Guild.dataset == "demo"))
        db.execute(delete(Encounter).where(Encounter.dataset == "demo"))
        settings = get_settings()
        for sf in db.scalars(select(SourceFile).where(SourceFile.id.in_(source_ids or [-1]))):
            still_used = db.scalar(select(func.count()).select_from(Report).where(Report.source_file_id == sf.id))
            if not still_used:
                (settings.storage_dir / sf.stored_path).unlink(missing_ok=True)
                db.delete(sf)
        cache.bump_version(db, "demo")
        db.commit()
    print("Datos DEMO eliminados.")
    return 0


def _seed_demo(args: argparse.Namespace) -> int:
    from app.demo.generator import generate
    from app.importer.pipeline import ImportMeta, create_import
    from app.worker.queue import drain

    settings = get_settings()
    with get_sessionmaker()() as db:
        sync_catalog(db)
        existing = db.scalar(select(func.count()).select_from(Report).where(Report.dataset == "demo"))
    if existing and not args.force:
        with get_sessionmaker()() as db:
            outdated = db.scalar(
                select(func.count())
                .select_from(Report)
                .where(Report.dataset == "demo", Report.parser_version != PARSER_VERSION)
            )
        if not (args.refresh_outdated and outdated):
            print(f"Ya hay {existing} reportes DEMO. Usá --force para regenerarlos.")
            return 0
        print(f"{outdated} reportes DEMO con otra versión del parser: se regeneran.")
    if existing:
        _reset_demo()
    files = generate(weeks=args.weeks)
    with get_sessionmaker()() as db:
        for name, text, meta in files:
            m = ImportMeta(title=name.removesuffix(".txt"), dataset="demo", **meta)  # type: ignore[arg-type]
            create_import(db, settings, io.BytesIO(text.encode("utf-8")), name, m, None)
        done = drain(db, settings, max_jobs=10_000)
    print(f"DEMO: {len(files)} archivos generados, {done} trabajos procesados.")
    return 0


def _process_pending(_: argparse.Namespace) -> int:
    from app.worker.queue import drain

    with get_sessionmaker()() as db:
        print(f"Trabajos procesados: {drain(db, get_settings(), max_jobs=10_000)}")
    return 0


def _reprocess_all(args: argparse.Namespace) -> int:
    from app.importer.pipeline import enqueue_reprocess

    with get_sessionmaker()() as db:
        reports = db.scalars(select(Report).where(Report.dataset == args.dataset, Report.deleted_at.is_(None))).all()
        for r in reports:
            enqueue_reprocess(db, r, get_settings())
        db.commit()
    print(f"Reencolados {len(reports)} reportes ({args.dataset}).")
    return 0


def _rebuild(args: argparse.Namespace) -> int:
    with get_sessionmaker()() as db:
        n = cache.rebuild_all(db, args.dataset)
        db.commit()
    print(f"Caché reconstruida: {n} filas ({args.dataset}).")
    return 0


def _export_openapi(args: argparse.Namespace) -> int:
    from app.main import create_app

    schema = create_app().openapi()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OpenAPI escrito en {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create-admin")
    p.add_argument("--email")
    p.add_argument("--name")
    p.add_argument("--from-env", action="store_true")
    p.set_defaults(fn=_create_admin)
    sub.add_parser("sync-catalog").set_defaults(fn=_sync_catalog)
    p = sub.add_parser("seed-demo")
    p.add_argument("--force", action="store_true")
    p.add_argument("--weeks", type=int, default=6)
    p.add_argument("--refresh-outdated", action="store_true", help="regenera si el parser cambió de versión")
    p.set_defaults(fn=_seed_demo)
    sub.add_parser("reset-demo").set_defaults(fn=_reset_demo)
    sub.add_parser("process-pending").set_defaults(fn=_process_pending)
    for name, fn in (("reprocess-all", _reprocess_all), ("rebuild-rankings", _rebuild)):
        p = sub.add_parser(name)
        p.add_argument("--dataset", choices=["real", "demo"], default="real")
        p.set_defaults(fn=fn)
    p = sub.add_parser("export-openapi")
    p.add_argument("--out", default="../docs/openapi.json")
    p.set_defaults(fn=_export_openapi)
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
