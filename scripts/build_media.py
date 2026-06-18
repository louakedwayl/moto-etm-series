#!/usr/bin/env python3
"""Construit le bundle media distribuable depuis moto-etm-assets.

Pour chaque question reference dans data/serie*.json :
  - audio question     : NNN_question.flac  -> media/audio/question/NNN_question.m4a   (AAC 48k mono)
  - audio explication  : NNN_explain.flac   -> media/audio/explanation/NNN_explain.m4a (AAC 48k mono)
Pour chaque scene reference :
  - image scene_NNN.(png|jpg) -> media/images/scene_NNN.webp (<=1280px, qualite 80)

Le bundle media/ est ce que consomment le site web et l'app. Les masters bruts
(FLAC, PNG pleine resolution) restent dans moto-etm-assets et ne sont pas distribues.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_ASSETS = Path("/goinfre/wlouaked/moto-etm-assets")

AUDIO_BITRATE = "48k"
IMAGE_MAX = 1280
IMAGE_QUALITY = "80"


def ffmpeg_exe() -> str:
    exe = os.environ.get("FFMPEG")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        from shutil import which

        found = which("ffmpeg")
        if found:
            return found
    sys.exit("ffmpeg introuvable (pip install --user imageio-ffmpeg)")


def magick_exe() -> str:
    from shutil import which

    return which("magick") or which("convert") or sys.exit("ImageMagick introuvable")


def collect(data_dir: Path):
    ids, scenes = set(), set()
    for f in sorted(data_dir.glob("serie*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        questions = data["questions"] if isinstance(data, dict) else data
        for q in questions:
            ids.add(int(q["id"]))
            if q.get("scene"):
                scenes.add(q["scene"])
    return sorted(ids), sorted(scenes)


def needs_build(src: Path, dst: Path, force: bool) -> bool:
    if force or not dst.exists():
        return True
    return src.stat().st_mtime > dst.stat().st_mtime


def convert_audio(ff, src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ff, "-y", "-loglevel", "error", "-i", str(src),
           "-c:a", "aac", "-b:a", AUDIO_BITRATE, "-ac", "1",
           "-movflags", "+faststart", str(dst)]
    subprocess.run(cmd, check=True)


def convert_image(mg, src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [mg, str(src), "-resize", f"{IMAGE_MAX}x{IMAGE_MAX}>",
           "-quality", IMAGE_QUALITY, "-define", "webp:method=6", str(dst)]
    subprocess.run(cmd, check=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS)
    p.add_argument("--out", type=Path, default=REPO / "media")
    p.add_argument("--force", action="store_true", help="reconvertit meme si la sortie existe")
    p.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    args = p.parse_args()

    ff, mg = ffmpeg_exe(), magick_exe()
    ids, scenes = collect(REPO / "data")
    print(f"{len(ids)} questions, {len(scenes)} scenes -> {args.out}")

    tasks = []  # (label, fn)
    for i in ids:
        n = f"{i:03d}"
        src_q = args.assets_dir / "audio" / "question" / f"{n}_question.flac"
        dst_q = args.out / "audio" / "question" / f"{n}_question.m4a"
        if src_q.exists() and needs_build(src_q, dst_q, args.force):
            tasks.append((dst_q.name, lambda s=src_q, d=dst_q: convert_audio(ff, s, d)))
        src_e = args.assets_dir / "audio" / "explanation" / f"{n}_explain.flac"
        dst_e = args.out / "audio" / "explanation" / f"{n}_explain.m4a"
        if src_e.exists() and needs_build(src_e, dst_e, args.force):
            tasks.append((dst_e.name, lambda s=src_e, d=dst_e: convert_audio(ff, s, d)))

    for scene in scenes:
        stem = Path(scene).stem
        src_i = args.assets_dir / "images" / scene
        if not src_i.exists():
            print(f"  ! image source absente: {scene}", file=sys.stderr)
            continue
        dst_i = args.out / "images" / f"{stem}.webp"
        if needs_build(src_i, dst_i, args.force):
            tasks.append((dst_i.name, lambda s=src_i, d=dst_i: convert_image(mg, s, d)))

    if not tasks:
        print("Rien a faire (bundle a jour).")
        return 0

    print(f"{len(tasks)} fichiers a convertir sur {args.jobs} threads...")
    done = errors = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futures = {ex.submit(fn): label for label, fn in tasks}
        for fut in as_completed(futures):
            label = futures[fut]
            try:
                fut.result()
                done += 1
                if done % 50 == 0:
                    print(f"  {done}/{len(tasks)}")
            except Exception as e:
                errors += 1
                print(f"  ECHEC {label}: {e}", file=sys.stderr)

    total = sum(f.stat().st_size for f in args.out.rglob("*") if f.is_file())
    print(f"Termine: {done} ok, {errors} erreurs. Bundle media = {total/1e6:.1f} Mo")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
