# broll

Skill de Claude Code que recolecta el material de apoyo de un video partiendo del guion.

Lee el guion, propone candidatos, espera aprobacion y solo entonces descarga. Deja las carpetas
ordenadas y un `CREDITOS.txt` con autores, fechas y licencias para poder acreditar en la
descripcion sin reconstruir nada a mano.

## Que recolecta

| Tipo | De donde |
|---|---|
| Imagenes de prensa | Captura del articulo, con autor y fecha extraidos del JSON-LD |
| Precios de tiendas | API de Steam y de Nintendo eShop, captura para PS y Xbox |
| Trailers | HLS H.264 de Steam, o el canal oficial en YouTube |
| Gameplay propio | Master local del disco, YouTube solo como fallback |
| Gameplay free use | YouTube con licencia CC verificada en el info json |
| Stock | Pexels y Pixabay |

## Instalacion

Copiar la carpeta a `~/.claude/skills/broll/`. Requiere:

```bash
winget install yt-dlp.yt-dlp
```

```bash
npx --yes playwright@latest install chromium
```

ffmpeg, jq y node deben estar en el PATH. Node no es opcional: yt-dlp lo necesita como runtime
de JavaScript para sacar todos los formatos de YouTube.

Keys de Pexels y Pixabay, gratuitas, en `~/.claude/.env.broll` (fuera de esta carpeta, que es
un repo publico):

```
PEXELS_API_KEY=...
PIXABAY_API_KEY=...
```

## Uso

```
/broll <ruta del guion>
```

O en lenguaje normal: "saca el broll para el guion de la review de X".

Devuelve `candidatos.md` para marcar. Al confirmar, descarga y escribe `CREDITOS.txt`.

## Estructura

```
SKILL.md                         ciclo, reglas y estructura de carpetas
reference/fuentes.md             endpoints verificados y sus trampas
reference/descarga.md            comandos de yt-dlp, ffmpeg y capturas
reference/creditos.md            formato del TXT y reglas de atribucion
assets/candidatos.plantilla.md   tabla de aprobacion
assets/CREDITOS.plantilla.txt    esqueleto del TXT final
scripts/ldjson.js                autor y fecha de un articulo de prensa
scripts/capturar.js              captura 1920x1080 descartando el banner de cookies
```

## Decisiones

- **Aprobar antes de bajar.** Un trailer son cientos de MB y la mitad de los candidatos no
  sobreviven a mirarlos.
- **H.264 siempre.** DaVinci Resolve free en Windows no decodifica AV1 ni VP9. Un clip que no
  abre es un clip que no existe.
- **Prensa sin autor se descarta.** Acreditar al medio en lugar de a quien firmo no es acreditar.
- **El ID es la llave.** `B07` aparece en el nombre del archivo, en los candidatos y en los
  creditos. Sin eso no se sabe a quien acreditar un plano semanas despues.
