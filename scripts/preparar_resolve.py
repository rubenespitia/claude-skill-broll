# -*- coding: utf-8 -*-
"""Prepara el B-roll para DaVinci Resolve (version gratuita).

Genera dos cosas a partir de manifest.json:

  por-seccion/          arbol de enlaces duros ordenado por seccion del guion.
                        Se mete en Resolve con "Add Folder and SubFolders into
                        Media Pool (Create Bins)" y salen los bins hechos.
                        Son hardlinks: no ocupan disco extra.

  B-ROLL-GUIA.fcpxml    timeline con todo en orden de guion y un marcador por
                        recurso. Entra por File > Import > Timeline.

Como se reparte la duracion:

  1. Cada seccion recibe una tajada del total **proporcional a sus palabras**
     en el guion hablado, no a cuantos recursos tenga. Los recuentos estan en
     manifest.json, seccion por seccion.
  2. Dentro de la seccion, las imagenes duran DUR_IMAGEN y el video se lleva
     el resto, repartido entre sus fuentes sin pedirle a ninguna mas de lo que
     tiene. Una fuente usada en dos secciones comparte su capacidad.
  3. La tajada de cada video se trocea en fragmentos de ~DUR_SEGMENTO
     repartidos a lo largo del clip, saltandose MARGEN de cabeza y de cola.
  4. Los clips se entrelazan para que **no haya mas de MAX_IMG_SEGUIDAS
     imagenes seguidas**. Eso reordena dentro de la seccion, no entre secciones.

El timeline sale **sin transiciones** pero **con handles**: Resolve no respeta el
tipo de transicion al importar, asi que se ponen alli, donde se aplican a todos
los cortes de una vez. Los handles estan para que eso no de "insufficient
handles".

Tratamiento de las imagenes:

  Cada imagen fija se hornea con ffmpeg a compuestos/<nombre>_comp.mp4, un clip
  1920x1080 con la propia imagen desenfocada y derivando de fondo y la imagen
  nitida encima al ESCALA_IMAGEN, centrada. Resuelve de paso los posters
  verticales, que sin fondo salen con barras negras.

  Se hornea en vez de montar dos pistas con adjust-transform porque asi el
  timeline se queda en una sola pista y las transiciones son solapamientos
  normales. Los lanes y los adjust-transform dependen de que el importador los
  respete; un solapamiento no.

  Los compuestos se renderizan 2*TRANSICION_S mas largos que su duracion en
  timeline: una transicion centrada come media a cada lado, y dejar el minimo
  justo hace que Resolve avise de "insufficient handles".

Uso:  py preparar_resolve.py [<carpeta B-roll>]
      py preparar_resolve.py [<carpeta B-roll>] --prueba

Sin argumento usa el directorio actual. Necesita ffmpeg y ffprobe en el PATH.
"""

import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from urllib.parse import quote
from xml.sax.saxutils import escape

def _raiz():
    """Carpeta B-roll de la pieza: primer argumento, o el directorio actual."""
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    return os.path.abspath(args[0]) if args else os.getcwd()


AQUI = _raiz()

# timeline: 23.976p 1080, que es donde caen los trailers de cine
TL_NUM, TL_DEN = 24000, 1001          # fps = TL_NUM / TL_DEN
TL_ANCHO, TL_ALTO = 1920, 1080

OBJETIVO_TOTAL_S = 600.0              # duracion objetivo del timeline
DUR_IMAGEN = 4.0                      # segundos por imagen
DUR_SEGMENTO = 8.0                    # duracion objetivo de cada fragmento
MARGEN = 0.08                         # cabeza y cola que se descartan de cada video
MAX_IMG_SEGUIDAS = 2
PALABRAS_POR_MINUTO = 160             # solo para el informe

# Tratamiento de las imagenes fijas. Cada una se hornea con ffmpeg a un clip
# 1920x1080: la propia imagen desenfocada y derivando de fondo, y la imagen
# nitida encima al ESCALA_IMAGEN del encuadre, centrada. Asi el timeline se
# queda en una sola pista y las transiciones son solapamientos normales, que es
# lo unico que el importador de Resolve traga sin dramas.
COMPONER_IMAGENES = True
ESCALA_IMAGEN = 0.80                  # tamano de la imagen dentro del encuadre
BLUR_SIGMA = 30                       # desenfoque del fondo
FONDO_BRILLO = -0.15                  # el fondo va mas oscuro que la imagen
FONDO_SATURACION = 0.75
# Holgura del fondo en PIXELES, igual en los dos ejes. En porcentaje daria 192
# px en x y solo 108 en y, asi que una diagonal recorreria mas distancia en el
# mismo tiempo y se veria mas rapida.
DERIVA_PX = 160

# Emitir o no los <transition>. Va en False porque Resolve no respeta el tipo
# al importar: monta Edge Wipe o Cross Dissolve y no hay forma de pedirle otra
# cosa. Las transiciones se ponen en Resolve, que ahi si se aplican a todos los
# cortes de una vez.
TRANSICIONES = False
# Se sigue usando aunque TRANSICIONES este en False: define el handle que se
# reserva a cada lado del corte para que esas transiciones manuales tengan de
# donde tirar. Sin handle, Resolve avisa de "insufficient handles".
TRANSICION_S = 0.5
# (tipo, preset) que se ciclan corte a corte.
#
# [verificado 2026-09-30] Resolve NO respeta el tipo al importar FCPXML. Solo
# hay dos resultados posibles y ninguno depende del `name`:
#
#   <transition> sin hijo <filter-video>  ->  Cross Dissolve
#   <transition> con hijo <filter-video>  ->  Edge Wipe
#
# Probado con name="Slide", "Push", "Slide, Left-Right", "Push Right",
# "Edge Wipe" y "Wipe", y replicando la estructura exacta que escribe Resolve
# al exportar, uid incluido. Siempre lo mismo.
#
# Por eso preset va a None: Cross Dissolve es neutro y Edge Wipe no. El tipo se
# cambia en Resolve despues de importar, y ahi si se puede en bloque.
# Cada entrada es (tipo, preset, uid). preset=None -> sin <filter-video>.
# uid=None -> se usa EFECTO_UID, el que escribe Resolve al exportar.
EFECTO_UID = "FxPlug:4731E73A-8DAC-4113-9A30-AE85B1761265"
TRANSICION_CICLO = [("Cross Dissolve", None, None)]

EXT_VIDEO = (".mp4", ".mov", ".mxf", ".mkv", ".avi")

FPS_TL = TL_NUM / TL_DEN
FRAMES_IMAGEN = int(round(DUR_IMAGEN * FPS_TL))
FRAMES_TRANS = int(round(TRANSICION_S * FPS_TL))
MEDIA_TRANS = FRAMES_TRANS // 2       # lo que la transicion come a cada lado
# Handle que se reserva de verdad. El minimo teorico es MEDIA_TRANS, pero
# dejarlo justo hace que Resolve avise de "insufficient handles": redondea la
# duracion hacia arriba y se queda sin margen. Se reserva el doble.
HANDLE = FRAMES_TRANS

# Resolve solo digiere tasas estandar. ffprobe devuelve cosas como 19001/317
# (= 59.9401) y declarar eso en un <format> lo tumba.
TASAS_ESTANDAR = [(24000, 1001), (24, 1), (25, 1), (30000, 1001), (30, 1),
                  (50, 1), (60000, 1001), (60, 1)]


def ajustar_tasa(num, den):
    fps = num / den
    return min(TASAS_ESTANDAR, key=lambda t: abs(t[0] / t[1] - fps))


def t_timeline(frames):
    return "0s" if frames == 0 else "%d/%ds" % (frames * TL_DEN, TL_NUM)


def t_fuente(frames, num, den):
    if frames == 0:
        return "0s"
    if den == 1:
        return "%d/%ds" % (frames, num)
    return "%d/%ds" % (frames * den, num)


def attr(valor):
    return escape(str(valor), {'"': "&quot;", "'": "&apos;"})


def file_url(ruta):
    return "file:///" + quote(ruta.replace("\\", "/"), safe="/:")


def _stream(ruta, tipo):
    """Primer stream del tipo pedido, como dict. JSON y no csv: ffprobe ignora
    el orden en que pides los campos e imprime en el suyo, asi que con csv se
    cruzan los valores en silencio."""
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", tipo, "-show_streams",
         "-of", "json", ruta],
        capture_output=True, text=True).stdout
    flujos = json.loads(salida).get("streams", [])
    return flujos[0] if flujos else None


def sondear(ruta):
    es_video = os.path.splitext(ruta)[1].lower() in EXT_VIDEO
    v = _stream(ruta, "v:0")
    if not es_video:
        return {"video": False, "ancho": int(v["width"]), "alto": int(v["height"])}
    num, den = ajustar_tasa(*[int(x) for x in v["r_frame_rate"].split("/")])
    a = _stream(ruta, "a:0")
    return {"video": True,
            "ancho": int(v["width"]), "alto": int(v["height"]),
            "num": num, "den": den, "frames": int(v["nb_frames"]),
            "canales": int(a["channels"]) if a else 0,
            "tasa": int(a["sample_rate"]) if a else 0}


def capacidad(info):
    """Frames de timeline que se le pueden sacar a un video, sin cabeza ni cola."""
    segundos = info["frames"] / (info["num"] / info["den"])
    return int(segundos * (1 - 2 * MARGEN) * FPS_TL)


def repartir(presupuesto, capacidades):
    """Reparte a partes iguales sin pedirle a nadie mas de lo que tiene, y
    redistribuye lo que sobra de los cortos entre los que aun tienen sitio."""
    asignado = [0] * len(capacidades)
    abiertos = [i for i, c in enumerate(capacidades) if c > 0]
    while abiertos and presupuesto > 0:
        cuota = presupuesto // len(abiertos)
        if cuota == 0:
            break
        movido = False
        for i in list(abiertos):
            dar = min(cuota, capacidades[i] - asignado[i])
            if dar > 0:
                asignado[i] += dar
                presupuesto -= dar
                movido = True
            if asignado[i] >= capacidades[i]:
                abiertos.remove(i)
        if not movido:
            break
    return asignado


# Hacia donde deriva el fondo, en vectores unitarios. El modulo es 1 en todos,
# asi que todas las variantes recorren la misma distancia en el mismo tiempo:
# cambia la direccion, no la velocidad. El orden esta puesto para que dos
# imagenes seguidas no se muevan parecido.
_D = 0.7071067811865476  # 1/raiz(2): con 0.707 el modulo se queda en 159.94
DIRECCIONES = [
    (1.0, 0.0),      # derecha
    (-_D, _D),       # diagonal abajo-izquierda
    (0.0, -1.0),     # arriba
    (_D, _D),        # diagonal abajo-derecha
    (-1.0, 0.0),     # izquierda
    (_D, -_D),       # diagonal arriba-derecha
    (0.0, 1.0),      # abajo
    (-_D, -_D),      # diagonal arriba-izquierda
]


def desplazamiento(direccion):
    """(x0, x1, y0, y1) del recorrido de la ventana de recorte, en pixeles.

    El recorrido se centra en la holgura: sale y llega a la misma distancia del
    centro, sea cual sea la direccion."""
    dx, dy = DIRECCIONES[direccion % len(DIRECCIONES)]
    mitad = DERIVA_PX / 2.0
    return (mitad - dx * mitad, mitad + dx * mitad,
            mitad - dy * mitad, mitad + dy * mitad)


def _firma_receta():
    """Los parametros con los que se horneo. Si cambian hay que rehacer los
    compuestos: mirar solo la fecha del archivo no basta, porque tocar una
    constante no toca el jpg de origen y el cache los daria por buenos."""
    return "v4 escala=%g blur=%g brillo=%g sat=%g deriva=%dpx dirs=%d dur=%g %dx%d" % (
        ESCALA_IMAGEN, BLUR_SIGMA, FONDO_BRILLO, FONDO_SATURACION, DERIVA_PX,
        len(DIRECCIONES), DUR_IMAGEN + 2 * TRANSICION_S, TL_ANCHO, TL_ALTO)


def componer(origen, destino, direccion=0, forzar=False):
    """Hornea una imagen fija a un clip 1920x1080: la propia imagen desenfocada
    y derivando de fondo, la imagen nitida encima al ESCALA_IMAGEN, centrada.

    `direccion` alterna hacia donde deriva el fondo. Con todas iguales el
    montaje entero parece irse para el mismo lado.

    Se renderiza TRANSICION_S de mas para que la transicion tenga handle a cada
    lado."""
    if (not forzar and os.path.isfile(destino)
            and os.path.getmtime(destino) >= os.path.getmtime(origen)):
        return destino

    dur = DUR_IMAGEN + 2 * TRANSICION_S
    ancho_bg = (TL_ANCHO + DERIVA_PX) // 2 * 2
    alto_bg = (TL_ALTO + DERIVA_PX) // 2 * 2
    ancho_fg = int(TL_ANCHO * ESCALA_IMAGEN) // 2 * 2
    alto_fg = int(TL_ALTO * ESCALA_IMAGEN) // 2 * 2

    x0, x1, y0, y1 = desplazamiento(direccion)
    filtro = (
        "[0:v]split=2[a][b];"
        "[a]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
        "gblur=sigma=%g,eq=brightness=%g:saturation=%g,"
        "crop=%d:%d:x='%g+(%g)*t/%g':y='%g+(%g)*t/%g'[bg];"
        "[b]scale=%d:%d:force_original_aspect_ratio=decrease,"
        "scale=trunc(iw/2)*2:trunc(ih/2)*2[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2"
        % (ancho_bg, alto_bg, ancho_bg, alto_bg,
           BLUR_SIGMA, FONDO_BRILLO, FONDO_SATURACION,
           TL_ANCHO, TL_ALTO, x0, x1 - x0, dur, y0, y1 - y0, dur,
           ancho_fg, alto_fg))

    os.makedirs(os.path.dirname(destino), exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-loop", "1",
         "-framerate", "%d/%d" % (TL_NUM, TL_DEN), "-i", origen,
         "-t", "%g" % dur, "-filter_complex", filtro,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-an", "-y", destino],
        capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg fallo componiendo %s:\n%s"
                           % (os.path.basename(origen), r.stderr.strip()[:400]))
    return destino


def recolectar(manifest, avisar=None):
    """Sonda todos los archivos y, si toca, hornea las imagenes. Cada entrada
    lleva `imagen`, que dice que **beat** es, y `ruta`, que es el archivo que
    acaba en el timeline: para una imagen compuesta, el mp4, no el jpg."""
    entradas, faltan = [], []
    pendientes = []
    for seccion in manifest["secciones"]:
        for recurso in seccion["recursos"]:
            for rel in recurso["archivos"]:
                ruta = os.path.join(AQUI, rel.replace("/", os.sep))
                if not os.path.isfile(ruta):
                    faltan.append(rel)
                    continue
                pendientes.append((seccion, recurso, ruta))

    imgs = [p for p in pendientes
            if os.path.splitext(p[2])[1].lower() not in EXT_VIDEO]

    # si la receta cambio, los compuestos de disco ya no valen aunque sean mas
    # nuevos que su origen
    receta = os.path.join(AQUI, "compuestos", ".receta")
    firma = _firma_receta()
    previa = None
    if os.path.isfile(receta):
        with open(receta, encoding="utf-8") as f:
            previa = f.read().strip()
    rehacer = previa != firma

    def _destino(ruta):
        base = os.path.splitext(os.path.basename(ruta))[0]
        return os.path.join(AQUI, "compuestos", base + "_comp.mp4")

    if COMPONER_IMAGENES and imgs and avisar:
        por_hacer = [p for p in imgs
                     if rehacer or not os.path.isfile(_destino(p[2]))
                     or os.path.getmtime(_destino(p[2])) < os.path.getmtime(p[2])]
        if por_hacer:
            avisar("componiendo %d de %d imagenes%s..."
                   % (len(por_hacer), len(imgs),
                      " (receta nueva)" if rehacer and previa else ""))

    n_img = 0
    for seccion, recurso, ruta in pendientes:
        es_img = os.path.splitext(ruta)[1].lower() not in EXT_VIDEO
        origen = ruta
        if es_img and COMPONER_IMAGENES:
            ruta = componer(ruta, _destino(ruta), direccion=n_img, forzar=rehacer)
            n_img += 1
        entradas.append({"seccion": seccion, "recurso": recurso,
                         "ruta": ruta, "origen": origen, "imagen": es_img,
                         "info": sondear(ruta)})

    if COMPONER_IMAGENES and imgs:
        os.makedirs(os.path.dirname(receta), exist_ok=True)
        with open(receta, "w", encoding="utf-8") as f:
            f.write(firma)
    return entradas, faltan


def planificar(manifest, entradas):
    """Asigna frames y fragmentos a cada entrada de video. Devuelve el informe
    por seccion."""
    total = int(OBJETIVO_TOTAL_S * FPS_TL)
    palabras = sum(s.get("palabras", 1) for s in manifest["secciones"])
    restante = {}
    for e in entradas:
        if not e["imagen"] and e["ruta"] not in restante:
            restante[e["ruta"]] = capacidad(e["info"])

    informe = []
    for seccion in manifest["secciones"]:
        ents = [e for e in entradas if e["seccion"] is seccion]
        imgs = [e for e in ents if e["imagen"]]
        vids = [e for e in ents if not e["imagen"]]
        presupuesto = int(total * seccion.get("palabras", 1) / palabras)
        frames_img = len(imgs) * FRAMES_IMAGEN
        presupuesto_v = max(0, presupuesto - frames_img)

        for e, f in zip(vids, repartir(presupuesto_v, [restante[e["ruta"]] for e in vids])):
            e["frames"] = f
            restante[e["ruta"]] -= f

        # fragmentos: los que pida la duracion, y al menos los necesarios para
        # cortar las rachas de imagenes
        for e in vids:
            e["n_seg"] = max(1, int(round(e["frames"] / (DUR_SEGMENTO * FPS_TL))))
        necesarios = max(0, -(-len(imgs) // MAX_IMG_SEGUIDAS) - 1)
        while vids and sum(e["n_seg"] for e in vids) < necesarios:
            e = max(vids, key=lambda e: e["frames"] / e["n_seg"])
            if e["frames"] // (e["n_seg"] + 1) < 1:
                break
            e["n_seg"] += 1

        informe.append({"seccion": seccion, "presupuesto": presupuesto,
                        "imgs": len(imgs), "vids": len(vids),
                        "frames_video": sum(e["frames"] for e in vids),
                        "frames_img": frames_img,
                        "segmentos": sum(e["n_seg"] for e in vids),
                        "necesarios": necesarios})

    # posiciones: los fragmentos de una fuente se reparten por todo el clip,
    # contando los que pidan todas las secciones donde aparece
    por_ruta = Counter()
    for e in entradas:
        if not e["imagen"]:
            por_ruta[e["ruta"]] += e["n_seg"]
    cursor = defaultdict(int)
    for e in entradas:
        if e["imagen"]:
            continue
        info = e["info"]
        fps_src = info["num"] / info["den"]
        # la transicion come MEDIA_TRANS a cada lado del corte, asi que ningun
        # fragmento puede empezar antes ni acabar despues de ese margen
        handle = int(round(HANDLE / FPS_TL * fps_src)) + 2
        ini_util = max(handle, int(info["frames"] * MARGEN))
        fin_util = min(info["frames"] - handle,
                       info["frames"] - int(info["frames"] * MARGEN))
        bloque = max(1, (fin_util - ini_util) // max(1, por_ruta[e["ruta"]]))
        base, resto = divmod(e["frames"], e["n_seg"])
        tramos = []
        for i in range(e["n_seg"]):
            dur_tl = base + (1 if i < resto else 0)
            if dur_tl <= 0:
                continue
            k = cursor[e["ruta"]]
            cursor[e["ruta"]] += 1
            largo = int(round(dur_tl / FPS_TL * fps_src))
            arranque = min(ini_util + k * bloque, max(handle, fin_util - largo))
            arranque = max(handle, min(arranque, info["frames"] - largo - handle))
            tramos.append((max(0, arranque), dur_tl))
        e["tramos"] = tramos
    return informe


def ordenar(ents):
    """Entrelaza para no dejar mas de MAX_IMG_SEGUIDAS imagenes juntas."""
    imgs = [(e, (HANDLE, FRAMES_IMAGEN)) for e in ents if e["imagen"]]
    colas = [[(e, t) for t in e["tramos"]] for e in ents if not e["imagen"]]
    vids = []
    while any(colas):
        for c in colas:
            if c:
                vids.append(c.pop(0))
    salida, i, j = [], 0, 0
    while i < len(imgs) or j < len(vids):
        for _ in range(MAX_IMG_SEGUIDAS):
            if i < len(imgs):
                salida.append(imgs[i])
                i += 1
        if j < len(vids):
            salida.append(vids[j])
            j += 1
    return salida


def construir_fcpxml(manifest, avisar=None):
    entradas, faltan = recolectar(manifest, avisar)
    informe = planificar(manifest, entradas)

    formatos, assets, clips = {}, [], []
    cache = {}

    def id_formato(clave, gen):
        if clave not in formatos:
            fid = "r%d" % (len(formatos) + 1)
            formatos[clave] = (fid, gen(fid))
        return formatos[clave][0]

    # un <effect> por uid distinto que pida el ciclo
    efectos_id = {}
    for _, preset, uid in TRANSICION_CICLO:
        if preset is not None:
            u = uid or EFECTO_UID
            efectos_id.setdefault(u, "e%d" % (len(efectos_id) + 1))
    id_formato(("tl",),
               lambda f: '<format id="%s" name="FFVideoFormat1080p2398" '
                         'frameDuration="%d/%ds" width="%d" height="%d" '
                         'colorSpace="1-1-1 (Rec. 709)"/>'
                         % (f, TL_DEN, TL_NUM, TL_ANCHO, TL_ALTO))
    fid_tl = formatos[("tl",)][0]

    def asset_de(e):
        ruta, info = e["ruta"], e["info"]
        if ruta in cache:
            return cache[ruta]
        aid = "a%d" % (len(cache) + 1)
        uid = hashlib.md5(ruta.encode("utf-8")).hexdigest().upper()
        if info["video"]:
            fid = id_formato(
                ("v", info["ancho"], info["alto"], info["num"], info["den"]),
                lambda f, i=info: '<format id="%s" name="FFVideoFormatCustom" '
                                  'frameDuration="%d/%ds" width="%d" height="%d" '
                                  'colorSpace="1-1-1 (Rec. 709)"/>'
                                  % (f, i["den"], i["num"], i["ancho"], i["alto"]))
            dur = t_fuente(info["frames"], info["num"], info["den"])
            audio = ""
            if info["canales"]:
                audio = (' hasAudio="1" audioSources="1" audioChannels="%d" '
                         'audioRate="%d"' % (info["canales"], info["tasa"]))
        else:
            # el still hereda la tasa del timeline: un format sin frameDuration
            # tumba el importador de Resolve
            fid = id_formato(
                ("i", info["ancho"], info["alto"]),
                lambda f, i=info: '<format id="%s" name="FFVideoFormatCustom" '
                                  'frameDuration="%d/%ds" width="%d" height="%d" '
                                  'colorSpace="1-13-1"/>'
                                  % (f, TL_DEN, TL_NUM, i["ancho"], i["alto"]))
            dur = t_timeline(FRAMES_IMAGEN)
            audio = ""
        assets.append(
            '<asset id="%s" name="%s" uid="%s" start="0s" duration="%s" '
            'hasVideo="1" videoSources="1" format="%s"%s>'
            '<media-rep kind="original-media" src="%s"/></asset>'
            % (aid, attr(os.path.splitext(os.path.basename(ruta))[0]), uid,
               dur, fid, audio, attr(file_url(ruta))))
        cache[ruta] = (aid, fid)
        return cache[ruta]

    pos = 0
    posiciones = []
    marcados = set()
    frames_img_tot = 0
    for seccion in manifest["secciones"]:
        ents = [e for e in entradas if e["seccion"] is seccion]
        for e, (ini_src, dur_tl) in ordenar(ents):
            info = e["info"]
            aid, fid = asset_de(e)
            if info["video"]:
                inicio = t_fuente(ini_src, info["num"], info["den"])
                dur_marca = t_fuente(1, info["num"], info["den"])
            else:
                inicio = "0s"
                dur_marca = t_timeline(1)
            if e["imagen"]:
                frames_img_tot += dur_tl

            clave = (seccion["n"], e["recurso"]["id"])
            marcador = ""
            if clave not in marcados:
                marcados.add(clave)
                marcador = '<marker start="%s" duration="%s" value="%s"/>' % (
                    inicio, dur_marca,
                    attr("S%s %s | %s | %s" % (seccion["n"], e["recurso"]["id"],
                                               e["recurso"]["frase"],
                                               e["recurso"]["credito"])))

            clips.append(
                '<asset-clip ref="%s" offset="%s" name="%s" start="%s" duration="%s" '
                'format="%s" tcFormat="NDF">%s</asset-clip>'
                % (aid, t_timeline(pos),
                   attr(os.path.splitext(os.path.basename(e["ruta"]))[0]),
                   inicio, t_timeline(dur_tl), fid, marcador))
            posiciones.append((pos, dur_tl))
            pos += dur_tl

    # Las transiciones no anaden tiempo: se centran en el corte y se comen el
    # handle de los dos clips. Por eso los offsets de los clips no cambian.
    elementos = []
    for i, c in enumerate(clips):
        elementos.append(c)
        if TRANSICIONES and i + 1 < len(clips):
            corte = posiciones[i][0] + posiciones[i][1]
            # indexar por numero de corte, no por len(elementos): esa lista
            # crece con clips Y transiciones, y el ciclo saldria desordenado
            tipo, preset, uid = TRANSICION_CICLO[i % len(TRANSICION_CICLO)]
            cuerpo = ("" if preset is None
                      else '<filter-video ref="%s" name="%s"/>'
                           % (efectos_id[uid or EFECTO_UID], attr(preset)))
            elementos.append(
                '<transition name="%s" offset="%s" duration="%s">%s</transition>'
                % (attr(tipo), t_timeline(corte - MEDIA_TRANS),
                   t_timeline(FRAMES_TRANS), cuerpo))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<!DOCTYPE fcpxml>",
           '<fcpxml version="1.9">', "<resources>"]
    # un <effect> por uid referenciado; declararlos sueltos no rompe nada pero
    # ensucia el archivo
    if TRANSICIONES:
        for u, eid in efectos_id.items():
            nombre_ef = next(t for t, pr, ui in TRANSICION_CICLO
                             if pr is not None and (ui or EFECTO_UID) == u)
            xml.append('<effect id="%s" name="%s" uid="%s"/>'
                       % (eid, attr(nombre_ef), attr(u)))
    xml += [x for _, x in formatos.values()]
    xml += assets
    xml.append("</resources>")
    xml.append('<library><event name="%s">' % attr("B-ROLL " + manifest["proyecto"]))
    xml.append('<project name="B-ROLL GUIA">')
    xml.append('<sequence format="%s" duration="%s" tcStart="0s" tcFormat="NDF" '
               'audioLayout="stereo" audioRate="48k"><spine>' % (fid_tl, t_timeline(pos)))
    xml += elementos
    xml.append("</spine></sequence></project></event></library></fcpxml>")

    stats = {"frames": pos, "clips": len(clips), "assets": len(cache),
             "marcadores": len(marcados), "frames_img": frames_img_tot,
             "transiciones": len(elementos) - len(clips),
             "faltan": faltan, "informe": informe, "entradas": entradas}
    return "\n".join(xml), stats


def arbol_por_seccion(manifest, entradas=None):
    raiz = os.path.join(AQUI, "por-seccion")
    creados = reutilizados = copiados = 0
    extra = defaultdict(list)
    for e in entradas or []:
        if e["ruta"] != e.get("origen"):
            extra[e["seccion"]["n"]].append(e["ruta"])
    for seccion in manifest["secciones"]:
        destino = os.path.join(raiz, "%s %s" % (seccion["n"], seccion["titulo"]))
        os.makedirs(destino, exist_ok=True)
        fuentes = [os.path.join(AQUI, rel.replace("/", os.sep))
                   for recurso in seccion["recursos"] for rel in recurso["archivos"]]
        fuentes += extra[seccion["n"]]
        for origen in fuentes:
                if not os.path.isfile(origen):
                    continue
                enlace = os.path.join(destino, os.path.basename(origen))
                if os.path.exists(enlace):
                    reutilizados += 1
                    continue
                try:
                    os.link(origen, enlace)
                    creados += 1
                except OSError:
                    import shutil
                    shutil.copy2(origen, enlace)
                    copiados += 1
    return creados, reutilizados, copiados


def mmss(segundos):
    return "%d:%02d" % (segundos // 60, segundos % 60)


def main():
    ruta_manifest = os.path.join(AQUI, "manifest.json")
    if not os.path.isfile(ruta_manifest):
        print("ERROR: falta manifest.json junto al script")
        return 1
    with open(ruta_manifest, encoding="utf-8") as f:
        manifest = json.load(f)

    if "--sondeo" in sys.argv:
        global TRANSICION_CICLO
        _fcp = ".../Transitions.localized/%s.localized/%s.localized/%s.effectBundle"
        TRANSICION_CICLO = [
            ("Slide", "Slide", _fcp % ("Movements", "Slide", "Slide")),
            ("Push", "Push", _fcp % ("Movements", "Push", "Push")),
            ("Slide", "Slide", ".../Transitions.localized/Movements.localized/"
                               "Slide.localized/Slide.moti"),
            ("Slide", "Slide", "DaVinci:Slide"),
            ("Cross Dissolve", "Cross Dissolve",
             _fcp % ("Dissolves", "Cross Dissolve", "Cross Dissolve")),
        ]
        # solo imagenes: cada una es exactamente un clip, asi cada corte se
        # queda con un nombre distinto del ciclo y el sondeo es legible
        recursos = [r for s_ in manifest["secciones"] for r in s_["recursos"]
                    if os.path.splitext(r["archivos"][0])[1].lower() not in EXT_VIDEO]
        elegidos = [dict(r, archivos=r["archivos"][:1])
                    for r in recursos[:len(TRANSICION_CICLO) + 1]]
        manifest = {"proyecto": manifest["proyecto"],
                    "secciones": [{"n": "01", "titulo": "Sondeo", "palabras": 100,
                                   "recursos": elegidos}]}
        xml, st = construir_fcpxml(manifest)
        with open(os.path.join(AQUI, "B-ROLL-SONDEO.fcpxml"), "w", encoding="utf-8") as f:
            f.write(xml)
        print("B-ROLL-SONDEO.fcpxml: %d clips, %d transiciones"
              % (st["clips"], st["transiciones"]))
        for i, (tipo, preset, uid) in enumerate(TRANSICION_CICLO[:st["transiciones"]], 1):
            print("  corte %d -> %-14s uid=%s" % (i, tipo, uid))
        return 0

    if "--prueba" in sys.argv:
        recursos = [r for s in manifest["secciones"] for r in s["recursos"]]
        imagen = next(r for r in recursos
                      if os.path.splitext(r["archivos"][0])[1].lower() not in EXT_VIDEO)
        video = next(r for r in recursos
                     if os.path.splitext(r["archivos"][0])[1].lower() in EXT_VIDEO)
        manifest = {"proyecto": manifest["proyecto"],
                    "secciones": [{"n": "01", "titulo": "Prueba", "palabras": 100,
                                   "recursos": [dict(imagen, archivos=imagen["archivos"][:1]),
                                                video]}]}
        xml, st = construir_fcpxml(manifest)
        with open(os.path.join(AQUI, "B-ROLL-PRUEBA.fcpxml"), "w", encoding="utf-8") as f:
            f.write(xml)
        print("B-ROLL-PRUEBA.fcpxml: %d clips" % st["clips"])
        return 0

    xml, st = construir_fcpxml(manifest, avisar=print)
    nombre = "B-ROLL-GUIA.fcpxml"
    with open(os.path.join(AQUI, nombre), "w", encoding="utf-8") as f:
        f.write(xml)
    creados, reutilizados, copiados = arbol_por_seccion(manifest, st["entradas"])

    guion = manifest.get("guion", {})
    palabras = guion.get("palabras")
    total_s = st["frames"] / FPS_TL
    video_s = (st["frames"] - st["frames_img"]) / FPS_TL

    print("por-seccion/    %d enlaces nuevos, %d ya estaban, %d copiados"
          % (creados, reutilizados, copiados))
    if palabras:
        print("guion           %d palabras -> %s narrados a %d ppm"
              % (palabras, mmss(palabras / PALABRAS_POR_MINUTO * 60), PALABRAS_POR_MINUTO))
    print("%-30s %s   %d clips, %d transiciones, %d marcadores, %d archivos"
          % (nombre, mmss(total_s), st["clips"], st["transiciones"],
             st["marcadores"], st["assets"]))
    print("  video %s (%.0f%%)   imagen %s (%.0f%%)"
          % (mmss(video_s), 100 * video_s / total_s,
             mmss(st["frames_img"] / FPS_TL), 100 * st["frames_img"] / st["frames"]))
    print()
    print("  %-26s %5s %7s %7s %7s  %s" %
          ("seccion", "palab", "guion", "broll", "video%", "img/vid"))
    for r in st["informe"]:
        s = r["seccion"]
        dur = (r["frames_video"] + r["frames_img"]) / FPS_TL
        narr = s.get("palabras", 0) / PALABRAS_POR_MINUTO * 60
        pct = 100 * r["frames_video"] / max(1, r["frames_video"] + r["frames_img"])
        aviso = "" if r["segmentos"] >= r["necesarios"] else "  <-- faltan cortes"
        print("  %-26s %5d %7s %7s %6.0f%%  %d/%d en %d frag%s"
              % (s.get("beat", s["titulo"])[:26], s.get("palabras", 0),
                 mmss(narr), mmss(dur), pct, r["imgs"], r["vids"],
                 r["segmentos"], aviso))
    if st["faltan"]:
        print("  FALTAN: %s" % ", ".join(st["faltan"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
