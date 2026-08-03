// Captura una pagina a 1920x1080 descartando el banner de cookies.
// Uso: node capturar.js <url> <salida.png> [--full]
//
// Solo pulsa opciones de RECHAZO o de CERRAR. Nunca acepta terminos ni cookies:
// aceptar en nombre de otro no es decision de un script.
//
// Requiere el paquete playwright resoluble desde este directorio:
//   npm install playwright

const [, , url, salida, ...resto] = process.argv;
if (!url || !salida) {
  console.error('uso: node capturar.js <url> <salida.png> [--full]');
  process.exit(1);
}
const paginaCompleta = resto.includes('--full');

const { chromium } = require('playwright');

// Rechazar primero, cerrar despues. Nada de "Accept".
const SELECTORES = [
  '#onetrust-reject-all-handler',
  'button#truste-consent-required',
  '[aria-label="Reject all"]',
  '[aria-label="Rechazar todo"]',
  'button:has-text("Reject All")',
  'button:has-text("Reject all")',
  'button:has-text("Rechazar todo")',
  'button:has-text("Solo las necesarias")',
  'button:has-text("Continue without accepting")',
  '.onetrust-close-btn-handler',
  '#onetrust-banner-sdk button[aria-label="Close"]',
  '[aria-label="Close"]',
  '[aria-label="Cerrar"]',
];

(async () => {
  const navegador = await chromium.launch();
  const contexto = await navegador.newContext({
    viewport: { width: 1920, height: 1080 },
    locale: 'es-MX',
  });
  const pagina = await contexto.newPage();

  try {
    await pagina.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await pagina.waitForTimeout(3500);

    let descartado = null;
    for (const sel of SELECTORES) {
      const el = pagina.locator(sel).first();
      try {
        if (await el.isVisible({ timeout: 400 })) {
          await el.click({ timeout: 2000 });
          descartado = sel;
          await pagina.waitForTimeout(1200);
          break;
        }
      } catch { /* siguiente selector */ }
    }

    // El overlay a veces sobrevive al boton. Segunda pasada por si acaso.
    await pagina.waitForTimeout(800);
    await pagina.screenshot({ path: salida, fullPage: paginaCompleta });

    console.log(JSON.stringify({
      salida,
      banner: descartado || 'no habia, o ninguno era rechazable',
      titulo: (await pagina.title()).slice(0, 80),
    }));
  } catch (e) {
    console.error('fallo:', e.message);
    process.exitCode = 2;
  } finally {
    await navegador.close();
  }
})();
