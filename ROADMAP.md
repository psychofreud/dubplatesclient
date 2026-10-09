# Roadmap

## Phase 1: stems on this computer (now)
- [x] Model manager: suggested models, all engine models, custom models (.ckpt + .yaml, https or local file, optional SHA-256).
- [x] Stem queue: drop files or folders, progress, cancel, "Open folder".
- [x] Output: `<Track> Stems/` next to the track or in one folder; FLAC / WAV / MP3; `dubplates.json`.
- [x] Chains: step 2 splits a stem again (now: Drums → kick, snare, toms, hi-hat, ride, crash in `Drums parts/`).
- [ ] Installers: Windows (PyInstaller + Inno Setup, code signing), macOS (Apple Silicon, notarized).
- [ ] First start without PyTorch: download the correct PyTorch (NVIDIA / Apple / CPU) with progress.

## Phase 2: link to dubplates.net
- "Link this computer": the client shows a code, the user confirms it on dubplates.net, the client gets a device token.
- `dubplates://` links: "Make stems" on the site opens the client with the track.
- The mixer loads a `Stems` folder (browser folder picker), or the client uploads stems to the user's library.
- `dubplates.json` → `source.sha256` tells the site "this track has stems".

## Phase 3: model list from the site
- Admin edits the model list on dubplates.net. The client gets it with "Check for new models".
- The list is signed (Ed25519). The private key is only on the admin's PC, the public key is in the client.
  A hacked server can not push a bad model. Every model has a SHA-256.

## Phase 4: tools on stems
- [x] Effects chain per stem: bleed reduction, repair, gate, compression, EQ, filters, limiter, gain (0.1.7).
- [x] VST3 plugins in the chain (pedalboard), plugin window or sliders.
- [ ] De-comb (the old Stemmer's AI-upsampling comb cut).
- [ ] Effects on drum parts and on "more work" results; combine two models (ensemble).
- [ ] AU plugins on macOS.

## Drum tools (later)
Built on the drum parts from the chain (`stems[].parts` in `dubplates.json`):
- Hit detection per part (onsets, frequency peaks, velocity) → a hit list (`<part>.hits.json`, MIDI export).
- Replace or layer hits with a sample (kick / snare replace), keep timing and velocity.
- Clean a part between hits (gate from the hit list), re-balance parts, re-mix to a new drum stem.

## More ideas
- **Stream monitor:** watch the dubplates.net live stream (or the test stream) in a window on a second PC,
  with audio level meters, stream health (bitrate, dropped data, delay) and an alert when the stream stops.
- **Recording:** record a mix or a live set from an audio interface to WAV/FLAC, with automatic split and tags.
  Optional: record the dubplates.net mixer output in full quality (no browser limits).
- **Analysis:** BPM, key, beat grid, loudness (LUFS); write tags into files, export for DJ software.
- **Batch tools:** convert formats, normalize loudness, trim silence, re-tempo (time-stretch) a folder.
- **Library sync:** keep a local folder in sync with the user's dubplates.net library (download / upload).
- **Offload site work:** C2PA signing, watermark check, video renders of recordings done on the user's GPU.
