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
In a normal browser the UI uses sample data (`?setup` shows the first-start page).

## Windows installer

`powershell -File installer\build_windows.ps1` makes `build\DubplatesClient-Setup-<version>.exe` (about 15 MB).
Needs `.venv` (run `run.bat` once), Node.js and Inno Setup 6 (`winget install JRSoftware.InnoSetup`).

- Per-user install in `%LOCALAPPDATA%\Programs\Dubplates Client`: no admin rights.
- It holds an embeddable Python, pip, pywebview and the app. On first start the window asks for the engine
  (PyTorch with CUDA for NVIDIA, about 3 GB, or CPU, about 300 MB) and installs it with pip (`bootstrap.py`).
- Uninstall removes the program and the engine. Settings and models stay in `%APPDATA%\Dubplates Client`.

## Layout

| Path | Content |
|---|---|
| `dubplates_client/main.py` | Starts the window (pywebview). Setup mode when the engine is missing. |
| `dubplates_client/bootstrap.py` | First start: installs PyTorch + the engine with pip. |
| `installer/` | Windows installer: build script + Inno Setup script. |
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
