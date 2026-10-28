#!/usr/bin/env python3
"""Mewlin Pomodoro v3 - pixel art a slot: metti GIF/PNG in ./assets, notifiche via ntfy."""
import sys, json, math, time, wave, shutil, subprocess, tempfile, secrets, threading, urllib.request
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QRectF, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QPainterPath, QPixmap, QMovie, QFontDatabase, QRadialGradient
from PyQt6.QtWidgets import QApplication, QWidget, QInputDialog

W, H = 440, 690
HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
CFG = Path.home() / ".config/mewlin-pomodoro/config.json"
TMP = Path(tempfile.gettempdir())
LOG = TMP / "mewlin_mpv.log"
DEFAULT = {"v": 3, "cycles": 4, "study": 25, "rest": 5, "channel": 0,
           "ntfy_on": False, "ntfy_server": "https://ntfy.sh", "ntfy_topic": "",
           "channels": [["Lofi Girl", "https://www.youtube.com/@LofiGirl/live"],
                        ["Chillhop", "https://www.youtube.com/@ChillhopMusic/live"],
                        ["Synthwave", "https://www.youtube.com/watch?v=4xDzrJKXOOY"]]}
LIMITS = {"cycles": (1, 12, 1), "study": (5, 120, 5), "rest": (1, 30, 1)}
PREP = 5
DEF_SPEED = 60   # velocita' predefinita delle GIF (%); si regola dal vivo con L
# margini interni (frazioni di larghezza/altezza) dove stanno i testi, per cornici decorate. Modificabili in assets/layout.json
INSET = {"plate": (.13, .16, .13, .16), "panel": (.09, .16, .09, .16), "button": (.08, .12, .08, .12)}
GOLD, PINK, GREENL, PINKL, PARCH, MUTED, INK = "#f3c969", "#ff9ab8", "#9bf08a", "#ff9ec0", "#f2e6c8", "#9d93c4", "#120c1c"
FAM = ["Pixelify Sans", "Press Start 2P", "Silkscreen", "VT323", "DejaVu Sans Mono", "Monospace"]
CENTER, LEFT = Qt.AlignmentFlag.AlignCenter, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

# nome: (x, y, w, h, ancoraggio, colore placeholder, descrizione). x,y,w,h = area massima in pixel finestra.
SLOTS = {
    "scene_bg": (20, 20, 400, 300, "c", "#6a5acd", "sfondo stanza: muro, pavimento, finestra, mensola"),
    "cat_idle": (60, 110, 320, 205, "b", "#8f8cb4", "gatto stregone che dorme sul pavimento"),
    "cat_study": (20, 70, 380, 245, "b", "#5fe06a", "gatto che legge + pentolone con pozione, tutto in una GIF (es. 190x120)"),
    "cauldron": (235, 160, 165, 155, "b", "#3fa43a", "OPZIONALE: pentolone separato (non serve se e' gia' dentro cat_study)"),
    "cat_break": (0, 0, 170, 130, "b", "#ff9ab8", "gatto che corre/insegue (il codice lo sposta e lo specchia)"),
    "bat": (0, 0, 56, 40, "c", "#9a82d8", "pipistrello (il codice ne fa volare 3)"),
    "plate": (20, 346, 400, 116, "c", "#d9b45a", "cornice del contatore (il testo lo scrive il codice)"),
    "button": (0, 0, 124, 46, "c", "#7a62b8", "sfondo dei bottoni cicli/reset/opzioni"),
    "panel": (20, 548, 400, 112, "c", "#5a4690", "pannello del player musicale"),
    "icon_book": (0, 0, 28, 28, "c", "#c06aff", "icona cicli"), "icon_reset": (0, 0, 28, 28, "c", "#c06aff", "icona reset"),
    "icon_gear": (0, 0, 28, 28, "c", "#c06aff", "icona opzioni"), "icon_play": (0, 0, 44, 44, "c", "#5fe06a", "tasto play"),
    "icon_pause": (0, 0, 44, 44, "c", "#5fe06a", "tasto pausa"), "icon_prev": (0, 0, 28, 28, "c", "#c06aff", "canale precedente"),
    "icon_next": (0, 0, 28, 28, "c", "#c06aff", "canale successivo"),
    "icon_skip": (0, 0, 28, 28, "c", "#c06aff", "salta alla fine della fase (freccia verso destra)"),
}


# ---------- helper ----------
def C(c): return c if isinstance(c, QColor) else QColor(c)
def A(c, a): q = QColor(c); q.setAlpha(a); return q

def poly(p, pts, color, line=None, w=2):
    pa = QPainterPath(); pa.moveTo(*pts[0])
    for q in pts[1:]: pa.lineTo(*q)
    pa.closeSubpath(); p.setBrush(QBrush(C(color)))
    p.setPen(QPen(C(line), w) if line else Qt.PenStyle.NoPen); p.drawPath(pa)

def txt(p, s, x, y, w, h, size, c, bold=True, sp=0, al=CENTER, fit=True):
    f = QFont(); f.setFamilies(FAM); f.setBold(bold); f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, sp)
    size = max(7, int(size)); f.setPixelSize(size)
    while fit and size > 7 and QFontMetrics(f).horizontalAdvance(str(s)) > w - 2:
        size -= 1; f.setPixelSize(size)
    p.setFont(f); p.setPen(C(c)); p.drawText(QRectF(x, y, w, h), al, str(s))

def pbox(p, x, y, w, h, fillc, border, c=4, bw=3):
    """riquadro pixel: angoli smussati a gradino, bordo, luce in alto"""
    ch = lambda x, y, w, h, c: [(x + c, y), (x + w - c, y), (x + w, y + c), (x + w, y + h - c),
                                (x + w - c, y + h), (x + c, y + h), (x, y + h - c), (x, y + c)]
    poly(p, ch(x, y, w, h, c), border); poly(p, ch(x + bw, y + bw, w - 2 * bw, h - 2 * bw, max(1, c - 2)), fillc)
    p.fillRect(QRectF(x + bw + c, y + bw, w - 2 * bw - 2 * c, 2), A("#ffffff", 45))

def rect(p, x, y, w, h, c): p.fillRect(QRectF(x, y, w, h), C(c))

def stroke(p, path, c, w):
    p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(C(c), w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap)); p.drawPath(path)


# ---------- asset ----------
class Asset:
    def __init__(s, name):
        s.mov = s.pix = s.ref = None
        for ext in (".gif", ".webp", ".apng", ".png"):
            f = ASSETS / (name + ext)
            if not f.exists(): continue
            if ext == ".png":
                s.pix = QPixmap(str(f)); s.ref = s.pix.size() if not s.pix.isNull() else None
            else:
                m = QMovie(str(f)); m.setCacheMode(QMovie.CacheMode.CacheAll)
                if m.isValid():
                    w = h = 0
                    for i in range(max(1, m.frameCount())):   # canvas = il frame piu' grande, cosi' le posizioni restano fisse
                        m.jumpToFrame(i); pm = m.currentPixmap(); w, h = max(w, pm.width()), max(h, pm.height())
                    m.jumpToFrame(0); s.mov = m; s.ref = QSize(w, h) if w else None; m.start()
            break

    def pixmap(s):
        pm = s.mov.currentPixmap() if s.mov else s.pix
        return None if pm is None or pm.isNull() else pm


README = """MEWLIN POMODORO - cartella assets
Metti qui GIF (anche .webp/.apng animati) o .png con questi nomi. Se un file manca, l'app mostra un placeholder.
Le immagini vengono ingrandite solo di multipli interi (x2, x3...) per restare nitide: disegnale piccole!
Sfondo trasparente consigliato per tutto tranne scene_bg. Opzionale: font.ttf (font pixel per i testi).

nome (area massima in pixel finestra) - cosa deve mostrare
"""

def write_readme():
    ASSETS.mkdir(exist_ok=True)
    body = README + "".join(f"{n}  ({v[2]}x{v[3]}, es. {v[2] // 4}x{v[3] // 4} -> x4) - {v[6]}\n" for n, v in SLOTS.items())
    body += """
EDITOR POSIZIONI: premi L nell'app. N = prossimo elemento, frecce = sposta (Shift = 5px), + / - = ingrandimento,
, / . = velocita' animazione, H = nascondi/mostra (es. cauldron se e' gia' dentro cat_study), R = azzera l'elemento, L = salva (assets/layout.json) ed esci.
In layout.json puoi anche cambiare "inset": [sx, alto, dx, basso] (frazioni) per i margini dei testi in plate/panel/button.
"""
    (ASSETS / "README.txt").write_text(body)


# ---------- suoni ----------
def make_meow(path, lo, span, dur, form):
    sr = 22050; n = int(sr * dur); ph = 0.0; buf = bytearray()
    for i in range(n):
        t = i / n; f0 = lo + span * math.sin(math.pi * t) + 12 * math.sin(i * .004); ph += 2 * math.pi * f0 / sr
        s = sum((math.exp(-((k * f0 - form) / 900) ** 2) + .25 / k) * math.sin(k * ph) for k in range(1, 10))
        buf += int(max(-1, min(1, s * math.sin(math.pi * t) ** .6 * min(1, t * 25) / 3)) * 26000).to_bytes(2, "little", signed=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(bytes(buf))

MEOW = {1: TMP / "mewlin_meow1.wav", 2: TMP / "mewlin_meow2.wav"}

def play_meow(n):
    for c in (["pw-play"], ["paplay"], ["aplay", "-q"], ["mpv", "--no-video", "--really-quiet"]):
        if shutil.which(c[0]):
            subprocess.Popen(c + [str(MEOW[n])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); return


# ---------- app ----------
class App(QWidget):
    def __init__(s):
        super().__init__()
        s.cfg = dict(DEFAULT)
        try:
            d = json.loads(CFG.read_text())
            if d.get("v", 0) < 2: d.pop("channels", None)
            s.cfg.update(d)
        except Exception: pass
        s.cfg["v"] = 3
        if not s.cfg["ntfy_topic"]: s.cfg["ntfy_topic"] = "mewlin-" + secrets.token_hex(6)
        write_readme(); s.assets = {n: Asset(n) for n in SLOTS}
        try: s.ov = json.loads((ASSETS / "layout.json").read_text())
        except Exception: s.ov = {}
        s.rects, s.autok, s.edit, s.sel = {}, {}, False, 0; s.apply_speed()
        s.page, s.state, s.msg, s.paused, s.hits = "main", "idle", None, None, []
        s.left, s.end, s.press, s.cd_played, s.nstat = s.cfg["cycles"], 0, 0, False, ""
        s.proc, s.mstat, s.merr, s.mstart, s.t0, s.t = None, "Off", False, 0, time.monotonic(), 0.0
        make_meow(MEOW[1], 360, 430, .8, 1700); make_meow(MEOW[2], 520, 380, .5, 2300)
        s.setWindowTitle("Mewlin Pomodoro"); s.setFixedSize(W, H)
        s.timer = QTimer(s); s.timer.timeout.connect(s.step); s.timer.start(33); s.save()

    # --- logica ---
    def save(s):
        CFG.parent.mkdir(parents=True, exist_ok=True); CFG.write_text(json.dumps(s.cfg, indent=1))

    def rem(s): return s.paused if s.paused is not None else max(0, s.end - time.monotonic())

    def cd(s):
        if s.state == "countdown": return s.rem()
        if s.state == "break" and s.paused is None and s.rem() <= PREP: return s.rem()
        return None

    def begin(s, kind):
        s.state, s.cd_played = kind, False
        s.end = time.monotonic() + (PREP if kind == "countdown" else s.cfg["study" if kind == "study" else "rest"] * 60)

    def notify(s, title, msg, force=False):
        if not (s.cfg["ntfy_on"] or force): return
        url = f'{s.cfg["ntfy_server"].rstrip("/")}/{s.cfg["ntfy_topic"]}'
        def run():
            try:
                req = urllib.request.Request(url, data=msg.encode(), headers={"Title": title, "Priority": "high", "Tags": "cat"})
                urllib.request.urlopen(req, timeout=8).read(); s.nstat = "Alert sent!"
            except Exception as e: s.nstat = "Alert failed: " + str(e)[:34]
        threading.Thread(target=run, daemon=True).start()

    def step(s):
        now = time.monotonic(); s.t = now - s.t0
        if s.proc:
            if s.proc.poll() is not None: s.music_died()
            else: s.mstat = "Connecting..." if now - s.mstart < 4 else "Playing"
        if s.state == "break" and s.paused is None and s.rem() <= PREP and not s.cd_played:
            s.cd_played = True; play_meow(1)
        if s.state != "idle" and s.paused is None and now >= s.end:
            old = s.state; c = s.cfg
            if old in ("countdown", "break"):
                s.begin("study"); play_meow(2); s.notify("Study time", f"Focus for {c['study']} min. Cycles left: {s.left}")
            else:
                s.left -= 1
                if s.left <= 0:
                    s.state, s.msg, s.left = "idle", ("Quest complete!", "Meow-velous!"), c["cycles"]
                    s.notify("Quest complete", "All cycles done. Great job!")
                else: s.begin("break"); s.notify("Break time", f"Rest for {c['rest']} min. Cycles left: {s.left}")
                play_meow(2)
        s.update()

    def reset(s): s.state, s.paused, s.msg, s.left, s.cd_played = "idle", None, None, s.cfg["cycles"], False

    def music_died(s):
        try: lines = [l.strip() for l in LOG.read_text(errors="ignore").splitlines() if l.strip()]
        except Exception: lines = []
        low = " ".join(lines).lower()
        if "javascript" in low or "js runtime" in low or "deno" in low: m = "Missing JS runtime: pacman -S deno"
        elif "yt-dlp" in low and ("not found" in low or "no such" in low): m = "yt-dlp not found"
        else: m = (lines[-1][:46] if lines else "Stream failed") + " (log in /tmp)"
        s.proc, s.mstat, s.merr = None, m, True

    def toggle_music(s, restart=False):
        if s.proc:
            s.proc.terminate(); s.proc = None
            if not restart: s.mstat, s.merr = "Off", False; return
        for tool, hint in (("mpv", "Install mpv"), ("yt-dlp", "Install yt-dlp + deno")):
            if not shutil.which(tool): s.mstat, s.merr = hint, True; return
        out = open(LOG, "w")
        s.proc = subprocess.Popen(["mpv", "--no-video", "--no-input-terminal", "--msg-level=all=warn", "--ytdl-format=bestaudio/best",
                                   s.cfg["channels"][s.cfg["channel"]][1]], stdin=subprocess.DEVNULL, stdout=out, stderr=out)
        s.mstart, s.mstat, s.merr = time.monotonic(), "Connecting...", False

    def fixurl(s, u): u = u.strip(); return u if "://" in u else "https://" + u

    def restart_music(s):
        if s.proc: s.toggle_music(True)

    def act(s, name, right=False):
        if name == "plate":
            s.press = s.t + .15
            if right: return s.reset()
            if s.state == "idle": s.msg = None; s.begin("countdown"); play_meow(1)
            elif s.state != "countdown":
                if s.paused is None: s.paused = s.rem()
                else: s.end, s.paused = time.monotonic() + s.paused, None
        elif name == "reset": s.reset()
        elif name == "skip" and s.state != "idle":   # salta alla fine dello studio / della pausa / del conto alla rovescia
            s.paused, s.cd_played, s.end = None, True, time.monotonic()
        elif name == "opts": s.page = "opts"
        elif name == "back": s.save(); s.page = "main"
        elif name == "play": s.toggle_music()
        elif name in ("prev", "next"):
            s.cfg["channel"] = (s.cfg["channel"] + (1 if name == "next" else -1)) % len(s.cfg["channels"]); s.save()
            if s.proc: s.toggle_music(True)
        elif name == "madd":
            nm, ok = QInputDialog.getText(s, "New channel", "Name:")
            if ok and nm.strip():
                u, ok = QInputDialog.getText(s, "New channel", "Link (YouTube live/playlist, or any URL mpv can open):")
                if ok and u.strip():
                    s.cfg["channels"].append([nm.strip()[:24], s.fixurl(u)]); s.cfg["channel"] = len(s.cfg["channels"]) - 1; s.save(); s.restart_music()
        elif name == "medit":
            cur = s.cfg["channels"][s.cfg["channel"]]
            nm, ok = QInputDialog.getText(s, "Edit channel", "Name:", text=cur[0])
            if ok and nm.strip():
                u, ok = QInputDialog.getText(s, "Edit channel", "Link:", text=cur[1])
                if ok and u.strip(): s.cfg["channels"][s.cfg["channel"]] = [nm.strip()[:24], s.fixurl(u)]; s.save(); s.restart_music()
        elif name == "mdel" and len(s.cfg["channels"]) > 1:
            del s.cfg["channels"][s.cfg["channel"]]; s.cfg["channel"] %= len(s.cfg["channels"]); s.save(); s.restart_music()
        elif name == "alerts": s.cfg["ntfy_on"] = not s.cfg["ntfy_on"]; s.save()
        elif name == "topic":
            v, ok = QInputDialog.getText(s, "ntfy topic", "Topic (nome segreto da iscrivere nell'app ntfy):", text=s.cfg["ntfy_topic"])
            if ok and v.strip(): s.cfg["ntfy_topic"] = v.strip().replace(" ", "-"); s.save()
        elif name == "test": s.nstat = "Sending..."; s.notify("Mewlin test", "Meow! Notifications work.", True)
        elif ":" in name:
            d, k = name.split(":"); lo, hi, st = LIMITS[k]
            s.cfg[k] = max(lo, min(hi, s.cfg[k] + st * (1 if d == "inc" else -1)))
            if k == "cycles" and s.state == "idle": s.left = s.cfg["cycles"]

    def mousePressEvent(s, e):
        for r, n in s.hits:
            if r.contains(e.position()): s.act(n, e.button() == Qt.MouseButton.RightButton); break

    def apply_speed(s):
        for n, a in s.assets.items():
            if a.mov: a.mov.setSpeed(int(s.ov.get(n, {}).get("speed", DEF_SPEED)))

    def edit_names(s):
        return {"study": ["cat_study", "cauldron"], "countdown": ["cat_study", "cauldron"], "break": ["cat_break", "bat"]}.get(s.state, ["cat_idle"]) + ["plate", "panel"]

    def keyPressEvent(s, e):
        k = e.key()
        if k == Qt.Key.Key_L and s.page == "main":
            s.edit = not s.edit
            if not s.edit: (ASSETS / "layout.json").write_text(json.dumps(s.ov, indent=1))
            return
        if s.edit and s.page == "main":
            names = s.edit_names(); s.sel %= len(names); n = names[s.sel]; o = s.ov.setdefault(n, {})
            st = 5 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1; cur = int(o.get("k") or s.autok.get(n, 1))
            if k == Qt.Key.Key_N: s.sel = (s.sel + 1) % len(names)
            elif k == Qt.Key.Key_Left: o["dx"] = o.get("dx", 0) - st
            elif k == Qt.Key.Key_Right: o["dx"] = o.get("dx", 0) + st
            elif k == Qt.Key.Key_Up: o["dy"] = o.get("dy", 0) - st
            elif k == Qt.Key.Key_Down: o["dy"] = o.get("dy", 0) + st
            elif k == Qt.Key.Key_Minus: o["k"] = max(1, cur - 1)
            elif k == Qt.Key.Key_Plus: o["k"] = min(12, cur + 1)
            elif k == Qt.Key.Key_Comma: o["speed"] = max(10, o.get("speed", DEF_SPEED) - 10); s.apply_speed()
            elif k == Qt.Key.Key_Period: o["speed"] = min(300, o.get("speed", DEF_SPEED) + 10); s.apply_speed()
            elif k == Qt.Key.Key_H: o["hide"] = not o.get("hide", False)
            elif k == Qt.Key.Key_R: s.ov[n] = {}; s.apply_speed()
        elif k == Qt.Key.Key_Space and s.page == "main": s.act("plate")

    def closeEvent(s, e):
        if s.proc: s.proc.terminate()
        s.save(); e.accept()

    # --- disegno: slot, placeholder ---
    def inner(s, d, name):
        l, t, r, b = s.ov.get(name, {}).get("inset", INSET.get(name, (.08, .12, .08, .12)))
        return QRectF(d.x() + d.width() * l, d.y() + d.height() * t, d.width() * (1 - l - r), d.height() * (1 - t - b))

    def blit(s, p, name, r=None, flip=False):
        a = s.assets[name]; pm = a.pixmap()
        if pm is None or a.ref is None: return None
        sl, o = SLOTS[name], s.ov.get(name, {})
        r = QRectF(r or QRectF(*sl[:4])).translated(o.get("dx", 0), o.get("dy", 0))
        pw, ph = a.ref.width(), a.ref.height()
        k = min(r.width() / pw, r.height() / ph); k = int(k) if k >= 1 else k
        s.autok[name] = k; k = o.get("k") or k
        tw, th = pw * k, ph * k
        x = r.x() + (r.width() - tw) / 2; y = r.y() + (r.height() - th if sl[4] == "b" else (r.height() - th) / 2)
        if a.mov is None and name in ("cat_idle", "cat_study") and math.sin(s.t * 2) > 0: y += max(1, int(k))  # respiro per immagini statiche
        p.save()
        if flip: p.translate(x + tw / 2, 0); p.scale(-1, 1); p.translate(-(x + tw / 2), 0)
        p.drawPixmap(QRectF(x, y, pm.width() * k, pm.height() * k).toRect(), pm); p.restore()
        d = QRectF(x, y, tw, th); s.rects[name] = d; return d

    def blit9(s, p, name, r):
        pm = s.assets[name].pixmap()
        if pm is None: return None
        pw, ph = pm.width(), pm.height(); ks = max(1, int(r.height() // ph)); b = max(2, min(pw, ph) // 3); bs = b * ks
        xs, ys = [0, b, pw - b, pw], [0, b, ph - b, ph]
        tx, ty = [r.x(), r.x() + bs, r.right() - bs, r.right()], [r.y(), r.y() + bs, r.bottom() - bs, r.bottom()]
        for i in range(3):
            for j in range(3):
                p.drawPixmap(QRectF(tx[i], ty[j], tx[i + 1] - tx[i], ty[j + 1] - ty[j]), pm, QRectF(xs[i], ys[j], xs[i + 1] - xs[i], ys[j + 1] - ys[j]))
        return r

    def slot(s, p, name, r=None, flip=False):
        if s.ov.get(name, {}).get("hide"): return
        if s.blit(p, name, r, flip) is not None: return
        sl, o = SLOTS[name], s.ov.get(name, {}); col = sl[5]
        r = QRectF(r or QRectF(*sl[:4])).translated(o.get("dx", 0), o.get("dy", 0)); s.rects[name] = r
        p.fillRect(r, A(col, 45)); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(C(col), 2, Qt.PenStyle.DashLine)); p.drawRect(r)
        sz = 10; p.fillRect(QRectF(r.x() + (r.width() - sz) * (.5 + .5 * math.sin(s.t * 2)),
                                   r.y() + (r.height() - sz) * (.5 + .5 * abs(math.sin(s.t * 3))), sz, sz), C(col))
        if r.height() >= 60:
            txt(p, name, r.x(), r.center().y() - 16, r.width(), 18, 13, PARCH)
            txt(p, f"{sl[2]}x{sl[3]} max", r.x(), r.center().y() + 2, r.width(), 16, 11, MUTED, False)
        else: txt(p, "BAT", r.x(), r.y(), r.width(), r.height(), 10, PARCH)

    def icon(s, p, name, cx, cy, fallback):
        sl = SLOTS[name]
        if s.blit(p, name, QRectF(cx - sl[2] / 2, cy - sl[3] / 2, sl[2], sl[3])) is None: fallback()

    def paintEvent(s, e):
        p = QPainter(s); s.hits = []
        p.fillRect(0, 0, W, H, C("#150f22"))
        for y in range(0, H, 6): p.fillRect(0, y, W, 1, A("#ffffff", 6))
        (s.draw_main if s.page == "main" else s.draw_opts)(p); p.end()

    def ambient(s, p):
        """sfondo vivo anche se statico: lanterna che sfarfalla + polvere che sale (config: layout.json -> "ambient")"""
        a = s.ov.get("ambient", {"lantern": [140, 50], "motes": 16, "glow": 60}); t = s.t
        if a.get("lantern"):
            cx, cy = 20 + a["lantern"][0], 20 + a["lantern"][1]; r = a.get("glow", 60)
            fl = .5 + .5 * math.sin(t * 9) * math.sin(t * 5.3 + 1); g = QRadialGradient(cx, cy, r)
            g.setColorAt(0, A("#ffb347", int(50 + 55 * fl))); g.setColorAt(1, A("#ffb347", 0))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        for i in range(int(a.get("motes", 16))):
            x = 20 + (i * 137) % 400 + 6 * math.sin(t * .7 + i); y = 320 - ((t * (5 + i % 5) + i * 41) % 300)
            p.fillRect(QRectF(int(x), int(y), 2, 2), A("#ffe9a8", int(60 + 50 * math.sin(t * 2 + i))))

    def fallback_bg(s, p):
        rect(p, 20, 20, 400, 215, "#241a3c"); rect(p, 20, 235, 400, 85, "#33264a")
        for r in range(20, 235, 36):
            rect(p, 20, r, 400, 2, "#2e2250")
            for x in range(20 + ((r - 20) // 36 % 2) * 40, 420, 80): rect(p, x, r, 2, 36, "#2e2250")
        for x in range(20, 420, 50): rect(p, x, 235, 2, 85, "#281c3b")
        rect(p, 305, 60, 60, 90, "#4a3a78"); rect(p, 309, 64, 52, 86, "#1b2a66"); rect(p, 325, 80, 20, 20, "#fff2b8")
        rect(p, 44, 120, 120, 6, "#6b4428"); [rect(p, x, 100, 14, 20, c) for x, c in ((56, "#5fe06a"), (92, "#c06aff"), (128, "#ff7a8a"))]
        txt(p, "scene_bg.gif", 20, 22, 400, 16, 11, MUTED, False)

    def pill(s, p, name, x, y, w, h, on=True):
        if on: s.hits.append((QRectF(x, y, w, h), name))
        p.setOpacity(1 if on else .4)
        d = s.blit9(p, "button", QRectF(x, y, w, h))
        if d is None: pbox(p, x, y, w, h, "#2e2150", "#7a62b8", 4, 3); d = QRectF(x, y, w, h)
        return s.inner(d, "button")

    def draw_main(s, p):
        t, st = s.t, s.state; s.rects = {}
        p.save(); p.setClipRect(QRectF(20, 20, 400, 300))
        if s.blit(p, "scene_bg") is None: s.fallback_bg(p)
        s.ambient(p)
        if st in ("study", "countdown"):
            s.slot(p, "cat_study")
            if s.assets["cauldron"].pixmap() is not None: s.slot(p, "cauldron")   # solo se esiste un file separato
        elif st == "break":
            a = t * .9; cx = 220 + 110 * math.sin(a)
            s.slot(p, "cat_break", QRectF(cx - 85, 185, 170, 130), math.cos(a) < 0)
            for k in range(3):
                bx, by = 220 + 150 * math.sin(t * 1.1 + k * 2.1), 80 + 30 * math.sin(t * 1.7 + k * 1.3) + k * 20
                s.slot(p, "bat", QRectF(bx - 28, by - 20, 56, 40))
        else: s.slot(p, "cat_idle")
        p.restore(); p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(C("#5a4690"), 4)); p.drawRect(QRectF(18, 18, 404, 304))
        # contatore: i testi stanno nel riquadro interno della cornice
        x, y, w, h = 20, 346, 400, 116; oy = 3 if t < s.press else 0
        s.hits.append((QRectF(x, y, w, h), "plate")); col = GREENL if st == "study" else PINKL
        d = s.blit(p, "plate", QRectF(x, y + oy, w, h))
        if d is None:
            pbox(p, x, y + oy, w, h, "#2a1d4a", "#d9b45a", 6, 4); d = QRectF(x, y + oy, w, h)
            for dx in (16, w - 24): rect(p, x + dx, y + 14 + oy, 8, 8, GOLD); rect(p, x + dx, y + h - 22 + oy, 8, 8, GOLD)
        ir = s.inner(d, "plate"); ix, iy, iw, ih = ir.x(), ir.y(), ir.width(), ir.height(); cdv = s.cd()
        if cdv is not None:
            txt(p, "Get ready..." if st == "countdown" else "Back to the cauldron in", ix, iy, iw, ih * .26, ih * .22, PARCH, sp=1)
            txt(p, math.ceil(cdv), ix, iy + ih * .2, iw, ih * .8, ih * (.6 + .12 * (cdv % 1)), GOLD if st == "countdown" else PINKL, fit=False)
        elif st == "idle":
            l1, l2 = s.msg or (("Ready to study", "dark magic?"), ("The cauldron", "awaits..."), ("Tap to brew", "a focus potion"), ("Meow! Tap me", "to begin"))[int(t / 4) % 4]
            txt(p, l1, ix, iy, iw, ih * .5, ih * .34, GOLD); txt(p, l2, ix, iy + ih * .5, iw, ih * .5, ih * .34, PARCH)
        else:
            r = s.rem(); sec = math.ceil(r); tot = s.cfg["study" if st == "study" else "rest"] * 60
            txt(p, "Paused" if s.paused is not None else ("Break in" if st == "study" else "Next spell in"), ix, iy, iw, ih * .26, ih * .2, PARCH, sp=1)
            size = ih * .5; cw, cc = size * .66, size * .36; tw = 4 * cw + cc
            if tw > iw: size *= iw / tw; cw, cc = size * .66, size * .36; tw = 4 * cw + cc
            gx = ix + (iw - tw) / 2
            for ch in f"{sec // 60:02d}:{sec % 60:02d}":
                wv = cc if ch == ":" else cw; txt(p, ch, gx, iy + ih * .2, wv, ih * .62, size, col, fit=False); gx += wv
            nb = 24; bw = iw / nb; done = int(nb * (1 - r / tot))
            for i in range(nb): rect(p, ix + i * bw, iy + ih * .86, bw - 2, max(3, ih * .1), col if i < done else "#120c1c")
        # riga bottoni
        yy = 478
        ir = s.pill(p, "cycles", 20, yy, 92, 46, False); p.setOpacity(1); cy = ir.center().y(); ix0 = ir.x() + 14
        s.icon(p, "icon_book", ix0, cy, lambda: (rect(p, ix0 - 12, cy - 9, 12, 18, "#8a2d3b"), rect(p, ix0, cy - 9, 12, 18, "#efe3c4")))
        txt(p, f"x{s.left}", ix0 + 20, ir.y(), ir.right() - ix0 - 20, ir.height(), 20, GOLD)
        ir = s.pill(p, "reset", 120, yy, 100, 46, st != "idle"); cy = ir.center().y(); ix0 = ir.x() + 14
        def f_reset():
            pa = QPainterPath(); pa.moveTo(ix0 + 8, cy - 7); pa.arcTo(QRectF(ix0 - 9, cy - 9, 18, 18), 40, 280); stroke(p, pa, PARCH, 3)
            poly(p, [(ix0 + 8, cy - 14), (ix0 + 17, cy - 8), (ix0 + 7, cy - 3)], PARCH)
        s.icon(p, "icon_reset", ix0, cy, f_reset); txt(p, "Reset", ix0 + 20, ir.y(), ir.right() - ix0 - 20, ir.height(), 15, PARCH); p.setOpacity(1)
        ir = s.pill(p, "skip", 228, yy, 60, 46, st != "idle"); cy = ir.center().y(); kx = ir.center().x()
        s.icon(p, "icon_skip", kx, cy, lambda: poly(p, [(kx - 10, cy - 3), (kx + 2, cy - 3), (kx + 2, cy - 9), (kx + 12, cy), (kx + 2, cy + 9), (kx + 2, cy + 3), (kx - 10, cy + 3)], PARCH)); p.setOpacity(1)
        ir = s.pill(p, "opts", 296, yy, 124, 46); cy = ir.center().y(); ix0 = ir.x() + 14
        def f_gear():
            for i in range(4): p.save(); p.translate(ix0, cy); p.rotate(i * 45); rect(p, -2.5, -11, 5, 22, GOLD); p.restore()
            rect(p, ix0 - 7, cy - 7, 14, 14, GOLD); rect(p, ix0 - 3, cy - 3, 6, 6, "#271b45")
        s.icon(p, "icon_gear", ix0, cy, f_gear); txt(p, "Options", ix0 + 20, ir.y(), ir.right() - ix0 - 20, ir.height(), 15, PARCH)
        # player: tutto dentro il riquadro interno del pannello
        d = s.blit(p, "panel")
        if d is None: pbox(p, 20, 548, 400, 112, "#1a1230", "#5a4690", 6, 3); d = QRectF(20, 548, 400, 112)
        ir = s.inner(d, "panel"); ix, iy, iw, ih = ir.x(), ir.y(), ir.width(), ir.height(); cy = iy + ih / 2; playing = s.proc is not None
        for nm, fx, dd in (("prev", .07, 1), ("next", .35, -1)):
            cx2 = ix + iw * fx; s.hits.append((QRectF(cx2 - 18, cy - 18, 36, 36), nm))
            s.icon(p, "icon_" + nm, cx2, cy, lambda cx2=cx2, dd=dd: (poly(p, [(cx2 + dd * 7, cy - 9), (cx2 + dd * 7, cy + 9), (cx2 - dd * 5, cy)], PARCH), rect(p, cx2 - dd * 9 - 1, cy - 9, 3, 18, PARCH)))
        px = ix + iw * .21; s.hits.append((QRectF(px - 26, cy - 26, 52, 52), "play"))
        if s.assets["icon_play"].pixmap() is None: pbox(p, px - 24, cy - 24, 48, 48, "#2f9a4a", "#1f6a2c", 5, 3)
        if playing: s.icon(p, "icon_pause", px, cy, lambda: (rect(p, px - 9, cy - 12, 7, 24, "#0f2a14"), rect(p, px + 2, cy - 12, 7, 24, "#0f2a14")))
        else: s.icon(p, "icon_play", px, cy, lambda: poly(p, [(px - 7, cy - 12), (px - 7, cy + 12), (px + 14, cy)], "#0f2a14"))
        tx, tw = ix + iw * .45, iw * .55
        txt(p, s.cfg["channels"][s.cfg["channel"]][0], tx, iy, tw, ih * .36, ih * .3, PARCH, al=LEFT)
        txt(p, s.mstat, tx, iy + ih * .36, tw, ih * .2, ih * .17, "#ff8a8a" if s.merr else MUTED, False, al=LEFT)
        load = playing and s.mstat.startswith("Conn"); n = 21; pitch = tw / n; mh = ih * .42
        for i in range(n):
            hh = (.2 + .8 * (.5 + .5 * math.sin(t * (3 if load else 7) + i * .9)) * (.55 + .45 * math.sin(t * 2.3 + i * .4) ** 2)) * mh if playing else 3
            hh = max(3, hh - hh % 2)
            rect(p, tx + i * pitch, iy + ih - hh, max(2, pitch * .6), hh, "#9bf08a" if playing and i % 3 else ("#a06aff" if playing else "#33295a"))
        if s.edit:   # editor posizioni
            names = s.edit_names(); s.sel %= len(names); n = names[s.sel]; o = s.ov.get(n, {})
            if n in s.rects: p.setBrush(Qt.BrushStyle.NoBrush); p.setPen(QPen(C("#ffd25a"), 2, Qt.PenStyle.DashLine)); p.drawRect(s.rects[n])
            rect(p, 0, 664, W, 26, "#000000")
            txt(p, f"EDIT {n}  dx{o.get('dx', 0)} dy{o.get('dy', 0)}  x{o.get('k') or s.autok.get(n, 1)}  speed {o.get('speed', DEF_SPEED)}%" + ("  HIDDEN" if o.get("hide") else ""), 0, 664, W, 13, 11, GOLD)
            txt(p, "N next  arrows move  +/- size  , . speed  H hide  R reset  L save", 0, 677, W, 12, 10, MUTED, False)

    def draw_opts(s, p):
        txt(p, "Options", 0, 16, W, 40, 30, GOLD)
        for i, (lab, k, unit) in enumerate((("Cycles", "cycles", "pomodoros"), ("Study", "study", "minutes"), ("Rest", "rest", "minutes"))):
            y = 66 + i * 86
            txt(p, lab, 0, y, W, 22, 16, MUTED, sp=2)
            for nm, cx, g in ((f"dec:{k}", 92, "-"), (f"inc:{k}", 348, "+")):
                s.hits.append((QRectF(cx - 25, y + 28, 50, 50), nm)); pbox(p, cx - 25, y + 28, 50, 50, "#2e2150", "#a98af0", 5, 3)
                rect(p, cx - 10, y + 51, 20, 4, PARCH)
                if g == "+": rect(p, cx - 2, y + 43, 4, 20, PARCH)
            txt(p, s.cfg[k], 120, y + 26, 200, 46, 42, PARCH); txt(p, unit, 120, y + 70, 200, 16, 12, MUTED, False)
        lab = lambda ir, tx, sz, c: txt(p, tx, ir.x(), ir.y(), ir.width(), ir.height(), sz, c)
        txt(p, "Phone / watch alerts (ntfy)", 0, 328, W, 20, 15, MUTED, sp=1)
        lab(s.pill(p, "alerts", 120, 354, 200, 40), "Alerts: " + ("ON" if s.cfg["ntfy_on"] else "OFF"), 17, GREENL if s.cfg["ntfy_on"] else PARCH)
        txt(p, "Topic: " + s.cfg["ntfy_topic"], 0, 402, W, 18, 12, PARCH, False)
        lab(s.pill(p, "topic", 50, 428, 160, 34), "Change topic", 13, PARCH); lab(s.pill(p, "test", 230, 428, 160, 34), "Send test", 13, PARCH)
        txt(p, s.nstat, 0, 470, W, 18, 12, "#ff8a8a" if "fail" in s.nstat else GREENL, False)
        # canali musicali
        chs, i = s.cfg["channels"], s.cfg["channel"]
        txt(p, "Music channels", 0, 494, W, 18, 15, MUTED, sp=1)
        for nm, bx, dd in (("prev", 56, 1), ("next", 344, -1)):
            s.hits.append((QRectF(bx, 514, 40, 32), nm)); pbox(p, bx, 514, 40, 32, "#2e2150", "#a98af0", 4, 3)
            poly(p, [(bx + 20 + dd * 5, 522), (bx + 20 + dd * 5, 538), (bx + 20 - dd * 6, 530)], PARCH)
        txt(p, f"{chs[i][0]}  ({i + 1}/{len(chs)})", 100, 514, 240, 32, 18, PARCH)
        u = chs[i][1]; txt(p, u if len(u) <= 46 else u[:45] + "...", 0, 549, W, 14, 11, MUTED, False)
        lab(s.pill(p, "madd", 40, 568, 116, 32), "Add link", 13, GREENL); lab(s.pill(p, "medit", 162, 568, 116, 32), "Edit", 13, PARCH)
        lab(s.pill(p, "mdel", 284, 568, 116, 32, len(chs) > 1), "Delete", 13, "#ff8a8a"); p.setOpacity(1)
        lab(s.pill(p, "back", 120, 620, 200, 50), "Back", 22, PARCH)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    write_readme()
    fid = QFontDatabase.addApplicationFont(str(ASSETS / "font.ttf"))
    if fid >= 0: FAM.insert(0, QFontDatabase.applicationFontFamilies(fid)[0])
    w = App(); w.show()
    sys.exit(app.exec())
