# -*- coding: utf-8 -*-
"""Revisa un FCPXML antes de abrirlo en Resolve.

Que el XML parsee no dice nada: Resolve se cierra sin mensaje ante valores que
son legales segun la especificacion pero que su importador no espera. Este
script comprueba rangos plausibles, no solo tipos.

Uso:  py validar_fcpxml.py archivo.fcpxml [--max-img N]

Sale con codigo 1 si encuentra algo. Cada comprobacion existe porque tumbo un
import de verdad; no quitar ninguna sin haber visto por que se puso.
"""

import os
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from fractions import Fraction

TASAS_OK = {"1001/24000s", "1/24s", "1/25s", "1001/30000s", "1/30s",
            "1/50s", "1001/60000s", "1/60s"}
MAX_IMG_SEGUIDAS = 2


def seg(valor):
    """'1001/24000s' o '4s' -> Fraction de segundos."""
    v = valor[:-1]
    return Fraction(*map(int, v.split("/"))) if "/" in v else Fraction(int(v))


def validar(ruta, max_img=MAX_IMG_SEGUIDAS):
    raiz = ET.parse(ruta).getroot()
    recursos = raiz.find("resources")
    spine = raiz.find(".//spine")
    clips = spine.findall("asset-clip")
    assets = {a.get("id"): a for a in recursos.findall("asset")}
    formatos = {f.get("id"): f for f in recursos.findall("format")}
    fallos = []

    def mal(msg):
        if msg not in fallos:
            fallos.append(msg)

    for c in clips:
        if c.get("ref") not in assets:
            mal("asset-clip apunta a un asset que no existe: %s" % c.get("ref"))
        if c.get("format") and c.get("format") not in formatos:
            mal("asset-clip apunta a un format que no existe: %s" % c.get("format"))

    for f in formatos.values():
        if not f.get("frameDuration"):
            # los stills con FFVideoFormatRateUndefined tumban el importador
            mal("format sin frameDuration: %s" % f.get("id"))
        elif f.get("frameDuration") not in TASAS_OK:
            # ffprobe da el r_frame_rate real, tipo 19001/317. Hay que ajustarlo
            mal("tasa no estandar en %s: %s" % (f.get("id"), f.get("frameDuration")))
        if int(f.get("width")) % 2 or int(f.get("height")) % 2:
            mal("dimension impar en %s: %sx%s" % (f.get("id"), f.get("width"), f.get("height")))

    for a in assets.values():
        if a.get("duration") == "0s":
            mal("asset con duration=0s: %s" % a.get("name"))
        canales = a.get("audioChannels")
        if canales is not None:
            tasa = int(a.get("audioRate") or 0)
            if not (1 <= int(canales) <= 32 and 8000 <= tasa <= 192000):
                # sintoma clasico de haber leido ffprobe con csv=p=0: los
                # campos salen en el orden interno, no en el que se piden
                mal("audio absurdo en %s: %s canales a %s Hz"
                    % (a.get("name"), canales, tasa))
        rep = a.find("media-rep")
        if rep is None:
            mal("asset sin media-rep: %s" % a.get("name"))
            continue
        src = rep.get("src", "")
        if not src.startswith("file:///"):
            mal("src que no es file:///: %s" % src[:60])
            continue
        p = urllib.parse.unquote(src[len("file:///"):]).replace("/", os.sep)
        if not os.path.isfile(p):
            mal("src que no existe en disco: %s" % p)

    # Un beat de imagen es o bien un still suelto (format con espacio de color
    # de imagen fija) o bien un compuesto horneado, que ya es mp4 y se reconoce
    # por el sufijo. Sirve para contar rachas.
    def _es_img(a):
        if (a.get("name") or "").endswith("_comp"):
            return True
        f = formatos.get(a.get("format"))
        return f is not None and f.get("colorSpace") == "1-13-1"

    es_img = {aid: _es_img(a) for aid, a in assets.items()}

    pos = Fraction(0)
    racha = peor = 0
    donde = None
    for c in clips:
        if seg(c.get("offset")) != pos:
            mal("hueco o solape en el spine, en %s" % c.get("name"))
        ini, dur = seg(c.get("start")), seg(c.get("duration"))
        tope = seg(assets[c.get("ref")].get("duration"))
        if ini + dur > tope + Fraction(1, 1000):
            mal("el clip se sale de su asset: %s" % c.get("name"))
        for m in c.findall("marker"):
            if not (ini <= seg(m.get("start")) < ini + dur):
                mal("marcador fuera del rango de su clip: %s" % c.get("name"))
        if es_img.get(c.get("ref")):
            racha += 1
            if racha > peor:
                peor, donde = racha, c.get("name")
        else:
            racha = 0
        pos += dur

    if seg(raiz.find(".//sequence").get("duration")) != pos:
        mal("la duracion de la secuencia no es la suma de los clips")

    # Las transiciones se centran en el corte y no anaden tiempo: se comen el
    # handle de los dos clips que tocan. Sin handle, Resolve no las monta.
    transiciones = spine.findall("transition")
    cortes = {}
    acum = Fraction(0)
    for i, c in enumerate(clips):
        cortes[acum + seg(c.get("duration"))] = i
        acum += seg(c.get("duration"))
    for t in transiciones:
        ini, dur = seg(t.get("offset")), seg(t.get("duration"))
        centro = ini + dur / 2
        if centro not in cortes:
            mal("transicion que no cae en un corte: offset %s" % t.get("offset"))
            continue
        i = cortes[centro]
        for clip, lado in ((clips[i], "salida"), (clips[i + 1], "entrada")):
            a = assets[clip.get("ref")]
            libre = (seg(a.get("duration")) - seg(clip.get("start")) - seg(clip.get("duration"))
                     if lado == "salida" else seg(clip.get("start")))
            if libre < dur / 2:
                mal("sin handle de %s para la transicion en %s"
                    % (lado, clip.get("name")))
    if peor > max_img:
        mal("racha de %d imagenes seguidas (hasta %s), el maximo es %d"
            % (peor, donde, max_img))

    return {"clips": len(clips), "assets": len(assets), "formats": len(formatos),
            "marcadores": len(spine.findall(".//marker")), "racha": peor,
            "transiciones": len(spine.findall("transition")),
            "duracion": float(pos), "fallos": fallos}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("uso: py validar_fcpxml.py archivo.fcpxml [--max-img N]")
        return 2
    max_img = MAX_IMG_SEGUIDAS
    if "--max-img" in sys.argv:
        max_img = int(sys.argv[sys.argv.index("--max-img") + 1])

    r = validar(args[0], max_img)
    print("%s  %d:%02d  %d clips, %d transiciones, %d assets, %d formats, "
          "%d marcadores, racha %d"
          % (os.path.basename(args[0]), r["duracion"] // 60, r["duracion"] % 60,
             r["clips"], r["transiciones"], r["assets"], r["formats"],
             r["marcadores"], r["racha"]))
    if not r["fallos"]:
        print("OK")
        return 0
    for f in r["fallos"]:
        print("  FALLO: %s" % f)
    return 1


if __name__ == "__main__":
    sys.exit(main())
