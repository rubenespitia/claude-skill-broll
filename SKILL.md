---
name: broll
description: Recolecta B-roll para un guion de video, sea de videojuegos o de cine - imagenes de prensa con autor, precios de tienda o taquilla, trailers, posters, gameplay propio del canal, gameplay free use y stock gratuito. Organiza todo en carpetas y genera un TXT de creditos con autores, fechas y licencias. Usar cuando el usuario pida "broll", "b-roll", "material de apoyo", "recursos visuales", "imagenes y videos para el guion", o cuando haya un guion de review que necesite planos de apoyo.
---

# B-roll para un guion

El guion manda. Cada recurso existe porque una frase concreta del guion lo pide, no porque el
juego sea popular. Si una seccion no necesita apoyo visual, no se le busca nada.

## Ciclo en tres fases

**Fase 1 - Leer y proponer.** Leer el guion, partirlo en secciones y listar que pide cada una.
Buscar candidatos y escribir `candidatos.md` en la carpeta de la pieza. Nada se descarga aun.

**Fase 2 - Aprobar.** El usuario marca `[x]` los que quiere. Esperar. No descargar sin marcas.

**Fase 3 - Descargar y acreditar.** Bajar solo lo marcado, nombrar por ID y escribir
`CREDITOS.txt`. Reportar lo que fallo, no rellenarlo en silencio con otra cosa.

## Carpeta destino

Dentro de la carpeta de la pieza, que sigue la convencion del vault `content-creation`:

```
<CARPETA_VIDEO>\VID_YYYY_MM_DD-titulo\B-roll\
  candidatos.md
  CREDITOS.txt
  imagenes\
    prensa\
    precios\
  videos\
    trailers\
    gameplay-propio\
    gameplay-freeuse\
    stock\
```

`<CARPETA_VIDEO>` es la raiz donde vive el trabajo de video. En la maquina de origen es
`C:\Users\<usuario>\Videos\1.-YOUTUBE`. Si no esta clara, preguntar una vez y no volver a
preguntarla.

Si la carpeta de la pieza no existe, preguntar la fecha y el titulo antes de crearla. Nunca
inventar el nombre: esa carpeta es la llave que une la nota de Obsidian, Notion y el disco.

## El ID es la llave

Cada recurso recibe un ID `B01`, `B02`, ... unico en toda la pieza, sin importar el tipo. Ese ID
aparece en tres sitios y debe coincidir: la fila de `candidatos.md`, el nombre del archivo y el
bloque de `CREDITOS.txt`.

```
B07_ign-analisis-silksong.png
B12_trailer-lanzamiento.mp4
```

Sin el ID no hay forma de saber a quien acreditar un plano tres semanas despues.

## Dos dominios

El guion puede ser de **videojuego** o de **cine**, y las fuentes no son las mismas. Mirar de
que va antes de empezar a buscar.

| | Videojuego | Cine |
|---|---|---|
| Arte y capturas | Steam `appdetails` | TMDB (poster, backdrop, stills) |
| Dato duro | Precio por region | Taquilla, solo si el guion habla de dinero |
| Trailer | Steam `hls_h264`, o canal oficial | Canal oficial del estudio |
| Material propio | Gameplay del canal | Normalmente no hay |
| Metraje de la obra | Gameplay propio, todo el que quieras | **Solo trailer, still y poster** |

Esa ultima fila es la diferencia grande. En un juego grabas lo que necesites. En cine no existe
fuente legitima de clips de la pelicula: lo que se puede mostrar sale del trailer, de los stills
oficiales y del poster. Decirlo una vez al proponer candidatos y seguir.

Subcarpetas: en cine, `imagenes/posters/` sustituye a `imagenes/precios/`, y
`videos/gameplay-propio/` casi siempre se queda vacia.

## Reglas por tipo

| Tipo | Regla que no se salta |
|---|---|
| Prensa | Autor y medio **siempre**. Si no se puede extraer el autor, se descarta el recurso |
| Precios | Anotar region y fecha de consulta. Un precio sin region es un dato falso |
| Trailers | Completo, nunca precortado. El corte es decision de edicion |
| Gameplay propio | Master local primero. YouTube solo si el archivo no esta en disco |
| Free use | Autor, canal y URL. Verificar el campo `license` del info json, no fiarse del titulo |
| Stock | Registrar autor igual aunque la licencia no lo exija |

## Formato que traga DaVinci Resolve free

Resolve gratuito en Windows no lee bien VP9, AV1 ni WebP. Forzar siempre H.264 al bajar y
convertir lo que llegue en otro codec. Los comandos exactos estan en `reference/descarga.md`.

Un archivo que Resolve no abre es un archivo que no existe.

## Setup, una sola vez

```bash
winget install yt-dlp.yt-dlp
```

```bash
npx --yes playwright@latest install chromium
```

Toda llamada de yt-dlp a YouTube lleva `--js-runtimes node`. Sin eso faltan formatos y no
aparece el AVC de 1080p. Detalle en `reference/descarga.md`.

Las API keys de Pexels, Pixabay y TMDB van en `~/.claude/.env.broll`, **fuera** de esta
carpeta, porque la carpeta de la skill es un repo publico:

```
PEXELS_API_KEY=...
PIXABAY_API_KEY=...
```

Ambas son gratuitas: pexels.com/api y pixabay.com/api/docs.

## Referencias

- `reference/fuentes.md` - de donde sale cada tipo, endpoints verificados y sus trampas
- `reference/descarga.md` - comandos exactos de yt-dlp, ffmpeg y capturas de pagina
- `reference/creditos.md` - formato del TXT y que exige cada licencia
- `assets/candidatos.plantilla.md` - tabla de la fase 1
- `assets/CREDITOS.plantilla.txt` - esqueleto del TXT final
- `scripts/ldjson.js` - saca titular, autor y fecha de un articulo de prensa
- `scripts/capturar.js` - captura una pagina a 1920x1080 descartando el banner de cookies
