// Extrae titular, autor y fecha del JSON-LD de un articulo de prensa.
// Uso: node ldjson.js <url>
// Salida: una linea JSON por bloque util, o nada si el articulo no lleva JSON-LD.

const url = process.argv[2];
if (!url) {
  console.error('uso: node ldjson.js <url>');
  process.exit(1);
}

const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36';

const ENTIDADES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', ndash: '–', mdash: '—', hellip: '…', rsquo: '’', lsquo: '‘', ldquo: '“', rdquo: '”' };

const limpiar = (s) => typeof s !== 'string' ? s : s
  .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(n))
  .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCharCode(parseInt(n, 16)))
  .replace(/&([a-z]+);/gi, (m, n) => ENTIDADES[n.toLowerCase()] ?? m)
  .trim();

// Los medios que usan @graph referencian al autor por @id en vez de incrustarlo.
// Sin resolver la referencia, el autor sale como [object Object].
function resolver(valor, indice, visto = 0) {
  if (valor == null || visto > 3) return undefined;
  if (typeof valor === 'string') return limpiar(valor);
  if (Array.isArray(valor)) {
    const nombres = valor.map(v => resolver(v, indice, visto + 1)).filter(Boolean);
    return nombres.length ? nombres.join(', ') : undefined;
  }
  if (typeof valor === 'object') {
    if (valor.name) return limpiar(typeof valor.name === 'string' ? valor.name : resolver(valor.name, indice, visto + 1));
    if (valor['@id'] && indice.has(valor['@id'])) return resolver(indice.get(valor['@id']), indice, visto + 1);
    if (valor['@id']) {
      // Ultimo recurso: varios CMS meten el slug del autor en la propia URL del @id
      const m = String(valor['@id']).match(/\/author\/([^/#?]+)/);
      if (m) return m[1].replace(/[-_]+/g, ' ');
    }
  }
  return undefined;
}

fetch(url, { headers: { 'User-Agent': UA }, redirect: 'follow' })
  .then(r => r.text())
  .then(html => {
    // Primera pasada: indexar TODOS los nodos por @id, de todos los bloques
    const bloques = [];
    for (const m of html.matchAll(/<script[^>]*application\/ld\+json[^>]*>([\s\S]*?)<\/script>/g)) {
      try { bloques.push(JSON.parse(m[1])); } catch { /* bloque roto, seguir */ }
    }
    const indice = new Map();
    const nodos = [];
    const aplanar = (j) => {
      const arr = Array.isArray(j) ? j : (j['@graph'] || [j]);
      for (const n of arr) {
        if (!n || typeof n !== 'object') continue;
        nodos.push(n);
        if (n['@id']) indice.set(n['@id'], n);
      }
    };
    bloques.forEach(aplanar);

    // Segunda pasada: emitir solo los nodos con contenido util
    const vistos = new Set();
    let encontrado = false;
    for (const n of nodos) {
      if (!n.headline && !n.author) continue;
      const out = {
        tipo: n['@type'],
        titular: limpiar(n.headline || n.name),
        autor: resolver(n.author, indice),
        fecha: n.datePublished || n.date_published || n.dateModified,
        medio: resolver(n.publisher, indice),
      };
      if (!out.autor && !out.fecha) continue;
      const clave = `${out.autor}|${out.fecha}`;
      if (vistos.has(clave)) continue;
      vistos.add(clave);
      console.log(JSON.stringify(out));
      encontrado = true;
    }

    if (!encontrado) {
      const meta = (prop) => {
        const re = new RegExp(`<meta[^>]+(?:property|name)=["']${prop}["'][^>]+content=["']([^"']+)`, 'i');
        const alt = new RegExp(`<meta[^>]+content=["']([^"']+)["'][^>]+(?:property|name)=["']${prop}["']`, 'i');
        return limpiar((html.match(re) || html.match(alt) || [])[1]);
      };
      const out = {
        tipo: 'meta',
        titular: meta('og:title'),
        autor: meta('article:author') || meta('author'),
        fecha: meta('article:published_time') || meta('date'),
        medio: meta('og:site_name'),
      };
      if (out.autor || out.fecha) console.log(JSON.stringify(out));
      else console.error('sin autor ni fecha: abrir en el browser y leer el DOM');
    }
  })
  .catch(e => { console.error('fallo la descarga:', e.message); process.exit(2); });
