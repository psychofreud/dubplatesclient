# Dubplates.net Client

A free desktop app that makes stems on your own computer (GPU or CPU).
It works alone. It can also work with [dubplates.net](https://dubplates.net) (later).

- Install stem models with one click: BS-Roformer, Mel-Roformer, Demucs, de-reverb and more.
- Add your own models.
- Stems go to `<Track> Stems/`, next to the track or in a folder you choose.
- Windows (NVIDIA CUDA, or CPU) and macOS (Apple Silicon GPU, or CPU).

Engine: [audio-separator](https://github.com/nomadkaraoke/python-audio-separator) (MIT) and PyTorch.

## Run from source

Windows: `run.bat`. macOS / Linux: `./run.sh`.
The first start makes `.venv`, installs PyTorch (CUDA when an NVIDIA GPU is found) and builds the UI.

UI development: `cd ui; npm install; npm run dev`, then start with `DUBPLATES_UI=http://localhost:5174`.

## Layout

| Path | Content |
|---|---|
| `dubplates_client/main.py` | Starts the window (pywebview). |
| `dubplates_client/api.py` | The methods the UI calls (`window.pywebview.api.*`). |
| `dubplates_client/config.py` | User settings, saved locally (never sent anywhere). |
| `dubplates_client/catalog.py` | The list of known models (`catalog.json`) and custom models. |
| `dubplates_client/jobs.py` | The stem queue: one track at a time, progress, output folder. |
| `ui/` | React UI (Vite). Same look as dubplates.net. |

## Folders

- Settings: `%APPDATA%\Dubplates Client` (Windows), `~/Library/Application Support/Dubplates Client` (macOS).
- Models: `models/` inside that folder (you can change it in Settings).

## Output

```
My Track Stems/
  My Track - Vocals.flac
  My Track - Instrumental.flac
  dubplates.json      (model, source file hash, stems, date)
```

## Licence

GPL-3.0-or-later. See `LICENSE`.
Model files have their own licences. The client downloads them from their original places.
