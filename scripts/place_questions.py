#!/usr/bin/env python3
import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path


DEFAULT_ASSETS_DIR = Path("/goinfre/wlouaked/moto-etm-assets")
DEFAULT_WORK_DIR = Path(__file__).resolve().parents[1]


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def normalize_serie(value):
    text = str(value).strip().lower()
    match = re.fullmatch(r"(?:serie)?\s*(\d+)", text)
    if not match:
        raise ValueError(f"serie invalide: {value!r}")
    return int(match.group(1))


def parse_placement(text):
    clean = text.strip()
    match = re.fullmatch(r"(\d+)\s*(?:->|>|:|,|\s+)\s*(?:serie)?\s*(\d+)", clean, re.IGNORECASE)
    if not match:
        raise ValueError(f"placement invalide: {text!r}")
    return int(match.group(1)), normalize_serie(match.group(2))


def read_placements(args):
    placements = []

    for raw in args.placements:
        placements.append(parse_placement(raw))

    if args.file:
        with args.file.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                try:
                    placements.append(parse_placement(line))
                except ValueError as error:
                    raise ValueError(f"{args.file}:{line_number}: {error}") from error

    if not placements:
        raise ValueError("aucun placement fourni")

    return placements


def build_question_index(assets_dir):
    index = {}
    data_dir = assets_dir / "data"
    if not data_dir.is_dir():
        raise FileNotFoundError(f"dossier source introuvable: {data_dir}")

    for path in sorted(data_dir.glob("serie*.json")):
        data = load_json(path)
        for question in data.get("questions", []):
            question_id = question.get("id")
            if isinstance(question_id, int):
                index.setdefault(question_id, deepcopy(question))

    return index


def serie_path(work_dir, serie_number):
    return work_dir / "data" / f"serie{serie_number}.json"


def load_or_create_serie(work_dir, serie_number):
    path = serie_path(work_dir, serie_number)
    if path.exists():
        data = load_json(path)
        if not isinstance(data.get("questions"), list):
            raise ValueError(f"{path}: champ questions manquant ou invalide")
        return path, data

    return path, {
        "id": f"serie{serie_number}",
        "version": "1.0.0",
        "questions": [],
    }


def find_existing(work_dir, question_id):
    found = []
    for path in sorted((work_dir / "data").glob("serie*.json")):
        data = load_json(path)
        for index, question in enumerate(data.get("questions", [])):
            if question.get("id") == question_id:
                found.append((path, data, index))
    return found


def remove_existing(work_dir, question_id):
    removed = []
    for path, data, index in reversed(find_existing(work_dir, question_id)):
        removed_question = data["questions"].pop(index)
        save_json(path, data)
        removed.append((path, removed_question))
    return removed


def apply_placements(work_dir, question_index, placements, move=False, dry_run=False):
    added = []
    skipped = []
    moved = []

    for question_id, serie_number in placements:
        if question_id not in question_index:
            raise KeyError(f"question introuvable dans les assets: {question_id}")

        target_path, target_data = load_or_create_serie(work_dir, serie_number)
        target_has_question = any(q.get("id") == question_id for q in target_data["questions"])
        existing = find_existing(work_dir, question_id)
        existing_elsewhere = [item for item in existing if item[0] != target_path]

        if target_has_question and not existing_elsewhere:
            skipped.append((question_id, serie_number, "deja presente"))
            continue

        if existing_elsewhere and not move:
            paths = ", ".join(str(path.relative_to(work_dir)) for path, _, _ in existing_elsewhere)
            raise ValueError(
                f"question {question_id} deja presente dans {paths}; "
                f"relance avec --move pour la deplacer vers serie{serie_number}"
            )

        if not dry_run:
            if move:
                removed = remove_existing(work_dir, question_id)
                moved.extend((question_id, path) for path, _ in removed if path != target_path)
                target_path, target_data = load_or_create_serie(work_dir, serie_number)

            if not any(q.get("id") == question_id for q in target_data["questions"]):
                target_data["questions"].append(deepcopy(question_index[question_id]))
                save_json(target_path, target_data)

        added.append((question_id, serie_number))

    return added, skipped, moved


def main():
    parser = argparse.ArgumentParser(
        description="Place des questions moto-etm-assets dans les fichiers data/serieN.json du repo de travail."
    )
    parser.add_argument("placements", nargs="*", help="Exemples: 311:3, 312->4, '313 serie5'")
    parser.add_argument("-f", "--file", type=Path, help="Fichier texte contenant un placement par ligne")
    parser.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS_DIR)
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--move", action="store_true", help="Deplace une question deja presente dans une autre serie")
    parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui serait fait sans modifier les fichiers")
    args = parser.parse_args()

    try:
        placements = read_placements(args)
        question_index = build_question_index(args.assets_dir)
        added, skipped, moved = apply_placements(
            args.work_dir,
            question_index,
            placements,
            move=args.move,
            dry_run=args.dry_run,
        )
    except Exception as error:
        print(f"Erreur: {error}", file=sys.stderr)
        return 1

    prefix = "[dry-run] " if args.dry_run else ""
    for question_id, serie_number in added:
        print(f"{prefix}{question_id} -> serie{serie_number}")
    for question_id, serie_number, reason in skipped:
        print(f"{prefix}{question_id} -> serie{serie_number} ignore ({reason})")
    for question_id, path in moved:
        print(f"{prefix}{question_id} retire de {path.relative_to(args.work_dir)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
