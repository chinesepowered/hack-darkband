# capyfinder (built by the Onsen factory)

Spec: [SPEC.md](SPEC.md). Answer to "where can I meet a capybara today?" — every fact carries its source.

## Run

```sh
python3 app.py
```

Starts the server on port **8000**. Override with the `PORT` env var: `PORT=9000 python3 app.py`.

## Data

`data/spots.json` — spot dataset gathered from the live web (Scout/Nimble); every spot carries its `source_url`.