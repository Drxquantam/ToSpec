# ToSpec API

Server-side FastAPI port of the client-side PHOTO SPEC exam-photo/signature
resizer (`frontend/index.html`), plus batch processing that the browser-only
version can't do.

## What's in here

- `api/` — FastAPI app (Pillow for resize/compress, SQLAlchemy + asyncpg for
  the presets table)
- `db/init.sql` — creates and seeds the `presets` table on first Postgres
  startup
- `frontend/index.html` — the original client-side tool, unmodified, kept
  here for convenience
- `docker-compose.yml` — `api` + `db` services

## Logic parity with the client-side tool

- **Crop**: center-crop/cover-fit to the target aspect ratio (equivalent to
  the HTML's `renderTo()` cover-fit draw with no pan/zoom, since there's no
  interactive frame server-side), then resized to exact `width_px × height_px`.
- **Compression**: the exact same quality ladder as `exportImage()`
  (`95, 90, 85, 80, 75, 70, 65, 60, 50, 40, 30, 20, 12, 8`), same
  best-in-range → closest-below-max → last fallback order.
- **DPI**: embedded via Pillow's `img.save(..., dpi=(dpi, dpi))`, which writes
  a genuine resolution tag. No byte-patching hack needed — that was only
  required in the browser because Canvas's `toBlob()` doesn't expose a way to
  set the JFIF DPI field.
- **Presets**: identical id/label/px/dpi/cm/KB values to the `PRESETS` object
  in the HTML, seeded into Postgres from `db/init.sql`.

## Running it

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000
- Interactive docs: http://localhost:8000/docs
- Postgres: localhost:5432 (creds from `.env`)

No image bytes are ever written to disk or the database — uploads are read
into memory, processed, returned in the response, and discarded.

## Endpoints

| Method | Path            | Description                                             |
|--------|-----------------|----------------------------------------------------------|
| GET    | `/presets`      | List all presets                                          |
| POST   | `/presets`      | Add a custom preset (no auth — see note below)             |
| POST   | `/resize`       | Resize+compress one image, returns the JPEG               |
| POST   | `/resize/batch` | Resize+compress multiple images, returns a zip            |
| GET    | `/health`       | Liveness check                                             |

`/resize` and `/resize/batch` are rate-limited to `RATE_LIMIT_RESIZE`
(default 20/minute per IP, configurable in `.env`).

### `POST /resize`

Multipart form. Either pass `preset_id`, or all five raw fields
(`width_px`, `height_px`, `dpi`, `min_kb`, `max_kb`).

```bash
# Using a preset
curl -X POST http://localhost:8000/resize \
  -F "file=@photo.jpg" \
  -F "preset_id=ssc_photo" \
  -o resized.jpg

# Using a raw spec
curl -X POST http://localhost:8000/resize \
  -F "file=@photo.jpg" \
  -F "width_px=413" -F "height_px=531" -F "dpi=300" \
  -F "min_kb=20" -F "max_kb=50" \
  -o resized.jpg
```

The response body is the JPEG. Metadata comes back in headers:
`X-Result-Kb`, `X-In-Range`, `X-Width-Px`, `X-Height-Px`, `X-Dpi`,
`X-Message` (the last explains what happened if the target range couldn't
be reached).

### `POST /resize/batch`

Same spec rules, but takes multiple `files` and returns a zip. The zip also
contains `manifest.json` with per-file results (since headers don't carry
per-file info once everything's bundled into one zip response).

```bash
curl -X POST http://localhost:8000/resize/batch \
  -F "files=@photo1.jpg" \
  -F "files=@photo2.jpg" \
  -F "preset_id=ibps_photo" \
  -o batch.zip
```

Limits (configurable in `.env`): `MAX_FILE_SIZE_MB` per file (default 15MB),
`MAX_BATCH_FILES` per batch request (default 30).

### `POST /presets`

No auth — stubbed for now per current project scope. Don't expose this
deployment publicly as-is if you add this endpoint to a real environment;
revisit auth before that happens.

```bash
curl -X POST http://localhost:8000/presets \
  -H "Content-Type: application/json" \
  -d '{
    "id": "custom_photo",
    "category": "Custom",
    "label": "My State PSC Photo",
    "width_px": 200, "height_px": 230, "dpi": 200,
    "cm_width": 3.5, "cm_height": 4.5,
    "min_kb": 20, "max_kb": 50
  }'
```

## Wiring the existing HTML frontend to this API

`frontend/index.html` currently does everything client-side and never makes
a network call. To point it at this API instead of (or alongside) its local
Canvas logic, the only place to touch is the `exportImage()` function and the
`generateBtn` click handler — replace the local canvas encode with a
`fetch()` call, e.g.:

```js
async function exportImageViaApi(file, spec) {
  const form = new FormData();
  form.append('file', file);
  form.append('width_px', spec.w);
  form.append('height_px', spec.h);
  form.append('dpi', spec.dpi);
  form.append('min_kb', spec.minKb);
  form.append('max_kb', spec.maxKb);

  const res = await fetch('http://localhost:8000/resize', { method: 'POST', body: form });
  if (!res.ok) throw new Error(await res.text());

  return {
    blob: await res.blob(),
    kb: Number(res.headers.get('X-Result-Kb')),
    inRange: res.headers.get('X-In-Range') === 'true',
    patched: true, // DPI is always genuinely embedded server-side
  };
}
```

Since the HTML is opened via `file://` (or a local dev server), CORS is
already configured to allow `null` and common `localhost` origins — see
`CORS_ORIGINS` in `.env`. If you serve the HTML from a different origin,
add it to that list and restart the `api` service.

## Environment variables

See `.env.example`. Copy it to `.env` before running `docker compose up` —
compose reads `.env` automatically for variable substitution, and the `api`
service also loads it directly via `env_file`.

## Local development without Docker

```bash
cd api
pip install -r requirements.txt
# point DATABASE_URL at a Postgres instance with db/init.sql applied
uvicorn app.main:app --reload
```
