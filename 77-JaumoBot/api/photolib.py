"""
Photo library: bulk import (images or ZIP archives), normalisation to clean JPEGs,
duplicate detection, thumbnails, and usage tracking (each photo -> one account).
"""

import hashlib
import io
import random
import re
import zipfile
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlmodel import Session, select

from .models import Account, BotRun, Photo
from .settings import PHOTOS_DIR

THUMBS_DIR = PHOTOS_DIR / ".thumbs"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
MAX_SIDE = 1600            # longest side after import
MIN_SIDE = 320             # reject tiny images
THUMB_SIDE = 360
MAX_FILE_BYTES = 30 * 1024 * 1024
ZIP_MAX_FILES = 3000
ZIP_MAX_TOTAL = 1024 * 1024 * 1024   # 1 GB uncompressed guard against zip bombs
ACTIVE_STATUSES = ("queued", "running")

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _clean_jpeg(data: bytes) -> tuple[bytes, int, int]:
    """Decode any supported image, fix rotation, drop metadata (EXIF/GPS), cap size, re-encode as JPEG."""
    try:
        with Image.open(io.BytesIO(data)) as im:
            im.seek(0)
            im = ImageOps.exif_transpose(im)
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            elif im.mode != "RGB":
                im = im.convert("RGB")
            w, h = im.size
            if min(w, h) < MIN_SIDE:
                raise ValueError(f"too small ({w}×{h}) — needs at least {MIN_SIDE}px on the short side")
            if max(w, h) > MAX_SIDE:
                im.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            out = io.BytesIO()
            im.save(out, "JPEG", quality=90, optimize=True, progressive=True)  # no exif= → metadata stripped
            return out.getvalue(), im.size[0], im.size[1]
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise ValueError(f"not a readable image ({type(e).__name__})")


def _write_thumb(filename: str, jpeg: bytes):
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    with Image.open(io.BytesIO(jpeg)) as im:
        im.thumbnail((THUMB_SIDE, THUMB_SIDE), Image.Resampling.LANCZOS)
        im.save(THUMBS_DIR / filename, "JPEG", quality=80)


def _unique_filename(original: str, taken: set[str]) -> str:
    stem = _SAFE.sub("_", Path(original).stem)[:60].strip("._") or "photo"
    name, n = f"{stem}.jpg", 2
    while name.lower() in taken or (PHOTOS_DIR / name).exists():
        name, n = f"{stem}_{n}.jpg", n + 1
    taken.add(name.lower())
    return name


def _iter_upload(filename: str, data: bytes):
    """Yield (display_name, bytes) for an image, or for every image inside a ZIP."""
    ext = Path(filename).suffix.lower()
    if ext == ".zip" or data[:4] == b"PK\x03\x04":
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile:
            yield filename, None, "not a valid ZIP file"
            return
        entries = [i for i in zf.infolist() if not i.is_dir()
                   and not i.filename.startswith("__MACOSX/")
                   and not Path(i.filename).name.startswith(".")
                   and Path(i.filename).suffix.lower() in IMAGE_EXTS]
        if len(entries) > ZIP_MAX_FILES:
            yield filename, None, f"ZIP has {len(entries)} images — max {ZIP_MAX_FILES} per archive"
            return
        if sum(i.file_size for i in entries) > ZIP_MAX_TOTAL:
            yield filename, None, "ZIP is too large when extracted (over 1 GB)"
            return
        if not entries:
            yield filename, None, "ZIP contains no images"
            return
        for info in entries:
            label = f"{Path(filename).name} › {info.filename}"
            if info.file_size > MAX_FILE_BYTES:
                yield label, None, "file larger than 30 MB"
                continue
            yield label, zf.read(info), None
        return
    if ext not in IMAGE_EXTS and ext:
        yield filename, None, f"unsupported file type '{ext}'"
        return
    if len(data) > MAX_FILE_BYTES:
        yield filename, None, "file larger than 30 MB"
        return
    yield filename, data, None


def import_uploads(s: Session, files: list[tuple[str, bytes]]) -> list[dict]:
    """Import images/ZIPs. Returns one result per image: saved | duplicate | error."""
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    known_hashes = {h: f for h, f in s.exec(select(Photo.sha256, Photo.filename)).all()}
    taken = {f.lower() for f in s.exec(select(Photo.filename)).all()}
    results = []
    for upload_name, data in files:
        for label, raw, error in _iter_upload(upload_name, data):
            if error:
                results.append({"name": label, "status": "error", "detail": error})
                continue
            try:
                jpeg, w, h = _clean_jpeg(raw)
            except ValueError as e:
                results.append({"name": label, "status": "error", "detail": str(e)})
                continue
            digest = hashlib.sha256(jpeg).hexdigest()
            if digest in known_hashes:
                results.append({"name": label, "status": "duplicate",
                                "detail": f"same image as {known_hashes[digest]}"})
                continue
            filename = _unique_filename(Path(label.split(" › ")[-1]).name, taken)
            (PHOTOS_DIR / filename).write_bytes(jpeg)
            _write_thumb(filename, jpeg)
            s.add(Photo(filename=filename, sha256=digest, width=w, height=h, size=len(jpeg),
                        original_name=label[:250]))
            known_hashes[digest] = filename
            results.append({"name": label, "status": "saved", "detail": filename})
    s.commit()
    return results


def sync_library(s: Session):
    """Register JPEGs already on disk (e.g. copied into the volume) and drop rows whose file vanished."""
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    rows = {p.filename: p for p in s.exec(select(Photo)).all()}
    on_disk = {p.name: p for p in PHOTOS_DIR.glob("*") if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg")}
    for name, path in on_disk.items():
        if name in rows:
            if not (THUMBS_DIR / name).exists():
                _write_thumb(name, path.read_bytes())
            continue
        data = path.read_bytes()
        try:
            with Image.open(io.BytesIO(data)) as im:
                w, h = im.size
        except Exception:
            continue
        s.add(Photo(filename=name, sha256=hashlib.sha256(data).hexdigest(), width=w, height=h,
                    size=len(data), original_name=name))
        _write_thumb(name, data)
    for name, row in rows.items():
        if name not in on_disk:
            s.delete(row)
    s.commit()


def photo_usage(s: Session) -> tuple[Counter, dict, set]:
    """
    Returns (usage count per filename, {filename: (account_id, name, status)} for the
    latest account using it, filenames reserved by queued/running runs).
    """
    usage, owner = Counter(), {}
    for acc_id, name, status, photo in s.exec(
            select(Account.id, Account.name, Account.status, Account.photo)
            .where(Account.photo.is_not(None)).order_by(Account.id)).all():
        usage[photo] += 1
        owner[photo] = (acc_id, name, status)
    reserved = set(s.exec(select(BotRun.photo).where(
        BotRun.kind == "signup", BotRun.status.in_(ACTIVE_STATUSES),
        BotRun.account_id.is_(None), BotRun.photo.is_not(None))).all())
    for f in reserved:
        usage[f] += 1
    return usage, owner, reserved


def pick_photos(s: Session, settings: dict, count: int, unique: bool) -> list[str]:
    """Least-used photos from the config's pool (or the whole library). Raises ValueError when short."""
    library = [f for f in s.exec(select(Photo.filename).order_by(Photo.id)).all() if (PHOTOS_DIR / f).exists()]
    pool = [f for f in (settings.get("photo_pool") or []) if f in set(library)] or library
    if not pool:
        raise ValueError("No photos in the library — upload photos first (Photos page)")
    usage, _, _ = photo_usage(s)
    picked = []
    for _ in range(count):
        low = min(usage[f] for f in pool)
        if unique and low > 0:
            scope = "selected photo pool" if settings.get("photo_pool") else "photo library"
            raise ValueError(f"Not enough unused photos: only {len(picked)} of {count} available in the {scope}. "
                             "Upload more photos, widen the config's photo pool, or allow photo reuse in Settings.")
        f = random.choice([x for x in pool if usage[x] == low])
        picked.append(f)
        usage[f] += 1
    return picked


def delete_photo_files(filename: str):
    for p in (PHOTOS_DIR / filename, THUMBS_DIR / filename):
        if p.exists():
            p.unlink()
