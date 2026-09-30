# Fase 4 - Llevarlo al timeline

Bajar el material no es entregarlo. Cuarenta archivos sueltos en una carpeta siguen siendo
cuarenta decisiones pendientes. Esta fase deja el B-roll dentro del editor, ordenado por
seccion del guion y con un marcador por recurso que dice que frase cubre y a quien se acredita.

Dos piezas, las dos generadas desde `manifest.json`:

| Que | Como entra en el editor |
|---|---|
| `por-seccion/` | arbol de enlaces duros. Boton derecho en Media Storage → *Add Folder and SubFolders into Media Pool (Create Bins)* |
| `B-ROLL-GUIA.fcpxml` | `File > Import > Timeline` |

**El orden importa.** Primero los bins, despues el timeline y **desmarcando**
*Automatically import source clips into media pool*. Al reves, Resolve duplica cada clip y los
bins por seccion se quedan sin usar.

---

## Comprobar la edicion de Resolve antes de nada

**[verificado 2026-09-30]** La API de scripting (`DaVinciResolveScript`) y el menu
`Workspace > Scripts` son **exclusivos de Studio**. En la edicion gratuita:

- `dvr.scriptapp('Resolve')` devuelve `None`, sin excepcion ni mensaje, con Resolve abierto
- `Preferences > System > General > External scripting using` **no existe**
- Los archivos de scripting estan en `C:\ProgramData\Blackmagic Design\...\Developer\Scripting\`
  **en las dos ediciones**, asi que verlos ahi no prueba nada

```powershell
Get-ItemProperty HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*,
  HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* |
  Where-Object { $_.DisplayName -like "*Resolve*" } | Select DisplayName, DisplayVersion
```

Si no dice "Studio", la via es FCPXML. Que es la que documenta este archivo, y funciona en las
dos ediciones, asi que ante la duda se usa esta.

---

## manifest.json

El mapa guion→recurso. Es lo unico que se edita a mano cuando cambia el material; el script no
se toca. Plantilla en `assets/manifest.plantilla.json`.

```json
{
  "proyecto": "Titulo de la pieza",
  "guion": {
    "fuente": "Notion, seccion \"Formato Blog/Review VIDEO\"",
    "url": "https://...",
    "palabras": 1115,
    "idioma": "español"
  },
  "secciones": [
    {
      "n": "01",
      "titulo": "Hook - el ano de Capcom",
      "beat": "HOOK",
      "palabras": 167,
      "recursos": [
        {
          "id": "B01",
          "frase": "la linea del guion que este recurso cubre",
          "credito": "Resident Evil Requiem (CAPCOM, via Steam)",
          "archivos": ["imagenes/capturas-juego/B01_re-requiem-01.jpg"]
        }
      ]
    }
  ]
}
```

- `palabras` por seccion es lo que manda el reparto de duracion. Sin ese campo todas las
  secciones pesan igual, que es casi siempre falso
- `frase` va en el nombre del marcador. Tiene que ser la linea **que se va a narrar**, no un
  resumen
- Un mismo recurso puede aparecer en **varias secciones**. La capacidad del archivo se descuenta
  globalmente y los fragmentos se reparten sin repetir plano
- Un `id` con varios `archivos` (cuatro capturas de un juego) es un solo recurso: un marcador,
  varios clips seguidos

### Contar las palabras

Del guion **hablado**, no del blog. Si la pagina tiene varias versiones, comprobar cual se lee
antes de mapear nada.

```bash
py -c "import re,io,sys; t=io.open(sys.argv[1],encoding='utf-8').read(); print(len(re.findall(r\"[\w'áéíóúñ]+\", t)))" seccion.txt
```

A 160 palabras por minuto sale la narracion. **La duracion del video terminado es mayor**:
pausas, enfasis y dejar sonar los clips. Un guion de 1115 palabras se narra en 7:00 y el video
acaba en 9-10 minutos. Si el objetivo del timeline y la narracion no cuadran, decirlo en vez de
estirar el material para disimularlo.

---

## Como se reparte la duracion

```
py scripts/preparar_resolve.py <carpeta B-roll>
```

1. **Cada seccion recibe una tajada del total proporcional a sus palabras.** No al numero de
   recursos que tenga: una seccion con muchas imagenes sueltas no vale mas que otra con dos
   clips si el guion pasa por encima de ella.
2. Dentro de la seccion, las imagenes duran `DUR_IMAGEN` y el video se lleva el resto.
3. El resto se reparte **a partes iguales entre las fuentes de video de la seccion**, sin
   pedirle a ninguna mas de lo que tiene. Lo que sobra de las cortas se redistribuye.
4. La tajada de cada video se **trocea en fragmentos de `DUR_SEGMENTO`** repartidos a lo largo
   del clip, saltandose `MARGEN` de cabeza y de cola.
5. Los clips se **entrelazan** para no dejar mas de `MAX_IMG_SEGUIDAS` imagenes juntas.

Constantes arriba del script:

| Constante | Por defecto | Que hace |
|---|---|---|
| `OBJETIVO_TOTAL_S` | 600 | duracion objetivo del timeline |
| `DUR_IMAGEN` | 4.0 | segundos por imagen |
| `DUR_SEGMENTO` | 8.0 | duracion objetivo de cada fragmento de video |
| `MARGEN` | 0.08 | cabeza y cola que se descartan de cada video |
| `MAX_IMG_SEGUIDAS` | 2 | imagenes fijas consecutivas permitidas |
| `PALABRAS_POR_MINUTO` | 160 | solo para el informe |

### Trocear, no estirar

Un trailer aguantando 70 segundos seguidos no es una guia de montaje: hay que scrubbearlo. Seis
fragmentos de 7 segundos repartidos por el mismo trailer se ojean. Por eso el reparto trocea en
vez de colocar un bloque largo.

### Entrelazar

Dos imagenes, un fragmento de video, dos imagenes. Si a una seccion no le salen suficientes
fragmentos para cortar las rachas, se trocea mas fino el video que mas margen tenga.

El caso extremo se da cuando una seccion tiene muchas imagenes y un solo video: nueve imagenes
necesitan cuatro separadores, asi que ese unico clip se parte en ocho trozos solo para poder
intercalarlo.

Esto **reordena dentro de la seccion, nunca entre secciones**. Los recursos de una seccion son
opciones para cubrirla, no una secuencia obligatoria.

### Tratamiento de las imagenes fijas

Una imagen a pantalla completa entre dos clips de video se nota como un bache, y los posters
verticales salen con barras negras a los lados. Por eso cada imagen se **hornea** con ffmpeg a
`compuestos/<nombre>_comp.mp4`: la propia imagen desenfocada, oscurecida y derivando despacio de
fondo, y la imagen nitida encima al `ESCALA_IMAGEN` del encuadre, centrada.

```
  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
  ░░░  ┌───────────────┐  ░░░     ░ = la misma imagen
  ░░░  │   la imagen   │  ░░░         blur + deriva lenta
  ░░░  │    al 80%     │  ░░░
  ░░░  └───────────────┘  ░░░     un solo clip, una sola pista
  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

**Se hornea en vez de montar dos pistas.** FCPXML permite hacerlo en vivo: el fondo en el spine
y la imagen como clip conectado en `lane="1"` con `<adjust-transform scale="0.8 0.8">`. Pero eso
depende de que el importador respete lanes y transforms, y ademas los clips conectados **no
admiten transiciones**: el fondo disolveria y la imagen daria un salto. Horneando, el timeline
se queda en una sola pista y todo son solapamientos normales.

Efecto lateral util: los compuestos sirven tal cual en el montaje final, no solo en la guia.

### La deriva del fondo

La ventana de recorte se desplaza sobre el fondo siguiendo un **vector unitario** que cambia
imagen a imagen: derecha, diagonal abajo-izquierda, arriba, diagonal abajo-derecha, izquierda,
diagonal arriba-derecha, abajo, diagonal arriba-izquierda. Con todas iguales el montaje entero
parece irse para el mismo lado, y se nota enseguida.

**La holgura va en pixeles, no en porcentaje.** Un 10% da 192 px en x pero solo 108 en y, asi
que una diagonal recorreria mas distancia en el mismo tiempo y se veria mas rapida.
`DERIVA_PX = 160` deja la misma holgura en los dos ejes, el modulo del vector es 1 en todas las
direcciones y el recorrido se centra en esa holgura. Cambia la direccion, nunca la velocidad.

El orden de la lista esta puesto para que dos imagenes seguidas no se muevan parecido: 135
grados entre cada direccion y la siguiente.

Escribir el diagonal como `0.707` deja el modulo en 159.94 en vez de 160. Da igual en pantalla,
pero obliga a explicar por que el test no da exacto: mejor `1/raiz(2)` completo.

#### Comprobarlo

Con blur fuerte no se distingue a ojo. Se hornea un degradado conocido y se mide:

| Que | Como |
|---|---|
| eje x | degradado horizontal, media de la franja izquierda al principio y al final |
| eje y | degradado vertical, media de la franja superior |
| diagonales | la misma medida: debe dar 1/raiz(2) del movimiento puro |

**[verificado 2026-09-30]** Horizontal ±40, diagonal ±27.5 en el mismo eje: razon 0.69.
Vertical ±23, diagonal ±16.4: razon 0.73.

Trampa de la medicion: con `FONDO_BRILLO` negativo el extremo oscuro del degradado **satura a
negro** y las dos lecturas dan 0.0, que parece "no se mueve". Usar un degradado que no toque los
extremos, de gris medio a gris claro.

Cuesta poco disco: 32 imagenes a 4,5 s salen en 8 MB con `libx264 -crf 20 -preset veryfast`.

**El cache va por firma de receta, no solo por fecha.** `compuestos/.receta` guarda los
parametros con los que se horneo. Mirar solo la fecha del archivo no basta: tocar
`ESCALA_IMAGEN` o `BLUR_SIGMA` no toca el jpg de origen, asi que los compuestos viejos pasarian
por buenos y el cambio no se veria por ningun lado.

| Constante | Por defecto | Que hace |
|---|---|---|
| `COMPONER_IMAGENES` | True | a False, las imagenes entran crudas |
| `ESCALA_IMAGEN` | 0.80 | tamano de la imagen dentro del encuadre |
| `BLUR_SIGMA` | 30 | desenfoque del fondo |
| `FONDO_BRILLO` / `FONDO_SATURACION` | -0.15 / 0.75 | el fondo va mas apagado que la imagen |
| `DERIVA` | 0.10 | cuanto se pasa el fondo del encuadre para poder moverse |

**Los compuestos tienen que estar en los bins.** El timeline los referencia a ellos, no a los
jpg, asi que `por-seccion/` los enlaza tambien. Si no, Resolve no resuelve el enlace al importar
con *Automatically import source clips* desmarcado.

### Transiciones

`<transition name="Cross Dissolve" offset="..." duration="..."/>`, hermano de los clips dentro
del spine.

**No anaden tiempo.** Se centran en el corte y se comen el handle de los dos clips que tocan,
asi que los offsets de los clips no cambian y la duracion de la secuencia sigue siendo la suma
de las duraciones. La transicion va en `corte - TRANSICION_S/2`.

De ahi sale el requisito que se olvida: **cada clip necesita handle**. Media transicion de
sobra antes de su punto de entrada y media despues de su salida.

| Tipo de clip | De donde sale el handle |
|---|---|
| Imagen compuesta | se renderiza `TRANSICION_S` mas larga de lo que dura en timeline |
| Fragmento de video | `MARGEN` ya deja sitio, pero hay que **forzarlo**: ningun fragmento puede empezar antes del handle ni acabar despues |

**El tipo se cicla corte a corte** con `TRANSICION_CICLO`, una lista de nombres. Con un solo
elemento salen todas iguales; con dos, alternan una y una.

**[verificado 2026-09-30] Resolve ignora el `name` del `<transition>`.** Sondeados
`Cross Dissolve`, `Slide, Left-Right`, `Slide, Right-Left`, `Push, Left-Right` y `Wipe` en un
mismo archivo: los cinco entran como **Cross Dissolve**. De lo que declara el XML solo respeta
la **duracion** y la **posicion respecto al corte**.

Asi que el tipo y la direccion **no se fijan desde el FCPXML**. Si hacen falta, se cambian en
Resolve despues de importar, seleccionando varias transiciones a la vez y tocando el Inspector
una sola vez por grupo.

`TRANSICION_CICLO` se queda por si una version futura si lo respeta. Para comprobarlo sin
generar noventa transiciones a ciegas:

```
py scripts/preparar_resolve.py <carpeta> --sondeo
```

Escribe `B-ROLL-SONDEO.fcpxml`, seis clips y un nombre distinto en cada corte. Se importa una
vez y el inspector dice cual reconocio.

Trampa al ciclar: **indexar por numero de corte**, no por la posicion en la lista de elementos
del spine, que crece con clips *y* transiciones. Con una alternancia de dos, ese error da un
patron irregular que no se ve mirando el timeline.

Si Resolve no traga las transiciones, `TRANSICIONES = False` y se regenera. El resto del
timeline no depende de ellas.

### Lo que el reparto no sabe

Reparte a partes iguales y **no conoce el peso editorial**. Una autocita de una frase recibe lo
mismo que el trailer principal si los dos estan en la misma seccion. Revisar el informe y
recortar a mano, o separar esa autocita a su propia seccion.

### El informe dice donde falta material

```
  seccion                    palab   guion   broll  video%  img/vid
  HOOK                         167    1:02    1:29     73%  6/5 en 10 frag
  CONTEXT                      180    1:07    1:36     63%  9/1 en 8 frag
  PIVOT                        270    1:41    2:25     78%  8/1 en 14 frag
```

Una seccion con mucho peso de guion y un solo video es un aviso: ahi falta metraje, y el
arreglo es volver a la fase 1 a buscarlo, no estirar lo que hay.

**El recuento de palabras destapa huecos que la lista de candidatos esconde.** Una seccion
puede tener ocho recursos y seguir estando coja si siete son imagenes fijas y se lleva el 23%
del guion.

---

## Validar antes de abrir Resolve

```
py scripts/validar_fcpxml.py B-ROLL-GUIA.fcpxml
```

**Que el XML parsee no dice nada.** Resolve se cierra sin mensaje ante valores que son legales
segun la especificacion. Validar la forma tampoco basta: `audioChannels="48000"` es un entero
perfectamente valido en un sitio donde toca un entero. Lo que hay que comprobar son **rangos
plausibles**.

| Comprobacion | Por que existe |
|---|---|
| tasas dentro de la lista estandar | `frameDuration="317/19001s"` tumba el importador |
| ningun `format` sin `frameDuration` | los stills con `FFVideoFormatRateUndefined` lo tumban |
| ningun asset con `duration="0s"` | idem, va con lo anterior |
| canales de audio 1-32, tasa 8k-192k | 48000 canales lo tumban |
| ninguna dimension impar | un `format` de 1919 px de ancho es una rareza que no compensa |
| `ref` y `format` resueltos | referencia rota |
| offsets contiguos, sin huecos ni solapes | |
| duracion de la secuencia = suma de clips | |
| ningun clip que se salga de su asset | |
| ningun marcador fuera del rango de su clip | |
| todos los `src` existen en disco | |
| racha de imagenes ≤ `MAX_IMG_SEGUIDAS` | la regla de ritmo, comprobada sobre el XML final |
| cada transicion cae centrada en un corte | una transicion suelta no la monta |
| los dos clips de cada transicion tienen handle | sin handle no hay nada que disolver |

Las comprobaciones de handle solo saltan si de verdad hay algo que comprobar. Probarlas a mano
al tocarlas: quitarle el `start` a un clip intermedio debe dar *sin handle de entrada*, y
estirar la duracion de un clip hasta el final de su asset debe dar *sin handle de salida*. Un
chequeo que nunca falla no esta comprobando nada.

Sale con codigo 1 si encuentra algo.

---

## Trampas de FCPXML

### Los marcadores solo tienen `value`

No hay campo de nota. Si el credito y la frase no van en el nombre del marcador, no llegan a
Resolve. Formato que funciona:

```
S05 B28 | dudo que sea el outbreak del 98 | Frame del trailer oficial (Sony Pictures)
```

### El `src` necesita los dos puntos sin escapar

```python
"file:///" + quote(ruta.replace("\\", "/"), safe="/:")
```

Con el `safe` por defecto sale `C%3A` y Resolve no encuentra el archivo.

### Un `<format>` por combinacion real

Cada asset de video necesita su `frameDuration`. Con material mezclado salen trece formats para
cuarenta y cuatro assets, y es correcto. Las imagenes heredan la tasa del timeline.

### Ajustar la tasa antes de escribirla

`ffprobe` devuelve el `r_frame_rate` literal. Hay archivos que dan `19001/317` (= 59.9401).
Ajustar a la mas cercana de: 24000/1001, 24, 25, 30000/1001, 30, 50, 60000/1001, 60.

### Sondear el audio por archivo

Un clip sin pista de audio con `hasAudio="1"` rompe el import. No suponerlo: mirarlo.

### ffprobe ignora el orden en que pides los campos

**[verificado 2026-09-30]** Esta es la que mas cara sale, porque falla en silencio:

```bash
ffprobe -show_entries stream=channels,sample_rate -of csv=p=0 archivo.mp4
# -> 48000,2     sample_rate primero, luego channels
```

ffprobe imprime en **su** orden interno. Con `csv=p=0` no vienen las claves, asi que sale un
numero donde esperabas otro y nada avisa. En la sonda de video cuela de milagro porque
`width,height,r_frame_rate,nb_frames` coincide con el orden interno.

**Usar siempre `-show_streams -of json` y leer por clave.** Nunca `csv=p=0` para mas de un
campo.

---

## Enlaces duros, no copias

`por-seccion/` reordena el material por seccion **sin duplicarlo**: son hardlinks, asi que el
arbol suma 587 MB logicos y el proyecto sigue pesando lo mismo. Mismo volumen NTFS. Si
`os.link` falla, el script cae a copia y lo dice en el informe.

El arbol original por tipo (`imagenes/prensa`, `videos/trailers`) **no se toca**: es el que
describe `CREDITOS.txt`. Romperlo invalida los creditos.

---

## Otros editores

`.fcpxml` lo importan Premiere y Final Cut. No esta probado fuera de Resolve. Lo que casi
seguro cambia es el mapeo de marcadores y el trato de los stills; el resto del formato es
estandar.
