# Comandos de descarga

Todo baja al `B-roll\` de la pieza y se nombra `<ID>_<slug>.<ext>` desde el momento en que toca
el disco. Renombrar despues es como se pierden los creditos.

## Regla de codec

Resolve free en Windows no decodifica VP9, AV1 ni WebP. Un clip AV1 abre como pantalla negra o
no importa. Por eso:

| Se quiere | No sirve |
|---|---|
| Video H.264 (`avc1`) en MP4 | VP9, AV1 |
| Audio AAC (`m4a`) | Opus |
| Imagen PNG o JPG | WebP, AVIF |

YouTube sirve AV1 por defecto en muchos videos, y `og:image` de medios modernos suele ser WebP.
Los dos casos hay que forzarlos.

---

## Trailer desde Steam

Con el `hls_h264` que da `appdetails`, sin recodificar:

```bash
ffmpeg -i "<url_hls_h264>" -c copy -bsf:a aac_adtstoasc "B12_trailer-lanzamiento.mp4"
```

Sale 1920x1080 H.264 + AAC. Los avisos `missing picture in access unit` y `Invalid NAL unit
size` de los primeros frames son normales en HLS y no dañan el archivo. Comprobar con:

```bash
ffprobe -v error -show_entries stream=codec_name,width,height -of csv=p=0 "B12_trailer-lanzamiento.mp4"
```

Debe decir `h264,1920,1080`.

---

## Video desde YouTube

### Dos requisitos de yt-dlp

**1. `--js-runtimes node` en toda llamada a YouTube.** Desde 2026 yt-dlp necesita un runtime de
JavaScript y solo habilita deno por defecto. Sin el avisa
`No supported JavaScript runtime could be found` y **faltan formatos**, incluido el AVC de
1080p que hace falta. Node ya esta instalado, basta con nombrarlo.

**2. El binario esta fuera del PATH hasta reiniciar la shell.** winget lo dejo en:

```
%LOCALAPPDATA%\Microsoft\WinGet\Packages\yt-dlp.yt-dlp_Microsoft.Winget.Source_8wekyb3d8bbwe\yt-dlp.exe
```

Si `command -v yt-dlp` no devuelve nada, usar esa ruta completa.

### Descarga

Trailer oficial, gameplay propio o free use. Forzar AVC y M4A:

```bash
yt-dlp --js-runtimes node \
  -f "bv*[vcodec^=avc1][height<=1080]+ba[ext=m4a]/b[ext=mp4]" \
  --merge-output-format mp4 \
  --write-info-json \
  -o "B14_trailer-gameplay.%(ext)s" \
  "URL"
```

**[verificado 2026-08-03]** Con `--js-runtimes node` el selector resuelve a `299+140`
(AVC 1080p60 + AAC). Sin el, el mismo comando cae a otro formato.

`--write-info-json` es obligatorio: de ahi salen `uploader`, `channel_url`, `upload_date` y
`license` para `CREDITOS.txt`. Sin el hay que reconstruir los datos a mano.

Si el video no tiene AVC a 1080p, yt-dlp cae al fallback y puede traer AV1. Comprobar con
ffprobe y, si paso, transcodificar:

```bash
ffmpeg -i entrada.webm -c:v dnxhd -profile:v dnxhr_lb -pix_fmt yuv422p -c:a pcm_s16le salida.mov
```

DNxHR LB pesa mas pero Resolve lo corta sin renderizar. Para 4K, bajar a `[height<=2160]` solo
si el guion lo justifica; 1080p es suficiente para un plano de apoyo de tres segundos.

### Solo un tramo de un video largo

Para gameplay propio o directos, evita bajar dos horas para usar ocho segundos:

```bash
yt-dlp --js-runtimes node \
  -f "bv*[vcodec^=avc1][height<=1080]+ba[ext=m4a]/b[ext=mp4]" \
  --download-sections "*00:12:30-00:13:10" \
  --merge-output-format mp4 --write-info-json \
  -o "B09_gameplay-jefe.%(ext)s" "URL"
```

Dejar margen de unos segundos a cada lado. El corte fino se hace en Resolve, no aqui.

---

## Master local en vez de descarga

Si el gameplay esta en disco, copiar el tramo sin recodificar:

```bash
ffmpeg -ss 00:12:30 -i "$CARPETA_VIDEO/VID_2026_03_11/grabacion.mp4" \
  -t 00:00:40 -c copy "B09_gameplay-jefe.mp4"
```

`-ss` antes de `-i` es rapido pero corta en el keyframe anterior, asi que el inicio real puede
irse hasta un par de segundos. Para un plano de apoyo no importa. Si tiene que ser exacto,
mover `-ss` despues de `-i` y aceptar que recodifica.

---

## Capturas de pagina

Para articulos de prensa y fichas de tienda:

```bash
node "$HOME/.claude/skills/broll/scripts/capturar.js" "URL" "B07_ign-analisis.png"
```

Navega a 1920x1080, **descarta el banner de cookies** y dispara. Añadir `--full` para pagina
entera, pero para B-roll casi siempre se quiere el viewport: entra el titular con la firma y
nada mas.

El script solo pulsa opciones de **rechazar** o de **cerrar**, nunca "Accept". Aceptar terminos
en nombre de otro no es decision de un script. Si la pagina solo ofrece aceptar, informa
`no habia, o ninguno era rechazable` y captura igual, con el banner puesto.

Necesita el paquete resoluble desde el directorio donde se ejecuta:

```bash
npm install playwright
```

**[verificado 2026-08-03]** En NPR, sin descartar el banner, el overlay atenua **la pagina
entera** y la captura queda gris e inservible. Con el script, limpia. Variety, Den of Geek,
FirstShowing, MovieWeb, Murphy's Multiverse y Metacritic no mostraron banner rechazable.

### Que revisar en cada captura

Mirar la imagen antes de darla por buena. Los dos fallos que salen siempre:

| Sintoma | Que hacer |
|---|---|
| Banda en blanco arriba | Hueco de publicidad sin cargar. Recortar. En Variety fueron ~270 px |
| Banner de anunciante arriba | Recortar. Metacritic sirve uno de GameSpot |

### Imagen suelta que llega en WebP

```bash
ffmpeg -i cabecera.webp "B08_cabecera.png"
```

---

## Verificacion final

Antes de escribir `CREDITOS.txt`, pasar todo lo bajado:

```bash
for f in videos/*/*.mp4; do
  printf "%s: " "$f"
  ffprobe -v error -show_entries stream=codec_name -select_streams v:0 -of csv=p=0 "$f"
done
```

Cualquier cosa que no diga `h264` se transcodifica o se reporta. No dar por buena una carpeta
sin haber corrido esto.
