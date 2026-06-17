# moto-etm-series

Depot de series JSON compatible avec le format de `moto-etm-assets`.

## Format

Chaque serie est stockee dans `data/serieN.json` :

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
      "explanation": "Explication de la reponse."
    }
  ]
}
```

Quand tu fournis des objets JSON, ils seront ajoutes dans la prochaine serie en gardant cette structure.

## Placement automatique

Le script `scripts/place_questions.py` recopie les questions depuis `/goinfre/wlouaked/moto-etm-assets/data`
vers les fichiers `data/serieN.json` de ce depot.

Exemples :

```sh
python3 scripts/place_questions.py 316:8 '317 serie9' '318 -> serie10'
```

Ou avec un fichier texte :

```sh
python3 scripts/place_questions.py -f placements.example.txt
```

Formats acceptes dans le fichier :

```txt
316 -> serie8
317 serie9
318:10
```

Par defaut, le script bloque si une question existe deja dans une autre serie. Pour la deplacer :

```sh
python3 scripts/place_questions.py --move '316 -> serie8'
```

Pour tester sans modifier les fichiers :

```sh
python3 scripts/place_questions.py --dry-run -f placements.example.txt
```

## Interface locale

Pour utiliser une interface simple dans le navigateur :

```sh
python3 scripts/placement_ui.py
```

Puis ouvre :

```txt
http://127.0.0.1:8765
```
