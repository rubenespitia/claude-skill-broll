# Fuentes por tipo de recurso

Lo marcado **[verificado 2026-08-03]** se probo con una llamada real. Lo demas es la ruta
prevista y hay que confirmarlo la primera vez que se use.

---

## Imagenes de prensa

Lo que se busca es una **cita con cara visible**: titular, medio y firma en pantalla. Por eso
casi siempre es una captura de la pagina del articulo, no la imagen de cabecera suelta.

### Encontrar articulos

`WebSearch` con el nombre del juego mas el termino del medio. Medios utiles:

| Español | Ingles |
|---|---|
| Vandal, 3DJuegos, Meristation | IGN, GameSpot, Polygon |
| Hobby Consolas, Eurogamer.es | PC Gamer, Eurogamer, RPS |
| Nivel Oculto, AreaJugones | Kotaku, Digital Foundry |

Metacritic y OpenCritic sirven para el agregado y para descubrir quien reseño, pero la captura
va del articulo original: el agregador no es el autor.

### Sacar autor y fecha

```bash
node "$HOME/.claude/skills/broll/scripts/ldjson.js" "URL"
```

Devuelve `{tipo, titular, autor, fecha, medio}` desde el JSON-LD del articulo, y cae a los meta
tags (`article:author`, `article:published_time`) si no hay JSON-LD.

**[verificado 2026-08-03]** Funciona en Eurogamer e IGN. Eurogamer usa `date_published` y no
`datePublished`, por eso no vale grepear un solo nombre de campo: el script mira los dos.

Cuando imprime `sin autor ni fecha`, casi siempre es una de estas tres:

| Causa | Que hacer |
|---|---|
| La URL redirige a otra pagina | Comprobar con `curl -sLo /dev/null -w "%{url_effective}"` |
| El medio pinta la firma en cliente | Abrir en el browser y leer el DOM |
| El articulo de verdad no firma | Descartar el recurso |

`WebFetch` no sirve para esto: devuelve texto ya procesado y en varios medios se come la firma.

**Si no hay autor, el recurso se descarta.** Poner el nombre del medio en su lugar no es
acreditar.

### Capturas oficiales del juego

Antes de recortar prensa, mirar si Steam ya da la imagen. Vienen a 1920x1080, son material
oficial de prensa y no hay que capturar nada:

```bash
curl -s "https://store.steampowered.com/api/appdetails?appids=<appid>" \
  | jq -r '."<appid>".data.screenshots[].path_full'
```

**[verificado 2026-08-03]** Silksong (1030300) devuelve 10 capturas, `path_full` a 1920x1080.
El `path_thumbnail` es 600x338 y no sirve para 1080p.

---

## Precios en tiendas

Un precio caduca. En `CREDITOS.txt` van siempre **region y fecha de consulta**, y si el precio
aparece en pantalla, la region deberia verse o decirse.

### Steam

**[verificado 2026-08-03]**

```bash
curl -s "https://store.steampowered.com/api/appdetails?appids=1030300&cc=co&l=spanish&filters=price_overview"
```

Devuelve `currency`, `initial`, `final`, `discount_percent`, `final_formatted`. El `cc` manda
sobre la region, no la cuenta desde la que se llama: `co` Colombia, `es` España, `mx` Mexico,
`us` Estados Unidos, `ar` Argentina.

Trampa: `initial_formatted` viene **vacio** cuando no hay descuento. Usar `final_formatted`
siempre y `initial_formatted` solo si `discount_percent > 0`.

### Nintendo eShop

**[verificado 2026-08-03]**

```bash
curl -s "https://api.ec.nintendo.com/v1/price?country=US&lang=en&ids=<nsuid>"
```

Devuelve `regular_price` y, si hay oferta, `discount_price`. Necesita el **nsuid**, que no es el
ID de la ficha web: sale del `og:` o del JSON de la pagina del juego en nintendo.com, o buscando
el titulo en la API de busqueda de la region. Sin key.

### PlayStation Store y Xbox

Sin API publica estable. Captura de la ficha de tienda con Playwright, comando en
`reference/descarga.md`. La captura ya lleva el precio y el logo de la tienda, que es justo lo
que hace falta en pantalla.

---

## Trailers

### Ruta preferida: Steam, sin yt-dlp

**[verificado 2026-08-03]** El trailer llega en H.264 directo, que es lo que Resolve quiere:

```bash
curl -s "https://store.steampowered.com/api/appdetails?appids=<appid>" \
  | jq -r '."<appid>".data.movies[] | "\(.name)\t\(.hls_h264)"'
```

Cada entrada trae `hls_h264` (m3u8), `dash_h264` y `dash_av1`. **Coger siempre el `h264`**, nunca
el `av1`. La descarga con ffmpeg esta en `reference/descarga.md`; probada, sale 1920x1080 H.264
con audio AAC. Los avisos `missing picture in access unit` del arranque son cosmeticos.

El campo antiguo `movies[].mp4.max` ya no existe. Documentacion vieja que lo mencione esta
desactualizada.

### Ruta alternativa: canal oficial en YouTube

Para juegos sin Steam (Nintendo, exclusivos de PS) o trailers que Steam no publica. yt-dlp
forzando AVC, comando en `reference/descarga.md`. Verificar que el canal es el del publisher y
no un reuploader: el credito va al publisher.

---

## Cine

### Localizar trailers sin adivinar URLs

yt-dlp busca en YouTube y devuelve canal, ID, duracion y fecha reales. Mucho mas fiable que
componer una URL a mano:

```bash
yt-dlp --js-runtimes node --skip-download --no-warnings \
  --print "%(uploader)s :: %(title)s :: %(id)s :: %(duration)ss :: %(upload_date)s" \
  "ytsearch1:<pelicula> official trailer <estudio>"
```

**[verificado 2026-08-03]** Resolvio los siete trailers de la review de Brand New Day al primer
intento, todos en canal oficial (Sony Pictures Entertainment, Marvel Entertainment).

Comprobar el `uploader`: el mismo trailer suele estar subido en varios canales y el credito va
al oficial. En Brand New Day aparecia tambien en el canal de PlayStation.

### Metraje de la pelicula

**No hay fuente legitima de clips.** Lo que se puede mostrar de una pelicula sale de tres
sitios: el trailer, los stills oficiales y el poster. Decirlo una vez al proponer candidatos, no
en cada linea.

### Posters y stills: TMDB

**[verificado 2026-08-03 con token real]** Key gratis en themoviedb.org/settings/api, plan
Developer. Autenticacion por cabecera, nunca por query string:

```bash
set -a; . ~/.claude/.env.broll; set +a
curl -s -H "Authorization: Bearer $TMDB_READ_TOKEN" \
  "https://api.themoviedb.org/3/search/movie?query=Spider-Man%20Homecoming&year=2017&language=es-MX" \
  | jq -r '.results[0] | "\(.id)\t\(.title)\t\(.poster_path)"'
```

**Trampa que cuesta media descarga.** El `poster_path` que devuelve `search` con
`language=es-MX` es el poster localizado, y las versiones en español suelen ser subidas mas
pequeñas: Homecoming salio a **756x1068** y Into the Spider-Verse a **728x1080**, mientras las
otras cuatro venian a 2000x3000.

Para no depender de eso, pedir todas las versiones y ordenar por ancho:

```bash
curl -s -H "Authorization: Bearer $TMDB_READ_TOKEN" \
  "https://api.themoviedb.org/3/movie/315635/images" \
  | jq -r '[.posters[] | {w: .width, h: .height, lang: (.iso_639_1 // "sin idioma"), path: .file_path}]
           | sort_by(-.w) | .[0:3] | .[] | "\(.w)x\(.h)  \(.lang)  \(.path)"'
```

Al maximo casi siempre hay un 2000x3000. Si en español no lo hay a ese tamaño, coger el ingles:
en un montaje de posters el idioma del titulo se nota mucho menos que un poster borroso.

La imagen se compone con el CDN, que no pide autenticacion:

```
https://image.tmdb.org/t/p/original<file_path>
```

`/movie/<id>/images` da tambien `backdrops` (stills horizontales, tipicos 3840x2160) y `logos`.

### Atribucion obligatoria de TMDB

La key gratuita **exige** acreditar. En un video eso va en la descripcion:

```
This product uses the TMDB API but is not endorsed or certified by TMDB.
```

Va como linea obligatoria en `CREDITOS.txt` en cuanto se use un solo recurso de TMDB. El plan
Developer es solo para uso no comercial; si el canal se monetiza, TMDB pide licencia comercial.

### Alternativa sin key

```bash
curl -s "https://en.wikipedia.org/api/rest_v1/page/summary/Spider-Man:_Brand_New_Day" \
  | jq -r '.originalimage.source'
```

**[verificado 2026-08-03]** Sin key, pero devuelve el poster a **258x387**. Sirve para
identificar cual es, no para ponerlo en pantalla.

### Stills sin TMDB

Un frame del trailer que ya se descargo, gratis y a 1920x1080:

```bash
ffmpeg -ss 00:01:12 -i B01_trailer-oficial.mp4 -frames:v 1 B16_still.png
```

### Prensa de cine

El mismo `scripts/ldjson.js`. Medios que responden bien: Variety, Den of Geek, NPR,
FirstShowing, IndieWire, Hollywood Reporter. En español: Espinof, SensaCine, Cinemania.

Metacritic y Rotten Tomatoes para el plano del agregado, pero la cita va del articulo original.

Cuidado con los agregadores de rumores (MovieWeb, Murphy's Multiverse, ScreenRant). Sirven para
documentar que **se reporto** algo, no para afirmar que ocurrio. Si el guion se apoya en uno,
avisar para que la frase se quede en "se reporto" y no suba a "se confirmo".

### Taquilla

Es el equivalente al precio de tienda de los juegos, pero **solo si el guion habla de dinero**.
Box Office Mojo y The Numbers. No meterlo por defecto.

---

## Gameplay propio del canal

**Primero el disco.** El master local no esta recomprimido y no lo throttlea nadie:

```
<CARPETA_VIDEO>\VID_YYYY_MM_DD-titulo\
```

Solo si no esta en disco, bajar de `@WantedGull` con yt-dlp.

Para localizar el momento exacto dentro de un directo largo, los subtitulos automaticos bajan
rapido aunque el video vaya lento — el mismo truco que usa la skill `stream-thumbnail`:

```bash
yt-dlp --js-runtimes node --write-auto-sub --sub-lang "es.*" --skip-download --sub-format vtt URL
```

Buscar en el VTT el nombre del jefe, el modo o la mecanica que menciona el guion, y sacar el
timestamp. En `candidatos.md` va el rango, no el video entero.

---

## Gameplay free use

Prioridad baja, solo cuando no hay material propio ni trailer que sirva.

En YouTube, filtro de Creative Commons en la busqueda: añadir `&sp=EgIwAQ%3D%3D` a la URL de
resultados. No basta: **verificar el campo `license` del info json** antes de dar por buena la
licencia, porque muchos titulos dicen "free use" sin serlo.

```bash
yt-dlp --js-runtimes node --skip-download --print "%(license)s | %(uploader)s | %(upload_date)s" URL
```

**[verificado 2026-08-03]** Devuelve `NA` cuando el video es licencia estandar de YouTube. Solo
vale si dice Creative Commons.

Si `license` no dice Creative Commons, el video no entra. Un "free to use" escrito en la
descripcion no es una licencia verificable y no se acepta.

---

## Stock gratuito

Las keys viven en `~/.claude/.env.broll`, nunca en esta carpeta.

Cargar las keys sin imprimirlas:

```bash
set -a; . ~/.claude/.env.broll; set +a
```

### Pexels

**[verificado 2026-08-03 con key real]**

```bash
curl -s -H "Authorization: $PEXELS_API_KEY" \
  "https://api.pexels.com/videos/search?query=<tema>&per_page=15&orientation=landscape"
```

De cada `videos[]`: `user.name` y `user.url` para el credito, `url` (pagina del clip),
`duration`, y el enlace real en `video_files[]`, filtrando `file_type == "video/mp4"`.

`size` es un **minimo, no un tamaño exacto**: con `size=medium` siguen saliendo clips de
3840x2160. Para quedarse en 1080p hay que filtrar por ancho al elegir el `video_files[]`:

```bash
jq -r '[.videos[0].video_files[] | select(.file_type=="video/mp4" and .width<=1920)]
       | max_by(.width) | .link'
```

### Pixabay

**[verificado 2026-08-03 con key real]**

```bash
curl -s "https://pixabay.com/api/videos/?key=$PIXABAY_API_KEY&q=<tema>&video_type=film&per_page=15"
```

De cada `hits[]`: `user` para el credito, `pageURL`, `duration`, `tags` y `videos.large.url`.

Trampa: `per_page` **minimo 3**. Con `per_page=1` devuelve texto plano, no JSON:
`[ERROR 400] "per_page" is out of valid range.`, y jq revienta con un error de parseo que no
dice nada del problema real.

### Codec

Los dos sirven **H.264 1920x1080 en MP4 directo**, comprobado descargando un clip de cada uno.
No hay que transcodificar nada para Resolve.

Ninguna de las dos exige atribucion. Se registra igual: cuesta una linea y evita tener que
reconstruirlo si un dia hace falta.
