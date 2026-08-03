# CREDITOS.txt

Un TXT plano por pieza, en la raiz de `B-roll\`. Dos partes: el bloque listo para pegar en la
descripcion de YouTube, y el detalle por archivo para cuando haya que rastrear un plano.

## Estructura

```
BROLL - <titulo de la pieza>
Recopilado: YYYY-MM-DD
Guion: <ruta del guion>

================================================================
BLOQUE PARA LA DESCRIPCION DE YOUTUBE
================================================================

<solo las lineas de los recursos que exigen atribucion, ya redactadas>

================================================================
DETALLE POR ARCHIVO
================================================================

[B01] imagenes/prensa/B01_ign-analisis.png
  Tipo        : Imagen - prensa
  Fuente      : IGN España
  Autor       : <firma del articulo>
  Publicado   : 2025-09-04
  URL         : https://...
  Licencia    : Cita con atribucion (captura de articulo)
  Atribucion  : obligatoria
  Credito     : Analisis de <autor>, IGN España (2025-09-04)
  Descargado  : 2026-08-03
  Uso         : seccion 2 del guion, frase "la critica coincidio en..."
```

Campos siempre presentes, aunque el valor sea `desconocido`. Un campo ausente parece un
descuido; un `desconocido` explicito es una decision.

## Que exige cada licencia

| Origen | Atribucion | Que va en el credito |
|---|---|---|
| Articulo de prensa | Obligatoria | Autor + medio + fecha. El medio solo no basta |
| Captura oficial de Steam | Recomendada | Nombre del juego + desarrollador/publisher |
| Trailer oficial | Recomendada | Publisher. Es material de prensa, se usa para cubrir |
| Precio de tienda | Obligatoria de facto | Tienda + region + fecha de consulta |
| Gameplay propio | Ninguna | Se registra igual, con VOD y timestamp de origen |
| Gameplay free use / CC | Obligatoria | Canal + titulo + URL + licencia exacta |
| Poster o still de TMDB | Obligatoria | Linea fija de TMDB, ver abajo |
| Pexels / Pixabay | No exigida | Autor + plataforma. Se pone igual |

## Linea fija de TMDB

Si se uso **un solo** recurso de TMDB, esta linea va en el bloque de descripcion, literal y sin
reescribir. Es condicion de la key gratuita:

```
This product uses the TMDB API but is not endorsed or certified by TMDB.
```

El bloque de descripcion recoge las filas marcadas **obligatoria**. Las demas se quedan en el
detalle: llenar la descripcion de creditos que nadie exige entierra los que si importan.

## Precios

Un precio es el unico dato del TXT que envejece mal. Formato fijo:

```
  Precio      : COL$ 47.500 (COP) - sin descuento
  Region      : Colombia (cc=co)
  Consultado  : 2026-08-03
```

Si el video se publica semanas despues de la captura, avisar al usuario de que reconsulte antes
de subir. Un precio desactualizado en pantalla se lee como error del canal.

## Gameplay propio

Aunque no lleve credito externo, se registra el origen para poder volver al material bruto:

```
  Origen      : VID_2026_03_11 / grabacion.mp4
  Tramo       : 00:12:30 - 00:13:10
  VOD publico : https://youtube.com/watch?v=...
```

## Reglas

1. Un bloque por archivo. Un archivo sin bloque no se entrega.
2. El ID del bloque coincide con el nombre del archivo y con la fila de `candidatos.md`.
3. Autor desconocido en un recurso de prensa: el recurso no se descarga.
4. Las fechas en ISO `YYYY-MM-DD`, tanto la de publicacion como la de descarga.
5. Nada de reescribir el TXT desde cero al añadir recursos: se añaden bloques y se conservan
   los IDs ya asignados.
