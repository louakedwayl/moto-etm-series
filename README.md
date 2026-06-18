# moto-etm-series

Repo de **distribution** du contenu ETM (Épreuve Théorique Moto), consommé à la fois
par le site **motoetm.com** et par l'application mobile.

Il contient :

- les **séries de QCM** en JSON (`data/serieN.json`) ;
- le **bundle média optimisé** (`media/`) : audio en AAC et images en WebP, prêts à
  être servis sur le web et le mobile.

Les masters bruts (FLAC lossless, PNG pleine résolution) vivent dans le repo séparé
`moto-etm-assets` et **ne sont pas** distribués ici.

## Structure

```
.
├── data/                         # 10 séries de QCM (400 questions, ids 1 → 400)
│   └── serieN.json               #   { id, version, questions: [...] }
├── media/                        # bundle optimisé (~100 Mo)
│   ├── audio/
│   │   ├── question/NNN_question.m4a      # AAC 48k mono
│   │   └── explanation/NNN_explain.m4a    # AAC 48k mono
│   └── images/scene_NNN.webp     # WebP, max 1280px, qualité 80
└── scripts/build_media.py        # régénère media/ depuis moto-etm-assets
```

## Format des séries

```json
{
  "id": "serie1",
  "version": "1.0.0",
  "questions": [
    {
      "id": 1,
      "scene": "scene_001.png",
      "question": "Texte de la question",
      "answers": ["Oui", "Non"],
      "correct": [0],
      "explanation": "Explication de la réponse."
    }
  ]
}
```

Les `id` de questions sont **uniques et continus** sur l'ensemble des séries (1 → 400).
Le champ `scene` garde son extension d'origine (`.png`/`.jpg`) comme identifiant ; le
fichier média correspondant est `media/images/<base>.webp`. Voir aussi les questions de
type `statements` (plusieurs affirmations Oui/Non) dans `moto-etm-assets`.

## Conventions média

| Type      | Source (assets)        | Bundle (ici)                         |
|-----------|------------------------|--------------------------------------|
| Image     | `scene_NNN.png/.jpg`   | `media/images/scene_NNN.webp`        |
| Audio Q   | `NNN_question.flac`    | `media/audio/question/NNN_question.m4a`   |
| Audio exp | `NNN_explain.flac`     | `media/audio/explanation/NNN_explain.m4a` |

`NNN` = id de la question paddé sur **3 chiffres**.

## Régénérer le bundle média

Nécessite `ffmpeg` (encodeur AAC) et ImageMagick (`magick`). Sans ffmpeg système :

```sh
pip3 install --user imageio-ffmpeg     # fournit un ffmpeg statique
```

Puis :

```sh
python3 scripts/build_media.py                 # convertit ce qui manque
python3 scripts/build_media.py --force         # tout reconvertir
python3 scripts/build_media.py --assets-dir /chemin/vers/moto-etm-assets
```

Le script ne reconvertit que les fichiers absents ou plus anciens que leur source.
