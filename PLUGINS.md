# Plugins

A plugin is a tool that works on **one stem**: a file goes in, a file comes out. Example: *Vocal repair*
(it cleans an AI-made vocal against a clean reference vocal).

Users run a plugin in the **Library**: open a stem set, click **＋** on a stem, then **Plugin**.
The result **replaces the stem** (same place in the set). The stem from the model stays in `.originals/`, and
**FX › Restore original** puts it back. An Effects chain on the stem works on the plugin's result.

## Where plugins live

Each plugin is a folder in the plugins folder of the client:

| System | Plugins folder |
|---|---|
| Windows | `%APPDATA%\Dubplates Client\plugins\` |
| macOS | `~/Library/Application Support/Dubplates Client/plugins/` |

```
plugins/
└── vocal_repair/
    ├── plugin.json          what the client must know (below)
    ├── audio_restore.py     the code
    ├── requirements.txt     packages the code needs
    └── .models/             any data files (models etc.)
```

**Models › Plugins** in the client shows the plugins, installs their packages ("Install packages"), and has
"Add a plugin folder…" (copies a folder into the plugins folder) and "Open the plugins folder".

## plugin.json

```json
{
  "id": "vocal_repair",
  "name": "Vocal repair",
  "version": "1.0",
  "author": "Anders",
  "description": "Repairs an AI-made vocal ...",
  "for": ["vocals"],
  "entry": "audio_restore:repair_vocal",
  "args": ["$reference", "$stem", "$output"],
  "inputs": [
    {"id": "reference", "type": "audio", "label": "Reference vocal", "help": "...", "remember": true}
  ],
  "options": [
    {"id": "ml", "type": "bool", "label": "ML dereverb (recommended)", "default": true},
    {"id": "mono", "type": "bool", "label": "Mono output", "default": false}
  ],
  "callbacks": {"progress": "progress", "log": "log", "cancel": "should_cancel"},
  "output": {"ext": ".wav"},
  "requirements": "requirements.txt",
  "skipPackages": ["matplotlib"],
  "files": ["audio_restore.py", ".models/dereverb_roformer.onnx", ".models/dereverb_vr.onnx"],
  "time": "About 70 s per song on a good GPU ..."
}
```

| Key | Meaning |
|---|---|
| `id` | Letters, digits, `_ . -`. Usually the folder name. |
| `for` | Stem names the plugin is made for. It is shown first on these stems; it works on all stems. |
| `entry` | `module:function`. The module is a `.py` file in the plugin folder. |
| `args` | The positional arguments. `$stem` = the stem file (the model's stem), `$output` = the file to write, `$<input id>` = a file the user chose. Default: `["$stem", "$output"]`. |
| `inputs` | Files the user chooses. `type`: `audio` or `file`. `remember`: the client fills in the last choice. `optional`: may be empty. Inputs not in `args` go as keyword arguments. |
| `options` | Keyword arguments. `type`: `bool`, `number` or `text`; `default`. The last values are remembered. |
| `callbacks` | The names of the keyword arguments for: `progress(fraction 0..1, message)`, `log(line)`, `cancel()` (returns True when the user cancels). Leave out what the function does not have. |
| `output.ext` | The extension of the file the function writes (`.wav`). The client writes the stem again in the set's format (FLAC / WAV / MP3). |
| `requirements` | A pip requirements file. `skipPackages`: names in it that the client must not install (optional extras). |
| `files` | Files that must be there. If one is missing, the client says "copy the whole plugin folder again". |
| `models` | Files the client downloads on **Install**: `[{"file": ".models/a.onnx", "url": "https://…", "size": 918257906, "sha256": "…", "name": "Mel-Roformer De-Reverb"}]`. Only https. With `size` and `sha256` the client checks the download. The plugin can not run until all are there. |
| `time` | A short note for the user (speed, memory). |

## The function

- It must write a **complete** file to `output` (or raise an exception). Keep the stem's length and timeline:
  the result replaces the stem in a set that plays in sync.
- It may return an object or a dict with `warnings` (a list of strings). The client shows them on the stem.
- An exception's message is shown to the user. A cancel: raise any exception after `cancel()` returned True.
- Printed output goes to `logs/plugin-<id>.log` in the client's folder (not to the user).

## How the client runs it

- In **its own process** (`plugin_runner.py`), one job at a time in the queue. After the job the process ends, so
  all its memory (also GPU memory) is free again. A crash in a plugin does not stop the client.
- With the client's Python 3.11. Packages from `requirements.txt` that the client does not have go into the
  plugin's own `.deps/` folder (first on `sys.path`), so a plugin can not break the stem engine. Example:
  `onnxruntime-directml` for Vocal repair, next to the engine's `onnxruntime`.
- On macOS `onnxruntime-directml` becomes `onnxruntime` (DirectML is only for Windows).

Only add plugins from people you trust: a plugin is a program with the same rights as the client.
