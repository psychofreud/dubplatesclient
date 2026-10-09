"""Effects on a stem: a chain of modules (clean-up, dynamics, tone) and VST3 plugins, rendered with pedalboard + numpy.

A chain is a list: [{"type": "gate", "on": true, "p": {...}}, {"type": "vst", "on": true, "path": "...", "name": "...",
"state": {param: value}}, ...]. Preview renders a short part; Apply renders the whole stem and replaces the file (the
original is kept in '<set>/.originals/' so it can come back).
"""
from __future__ import annotations

import json
import shutil
import sys
import threading
from pathlib import Path

import numpy as np
import soundfile as sf

# ---------- the modules: their knobs (the UI draws them from this) ----------
MODULES = {
    "bleed": {"title": "Bleed reduction", "text": "Pulls down the parts of this stem that are louder in the other stems.",
              "params": [["amount", "Amount", 0, 100, "%", 50], ["floor", "Floor", -60, -6, "dB", -30]],
              "presets": {"Light": {"amount": 30, "floor": -18}, "Medium": {"amount": 55, "floor": -30}, "Strong": {"amount": 85, "floor": -42}}},
    "repair": {"title": "Repair", "text": "De-noise (hiss, hum floor) and de-click.",
               "params": [["denoise", "De-noise", 0, 100, "%", 40], ["declick", "De-click", 0, 100, "%", 40], ["floor", "Floor", -40, -6, "dB", -20]],
               "presets": {"Light": {"denoise": 25, "declick": 25, "floor": -12}, "Medium": {"denoise": 55, "declick": 50, "floor": -20}, "Heavy": {"denoise": 90, "declick": 80, "floor": -30}}},
    "gate": {"title": "Gate", "text": "Turns the stem down between the hits or phrases.",
             "params": [["threshold", "Thresh", -80, 0, "dB", -45], ["range", "Range", -80, 0, "dB", -40], ["release", "Release", 10, 1000, "ms", 120]],
             "presets": {"Gentle": {"threshold": -50, "range": -20, "release": 250}, "Tight": {"threshold": -38, "range": -60, "release": 80}, "Drum hits": {"threshold": -30, "range": -80, "release": 40}}},
    "comp": {"title": "Compression", "text": "Evens out the level.",
             "params": [["threshold", "Thresh", -60, 0, "dB", -18], ["ratio", "Ratio", 1, 20, ":1", 3], ["attack", "Attack", 0.1, 100, "ms", 10], ["makeup", "Makeup", 0, 24, "dB", 3]],
             "presets": {"Glue": {"threshold": -20, "ratio": 2, "attack": 30, "makeup": 2}, "Vocal": {"threshold": -24, "ratio": 4, "attack": 5, "makeup": 6},
                         "Punch": {"threshold": -16, "ratio": 4, "attack": 25, "makeup": 4}, "Squash": {"threshold": -36, "ratio": 12, "attack": 1, "makeup": 12}}},
    "eq": {"title": "EQ", "text": "Four bands: low shelf, two peaks, high shelf.",
           "params": [["f1", "Low Hz", 20, 500, "Hz", 80], ["g1", "Low", -18, 18, "dB", 0], ["f2", "Mid 1 Hz", 100, 4000, "Hz", 400], ["g2", "Mid 1", -18, 18, "dB", 0],
                      ["f3", "Mid 2 Hz", 500, 12000, "Hz", 2500], ["g3", "Mid 2", -18, 18, "dB", 0], ["f4", "High Hz", 2000, 18000, "Hz", 10000], ["g4", "High", -18, 18, "dB", 0]],
           "presets": {"Flat": {"g1": 0, "g2": 0, "g3": 0, "g4": 0}, "Warmth": {"f1": 120, "g1": 3, "f2": 350, "g2": 1.5, "f3": 3000, "g3": -1.5, "f4": 9000, "g4": -2},
                       "Presence": {"f1": 90, "g1": -2, "f2": 350, "g2": -1.5, "f3": 3200, "g3": 4, "f4": 11000, "g4": 2.5}, "Air": {"g1": 0, "g2": 0, "f3": 5000, "g3": 1, "f4": 12000, "g4": 6},
                       "Scoop": {"f1": 90, "g1": 3, "f2": 500, "g2": -4, "f3": 2500, "g3": -1, "f4": 10000, "g4": 2}, "Telephone": {"f1": 300, "g1": -18, "f2": 1200, "g2": 6, "f3": 3000, "g3": 2, "f4": 3500, "g4": -18}}},
    "hpf": {"title": "High-pass", "text": "Removes rumble below the cut.", "params": [["freq", "Cut", 20, 1000, "Hz", 40]], "presets": {"Rumble": {"freq": 35}, "Vocal": {"freq": 90}, "Thin": {"freq": 250}}},
    "lpf": {"title": "Low-pass", "text": "Removes hiss and air above the cut.", "params": [["freq", "Cut", 1000, 20000, "Hz", 16000], ], "presets": {"Soft": {"freq": 14000}, "Dark": {"freq": 6000}, "Sub": {"freq": 1200}}},
    "limit": {"title": "Limiter", "text": "Stops peaks above the ceiling.", "params": [["ceiling", "Ceiling", -12, 0, "dB", -1], ["release", "Release", 10, 1000, "ms", 100]], "presets": {}},
    "gain": {"title": "Gain", "text": "Louder or quieter.", "params": [["db", "Gain", -24, 24, "dB", 0]], "presets": {}},
}
ORDER = ["bleed", "repair", "hpf", "gate", "comp", "eq", "lpf", "limit", "gain"]
CHAINS = {
    "Natural cleanup": [("repair", "Light"), ("bleed", "Light"), ("comp", "Glue")],
    "Vocal polish": [("repair", "Medium"), ("bleed", "Medium"), ("hpf", "Vocal"), ("gate", "Gentle"), ("comp", "Vocal"), ("eq", "Presence")],
    "Tight drums": [("gate", "Drum hits"), ("bleed", "Medium"), ("comp", "Punch"), ("eq", "Scoop")],
    "Solid bass": [("bleed", "Strong"), ("comp", "Squash"), ("eq", "Warmth"), ("lpf", "Sub")],
    "Wide & airy": [("comp", "Glue"), ("eq", "Air")],
    "Lo-fi": [("eq", "Telephone"), ("comp", "Squash")],
}
SUGGEST = {"vocals": "Vocal polish", "drums": "Tight drums", "bass": "Solid bass", "other": "Wide & airy", "instrumental": "Natural cleanup"}


def module(kind: str, preset: str | None = None) -> dict:
    m = MODULES[kind]
    p = {k: d for k, _, _, _, _, d in m["params"]}
    if preset:
        p.update(m["presets"].get(preset, {}))
    return {"type": kind, "on": True, "p": p}


def chain_preset(name: str) -> list[dict]:
    return [module(k, pr) for k, pr in CHAINS[name]]


def catalog() -> dict:
    return {"modules": MODULES, "order": ORDER, "chains": list(CHAINS), "suggest": SUGGEST}


# ---------- VST3 ----------
def vst_dirs() -> list[Path]:
    if sys.platform == "win32":
        return [Path(r"C:\Program Files\Common Files\VST3")]
    if sys.platform == "darwin":
        return [Path("/Library/Audio/Plug-Ins/VST3"), Path.home() / "Library/Audio/Plug-Ins/VST3"]
    return [Path("/usr/lib/vst3"), Path.home() / ".vst3"]


def scan_vst() -> list[dict]:
    """The VST3 plugins on this computer: [{name, path}] (a .vst3 inside a folder like 'Kilohearts' too)."""
    out = []
    for d in vst_dirs():
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.vst3"), key=lambda x: x.name.lower()):
            if any(q.suffix.lower() == ".vst3" for q in p.parents):
                continue                                    # (the inside of a .vst3 bundle)
            out.append({"name": p.stem, "path": str(p)})
    return out


_vst_cache: dict[str, object] = {}
_vst_lock = threading.Lock()


def load_vst(path: str):
    from pedalboard import load_plugin
    with _vst_lock:
        if path not in _vst_cache:
            _vst_cache[path] = load_plugin(path)
        return _vst_cache[path]


def vst_params(path: str) -> dict:
    """The plugin's parameters for the UI: {name: {value, min, max, label}} (numbers only)."""
    pl = load_vst(path)
    out = {}
    for k, prm in pl.parameters.items():
        try:
            v = getattr(pl, k)
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                out[k] = {"value": float(v), "min": float(prm.min_value) if prm.min_value is not None else 0.0,
                          "max": float(prm.max_value) if prm.max_value is not None else 1.0, "label": prm.label or ""}
        except Exception:  # noqa: BLE001
            continue
    return out


def vst_editor(path: str, state: dict) -> dict:
    """Opens the plugin's own window (blocks until the user closes it); returns the new parameter values."""
    pl = load_vst(path)
    _set_state(pl, state)
    pl.show_editor()
    return {k: v["value"] for k, v in vst_params(path).items()}


def _set_state(pl, state: dict):
    for k, v in (state or {}).items():
        try:
            setattr(pl, k, v)
        except Exception:  # noqa: BLE001
            pass


# ---------- the DSP of our own modules ----------
def _db(x):
    return 10 ** (x / 20)


def _env(mono: np.ndarray, sr: int, ms: float = 10) -> np.ndarray:
    """A level envelope (RMS over ms)."""
    n = max(1, int(sr * ms / 1000))
    p = np.convolve(mono.astype(np.float64) ** 2, np.ones(n) / n, mode="same")
    return np.sqrt(p).astype(np.float32)


def _smooth_gain(g: np.ndarray, sr: int, attack_ms: float, release_ms: float) -> np.ndarray:
    """Gain curve with attack (falls) / release (rises) times: a one-pole filter on 1-ms steps (fast in numpy)."""
    step = max(1, sr // 1000)
    gs = g[::step].astype(np.float64)
    a_up = np.exp(-1 / max(1, release_ms))          # per ms
    a_dn = np.exp(-1 / max(0.1, attack_ms))
    out = np.empty_like(gs)
    y = gs[0] if len(gs) else 1.0
    for i, x in enumerate(gs):                      # (one value per ms: 300 000 for 5 minutes)
        a = a_dn if x < y else a_up
        y = a * y + (1 - a) * x
        out[i] = y
    return np.interp(np.arange(len(g)), np.arange(len(gs)) * step, out).astype(np.float32)


def gate(x: np.ndarray, sr: int, p: dict) -> np.ndarray:
    env = _env(x.mean(axis=0), sr, 5)
    g = np.where(env > _db(p["threshold"]), 1.0, _db(p["range"])).astype(np.float32)
    return x * _smooth_gain(g, sr, 1.0, p["release"])


def _stft_blocks(x: np.ndarray, sr: int, fn, n_fft: int = 2048, hop: int = 512, block_s: float = 20.0):
    """Runs fn(spectra[ch, f, t], block) on blocks of ~20 s (low memory) and adds them back with overlap."""
    from scipy.signal import istft, stft
    n = x.shape[1]
    blk = int(block_s * sr)
    pad = n_fft * 4
    out = np.zeros_like(x)
    w = np.zeros(n, np.float32)
    start = 0
    while start < n:
        a, b = max(0, start - pad), min(n, start + blk + pad)
        _, _, Z = stft(x[:, a:b], fs=sr, nperseg=n_fft, noverlap=n_fft - hop)
        Z = fn(Z, (a, b))
        _, y = istft(Z, fs=sr, nperseg=n_fft, noverlap=n_fft - hop)
        y = y[:, :b - a]
        # fade the overlaps (raised cosine), then add
        ramp = np.ones(b - a, np.float32)
        if a > 0:
            ramp[:2 * pad] = np.sin(np.linspace(0, np.pi / 2, 2 * pad)) ** 2
        if b < n:
            ramp[-2 * pad:] = np.minimum(ramp[-2 * pad:], np.cos(np.linspace(0, np.pi / 2, 2 * pad)) ** 2)
        out[:, a:b] += y[:, :b - a] * ramp
        w[a:b] += ramp
        start += blk
    return out / np.maximum(w, 1e-6)


def repair(x: np.ndarray, sr: int, p: dict) -> np.ndarray:
    y = x.copy()
    if p["declick"] > 0:                             # clicks: single samples far above their neighbours
        k = 12 - 9 * p["declick"] / 100
        for c in range(y.shape[0]):
            d = np.abs(np.diff(y[c], prepend=y[c, 0]))
            med = np.median(d) + 1e-9
            bad = np.where(d > k * med * 8)[0]
            bad = bad[(bad > 2) & (bad < len(y[c]) - 3)]
            for i in bad[:20000]:
                y[c, i - 1:i + 2] = np.linspace(y[c, i - 2], y[c, i + 2], 3)
    if p["denoise"] > 0:                             # noise: a spectral gate from the quietest 10 % of the frames
        amt, floor = p["denoise"] / 100, _db(p["floor"])

        def fn(Z, _):
            mag = np.abs(Z)
            frame = mag.mean(axis=(0, 1))
            quiet = mag[:, :, frame <= np.percentile(frame, 5)]      # the noise floor: the quietest 5 % of the frames
            noise = (quiet.mean(axis=2, keepdims=True) if quiet.shape[2] else mag.min(axis=2, keepdims=True)) * (0.6 + 1.4 * amt)
            g = np.clip((mag ** 2 - noise ** 2) / np.maximum(mag ** 2, 1e-12), floor ** 2, 1.0) ** 0.5   # (Wiener-like: soft)
            return Z * g
        y = _stft_blocks(y, sr, fn)
    return y.astype(np.float32)


def bleed(x: np.ndarray, sr: int, p: dict, others: list[np.ndarray]) -> np.ndarray:
    """Soft mask: where the other stems are louder than this one, pull this one down (to the floor)."""
    if not others:
        return x
    amt, floor = p["amount"] / 100, _db(p["floor"])
    from scipy.signal import stft

    def fn(Z, ab):
        a, b = ab
        mine = np.abs(Z).mean(axis=0) ** 2
        rest = np.zeros_like(mine)
        for o in others:
            seg = o[:, a:b]
            if seg.shape[1] < b - a:
                seg = np.pad(seg, ((0, 0), (0, b - a - seg.shape[1])))
            _, _, Zo = stft(seg, fs=sr, nperseg=2048, noverlap=2048 - 512)
            rest += np.abs(Zo[:, :, :mine.shape[1]]).mean(axis=0) ** 2
        mask = mine / (mine + rest + 1e-12)
        g = np.clip(mask ** (amt * 2), floor, 1.0)
        return Z * g[None]
    return _stft_blocks(x, sr, fn).astype(np.float32)


def limit(x: np.ndarray, sr: int, p: dict) -> np.ndarray:
    """Peak limiter: the gain drops at once where a peak would go over the ceiling, and comes back with the release."""
    from scipy.ndimage import maximum_filter1d
    c = _db(p["ceiling"])
    peak = maximum_filter1d(np.abs(x).max(axis=0), size=max(1, sr // 500))      # (2 ms look around)
    g = np.minimum(1.0, c / np.maximum(peak, 1e-9)).astype(np.float32)
    step = max(1, sr // 1000)
    gmin = np.minimum.reduceat(g, np.arange(0, len(g), step))
    out, y, a = np.empty_like(gmin), 1.0, np.exp(-1 / max(1, p["release"]))
    for i, v in enumerate(gmin):
        y = v if v < y else a * y + (1 - a) * v
        out[i] = y
    gs = np.repeat(out, step)[:len(g)]
    return np.clip(x * np.minimum(gs, g), -c, c)


def _pb(mod: dict):
    from pedalboard import (Compressor, Gain, HighpassFilter, HighShelfFilter, LowpassFilter, LowShelfFilter, PeakFilter)
    t, p = mod["type"], mod["p"]
    if t == "comp":
        return [Compressor(threshold_db=p["threshold"], ratio=p["ratio"], attack_ms=p["attack"], release_ms=120), Gain(gain_db=p["makeup"])]
    if t == "eq":
        return [LowShelfFilter(cutoff_frequency_hz=p["f1"], gain_db=p["g1"], q=0.7), PeakFilter(cutoff_frequency_hz=p["f2"], gain_db=p["g2"], q=1.0),
                PeakFilter(cutoff_frequency_hz=p["f3"], gain_db=p["g3"], q=1.0), HighShelfFilter(cutoff_frequency_hz=p["f4"], gain_db=p["g4"], q=0.7)]
    if t == "hpf":
        return [HighpassFilter(cutoff_frequency_hz=p["freq"])]
    if t == "lpf":
        return [LowpassFilter(cutoff_frequency_hz=p["freq"])]
    if t == "limit":
        return []                                   # (our own limiter: see limit(); JUCE's adds make-up gain)
    if t == "gain":
        return [Gain(gain_db=p["db"])]
    return []


def process(x: np.ndarray, sr: int, chain: list[dict], others: list[np.ndarray] | None = None, report=None) -> np.ndarray:
    """x: [channels, samples] float32. Runs the chain in order (switched-off modules are skipped)."""
    from pedalboard import Pedalboard
    live = [m for m in chain if m.get("on", True)]
    for i, m in enumerate(live):
        if report:
            report(i / max(1, len(live)), MODULES.get(m["type"], {}).get("title") or m.get("name", "VST"))
        t = m["type"]
        if t == "gate":
            x = gate(x, sr, m["p"])
        elif t == "repair":
            x = repair(x, sr, m["p"])
        elif t == "limit":
            x = limit(x, sr, m["p"])
        elif t == "bleed":
            x = bleed(x, sr, m["p"], others or [])
        elif t == "vst":
            pl = load_vst(m["path"])
            _set_state(pl, m.get("state"))
            pl.reset()
            x = pl(x, sr)
        else:
            x = Pedalboard(_pb(m))(x, sr)
    return np.nan_to_num(x).astype(np.float32)


def read(path: Path, start: float = 0, dur: float | None = None):
    info = sf.info(str(path))
    a = int(start * info.samplerate)
    n = -1 if dur is None else int(dur * info.samplerate)
    x, sr = sf.read(str(path), start=a, frames=n, dtype="float32", always_2d=True)
    return x.T.copy(), sr, info


def others_of(folder: Path, meta: dict, stem: str, start: float = 0, dur: float | None = None) -> list[np.ndarray]:
    out = []
    for s in meta["stems"]:
        if s["name"].lower() != stem.lower():
            f = folder / s["file"]
            orig = folder / ".originals" / Path(s["file"]).name     # (bleed works on the stems as the model made them)
            out.append(read(orig if orig.exists() else f, start, dur)[0])
    return out


def write_like(path: Path, x: np.ndarray, sr: int, info):
    """Writes x in the same format as the stem (FLAC / WAV: same subtype; MP3: via the engine's format)."""
    ext = path.suffix.lower()
    peak = float(np.abs(x).max()) if x.size else 0
    if peak > 1.0:
        x = x / peak * 0.999                         # (no clipping in the file)
    if ext in (".flac", ".wav"):
        st = info.subtype if info.subtype in ("PCM_16", "PCM_24") else "PCM_24"
        sf.write(str(path), x.T, sr, subtype=st)
    else:
        from pedalboard.io import AudioFile
        with AudioFile(str(path), "w", sr, x.shape[0], quality=320) as f:
            f.write(x)


def stem_paths(folder: Path, meta: dict, stem: str) -> tuple[Path, Path]:
    s = next((s for s in meta["stems"] if s["name"].lower() == stem.lower()), None)
    if not s:
        raise ValueError(f"No stem “{stem}”")
    f = folder / s["file"]
    return f, folder / ".originals" / f.name


def preview(folder: Path, stem: str, chain: list[dict], start: float, dur: float, out: Path) -> str:
    """The stem from start, dur seconds long, through the chain (from the ORIGINAL stem: the chain replaces, it does
    not add up). Written to out (WAV)."""
    meta = json.loads((folder / "dubplates.json").read_text(encoding="utf-8"))
    f, orig = stem_paths(folder, meta, stem)
    x, sr, _ = read(orig if orig.exists() else f, start, dur)
    y = process(x, sr, chain, others_of(folder, meta, stem, start, dur) if any(m["type"] == "bleed" and m.get("on", True) for m in chain) else None)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), y.T, sr, subtype="PCM_16")
    return str(out)


def apply(folder: Path, stem: str, chain: list[dict], report=None) -> dict:
    """Renders the whole stem through the chain and replaces the file. The first time, the original goes to
    .originals/ (Restore puts it back). The chain is saved in dubplates.json (stem.fx)."""
    meta_p = folder / "dubplates.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    f, orig = stem_paths(folder, meta, stem)
    if not orig.exists():
        orig.parent.mkdir(exist_ok=True)
        shutil.copy2(f, orig)
    x, sr, info = read(orig)
    others = others_of(folder, meta, stem) if any(m["type"] == "bleed" and m.get("on", True) for m in chain) else None
    y = process(x, sr, chain, others, report)
    tmp = f.with_name(f.stem + ".fx-tmp" + f.suffix)
    write_like(tmp, y, sr, sf.info(str(orig)))
    tmp.replace(f)
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    s = next(s for s in meta["stems"] if s["name"].lower() == stem.lower())
    s["fx"] = chain
    meta_p.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"file": str(f)}


def restore(folder: Path, stem: str) -> dict:
    meta_p = folder / "dubplates.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    f, orig = stem_paths(folder, meta, stem)
    if not orig.exists():
        raise ValueError("No original copy of this stem")
    shutil.copy2(orig, f)
    s = next(s for s in meta["stems"] if s["name"].lower() == stem.lower())
    s.pop("fx", None)
    meta_p.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"file": str(f)}
