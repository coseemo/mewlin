#!/usr/bin/env python3
"""build_assets.py - dai fogli generati (sfondo magenta) agli asset di Mewlin Pomodoro.

Uso:  python build_assets.py [cartella_raw] [cartella_assets] [--tol 130] [--grid cat_idle=3x2]

Metti in ./raw i file con QUESTI nomi (png/jpg/webp):
  cat_idle, cat_study, cauldron, cat_break   fogli 3x2 (6 frame)      -> GIF
  bat                                        foglio 4x1 (4 frame)     -> GIF
  plate, button, panel                       immagine singola         -> PNG
  scene_bg                                   sfondo pieno (senza magenta) -> PNG
  scene_bg_sheet                             sfondo ANIMATO: foglio 3x2 (6 frame, opaco) -> scene_bg.gif
  icons                                      foglio 4x2 (7 icone, ordine: book, reset, gear, prev, next, play, pause)
Per ogni foglio: toglie il magenta, RIALLINEA i frame sulla parte ferma (--align auto), li ritaglia con lo STESSO riquadro,
riduce a media di area e rimappa i colori alla PALETTE, poi salva in ./assets con i nomi che l'app si aspetta.
Dipendenze:  sudo pacman -S python-pillow python-numpy
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image

PALETTE = """#0a0713 #0f0a1a #150f22 #241a3c #33264a #4a3a78 #5a4690 #2e2150 #2a1d4a #1a1230 #7a62b8
#8f8cb4 #cfcce6 #f2e6c8 #f7f3ff #14121f #25223a #3d3960 #6a64a0 #4a2890 #6d3fc0 #8e5fd8
#8a6a1a #f3c969 #fff2b8 #1f6a2c #3fa43a #5fe06a #b6ff8a #e58fb0 #ff9ab8 #8a2d3b #ff7a8a
#ff6a2a #ffd25a #1b2a66 #3b5bd0 #e8c43a #9ac23a #54428a""".split()
PAL = np.array([[int(h[i:i + 2], 16) for i in (1, 3, 5)] for h in PALETTE], dtype=np.int32)

# nome: (colonne, righe, larghezza max, altezza max, ms per frame)
SHEETS = {"cat_idle": (3, 2, 160, 102, 250), "cat_study": (3, 2, 190, 120, 160), "cauldron": (3, 2, 82, 77, 140),
          "cat_break": (3, 2, 85, 65, 90), "bat": (4, 1, 28, 20, 80)}
SINGLE = {"plate": (200, 58), "button": (62, 23), "panel": (200, 56)}
ICONS = ["icon_book", "icon_reset", "icon_gear", "icon_prev", "icon_next", "icon_play", "icon_pause"]
ICON_SIZE = {"icon_play": 22, "icon_pause": 22}   # gli altri 14
BG = (200, 150)


def load(raw, name):
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        f = raw / (name + ext)
        if f.exists(): return Image.open(f).convert("RGBA")
    return None

def key_magenta(img, tol):
    a = np.array(img); r, g, b = (a[..., i].astype(int) for i in range(3))
    mag = (r > 170) & (b > 170) & (((r + b) // 2 - g) > tol)
    a[..., 3] = np.where(mag, 0, a[..., 3]); return Image.fromarray(a)

def union_box(frames):
    box = None
    for f in frames:
        bb = f.getchannel("A").getbbox()
        if bb: box = bb if box is None else (min(box[0], bb[0]), min(box[1], bb[1]), max(box[2], bb[2]), max(box[3], bb[3]))
    return box

def fit(w, h, mw, mh):
    k = min(mw / w, mh / h); return max(1, round(w * k)), max(1, round(h * k))

OPT = {"palette": "adaptive", "colors": 48}

def snap(a, pal):
    """alfa binario + ogni pixel al colore piu' vicino della palette; ritorna (RGBA, indici)"""
    a = a.copy(); a[..., 3] = np.where(a[..., 3] >= 128, 255, 0)
    d = ((a[..., :3].astype(np.int32).reshape(-1, 1, 3) - pal[None]) ** 2).sum(2)
    idx = d.argmin(1).reshape(a.shape[:2]); a[..., :3] = pal[idx].astype(np.uint8)
    return a, np.where(a[..., 3] > 0, idx + 1, 0).astype(np.uint8)

def make_palette(arrs, n):
    """palette adattiva (colori reali dei tuoi disegni, uguale per tutti i frame) oppure quella fissa PALETTE"""
    if OPT["palette"] == "fixed": return PAL
    px = np.concatenate([a[..., :3][a[..., 3] >= 128] for a in arrs])
    if len(px) == 0: return PAL
    if len(px) > 200000: px = px[np.random.RandomState(0).choice(len(px), 200000, replace=False)]
    q = Image.fromarray(px.reshape(1, -1, 3).astype(np.uint8)).quantize(colors=n, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    used = sorted(set(np.array(q).ravel().tolist()))
    return np.array(q.getpalette()[:3 * n]).reshape(-1, 3)[used].astype(np.int32)

def finish(arrs, n=None):
    pal = make_palette(arrs, n or OPT["colors"]); return [snap(a, pal) for a in arrs], pal

def shrink(img, size): return np.array(img.resize(size, Image.BOX))

def save_png(a, path): Image.fromarray(a).save(path)

def save_gif(items, path, ms, palette):
    pal = [255, 0, 255] + [c for rgb in palette for c in rgb]; pal += [0] * (768 - len(pal))
    frames = []
    for _, idx in items:
        im = Image.fromarray(idx, "P"); im.putpalette(pal); frames.append(im)
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=ms, loop=0, transparency=0, disposal=2)

def align_frames(frames, maxfrac=.15):
    """Riallinea i frame sulla parte che non si muove (correlazione delle sagome), cosi' le altezze/posizioni tornano."""
    w, h = frames[0].size; m = max(2, int(maxfrac * min(w, h)))
    cur = [(np.array(f.getchannel("A")) > 0).astype(np.float32) for f in frames]; tot = [[0, 0] for _ in frames]
    ys, xs = np.arange(-m, m + 1) % h, np.arange(-m, m + 1) % w
    for it in range(2):
        ref = cur[0] if it == 0 else np.median(np.stack(cur), 0); F = np.fft.rfft2(ref)
        for i in range(len(cur)):
            cc = np.fft.irfft2(F * np.conj(np.fft.rfft2(cur[i])), s=(h, w))
            iy, ix = np.unravel_index(cc[np.ix_(ys, xs)].argmax(), (2 * m + 1, 2 * m + 1)); dy, dx = iy - m, ix - m
            cur[i] = np.roll(cur[i], (dy, dx), (0, 1)); tot[i][0] += dy; tot[i][1] += dx
    out = []
    for f, (dy, dx) in zip(frames, tot):
        c = Image.new("RGBA", f.size, (0, 0, 0, 0)); c.paste(f, (dx, dy)); out.append(c)
    return out

def cover43(img, fx=.5):
    """ritaglio 4:3; fx = 0 sinistra ... 1 destra (quale parte di una stanza larga tenere)"""
    w, h = img.size; tw = min(w, int(h * BG[0] / BG[1])); th = int(tw * BG[1] / BG[0]); x0 = int((w - tw) * fx); y0 = (h - th) // 2
    return img.crop((x0, y0, x0 + tw, y0 + th))

def cells(img, cols, rows):
    cw, ch = img.width // cols, img.height // rows
    return [img.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch)) for r in range(rows) for c in range(cols)]

def preview(out, imgs):
    scale, W = 3, 1300; pos, x, y, rowh = [], 8, 8, 0
    for im in imgs:
        w, h = im.width * scale, im.height * scale
        if x + w > W - 8: x, y, rowh = 8, y + rowh + 8, 0
        pos.append((x, y)); x += w + 8; rowh = max(rowh, h)
    canvas = Image.new("RGBA", (W, y + rowh + 8), (21, 15, 34, 255))
    for im, p in zip(imgs, pos): canvas.alpha_composite(im.resize((im.width * scale, im.height * scale), Image.NEAREST), p)
    canvas.save(out / "_preview.png")


def main():
    ap = argparse.ArgumentParser(description="fogli magenta -> assets di Mewlin Pomodoro")
    ap.add_argument("raw", nargs="?", default="raw"); ap.add_argument("out", nargs="?", default="assets")
    ap.add_argument("--tol", type=int, default=130, help="tolleranza magenta (piu' basso = toglie di piu')")
    ap.add_argument("--grid", action="append", default=[], help="es. cat_idle=3x2")
    ap.add_argument("--align", choices=["auto", "none"], default="auto", help="auto = riallinea i frame (default)")
    ap.add_argument("--palette", choices=["adaptive", "fixed"], default="adaptive", help="adaptive = usa i colori dei tuoi disegni (default)")
    ap.add_argument("--colors", type=int, default=48, help="colori per sprite/GIF")
    ap.add_argument("--bg-colors", type=int, default=72, help="colori per lo sfondo")
    ap.add_argument("--bg-x", type=float, default=.5, help="sfondo largo: 0=tieni la sinistra, 1=la destra")
    o = ap.parse_args(); raw, out = Path(o.raw), Path(o.out); out.mkdir(exist_ok=True)
    grids = {k: tuple(map(int, v.lower().split("x"))) for k, v in (g.split("=") for g in o.grid)}
    OPT["palette"], OPT["colors"] = o.palette, o.colors
    shown, done = [], 0

    for name, (cols, rows, mw, mh, ms) in SHEETS.items():
        img = load(raw, name)
        if img is None: print(f"- {name}: non trovato in {raw}/, salto"); continue
        cols, rows = grids.get(name, (cols, rows))
        fr = [f for f in cells(key_magenta(img, o.tol), cols, rows) if f.getchannel("A").getbbox()]
        if not fr: print(f"! {name}: nessun frame (sfondo non magenta?)"); continue
        if o.align == "auto" and len(fr) > 1: fr = align_frames(fr)
        box = union_box(fr); fr = [f.crop(box) for f in fr]
        size = fit(fr[0].width, fr[0].height, mw, mh); items, pal = finish([shrink(f, size) for f in fr])
        save_gif(items, out / f"{name}.gif", ms, pal); shown.append(Image.fromarray(items[0][0])); done += 1
        print(f"+ {name}.gif  {len(items)} frame  {size[0]}x{size[1]}")

    for name, (mw, mh) in SINGLE.items():
        img = load(raw, name)
        if img is None: print(f"- {name}: non trovato, salto"); continue
        img = key_magenta(img, o.tol); img = img.crop(img.getchannel("A").getbbox())
        size = fit(img.width, img.height, mw, mh); a = finish([shrink(img, size)])[0][0][0]
        save_png(a, out / f"{name}.png"); shown.append(Image.fromarray(a)); done += 1; print(f"+ {name}.png  {size[0]}x{size[1]}")

    sheet = load(raw, "scene_bg_sheet")
    if sheet is not None:
        cols, rows = grids.get("scene_bg_sheet", (3, 2))
        items, pal = finish([shrink(cover43(c, o.bg_x), BG) for c in cells(sheet, cols, rows)], o.bg_colors)
        save_gif(items, out / "scene_bg.gif", 200, pal); shown.append(Image.fromarray(items[0][0])); done += 1
        print(f"+ scene_bg.gif  {len(items)} frame  {BG[0]}x{BG[1]}")
    img = None if sheet is not None else load(raw, "scene_bg")
    if img is None and sheet is None: print("- scene_bg: non trovato, salto")
    elif img is None: pass
    else:
        img = cover43(img.convert("RGB").convert("RGBA"), o.bg_x)   # ritaglio 4:3
        a = finish([shrink(img, BG)], o.bg_colors)[0][0][0]; save_png(a, out / "scene_bg.png"); shown.append(Image.fromarray(a)); done += 1
        print(f"+ scene_bg.png  {BG[0]}x{BG[1]}")

    img = load(raw, "icons")
    if img is None: print("- icons: non trovato, salto")
    else:
        cl = cells(key_magenta(img, o.tol), *grids.get("icons", (4, 2)))
        for name, c in zip(ICONS, cl):
            bb = c.getchannel("A").getbbox()
            if not bb: print(f"! {name}: cella vuota"); continue
            c = c.crop(bb); S = ICON_SIZE.get(name, 14); size = fit(c.width, c.height, S, S)
            a = finish([shrink(c, size)])[0][0][0]; canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            canvas.paste(Image.fromarray(a), ((S - size[0]) // 2, (S - size[1]) // 2))
            canvas.save(out / f"{name}.png"); shown.append(canvas); done += 1; print(f"+ {name}.png  {S}x{S}")

    if shown: preview(out, shown); print(f"\nFatto: {done} file in {out}/  (controlla {out}/_preview.png)")


if __name__ == "__main__":
    main()
