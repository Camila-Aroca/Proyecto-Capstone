/**
 * SAAD-CP-079: exploración guiada por riesgo territorial. Recorre comunas sin datos, con cero observado y
 * con baja confianza, deja una bitácora con pasos reproducibles y los hallazgos, y un entradas.json para
 * `qa_campana_200.py --modo manual`.
 *
 * Uso: node scripts/qa_ui_exploracion.mjs --entorno local --url http://127.0.0.1:8080
 *      node scripts/qa_ui_exploracion.mjs --entorno aws   --url "$SAAD_URL"
 */
import { abrirNavegador, espera } from "./qa_ui_cdp.mjs";
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

const args = process.argv.slice(2);
const entorno = args[args.indexOf("--entorno") + 1] ?? "local";
const BASE = (args[args.indexOf("--url") + 1] ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const OUT = join(tmpdir(), `saad-explor-${entorno}`);
mkdirSync(OUT, { recursive: true });

const api = async (ruta) => (await fetch(`${BASE}/api/v1${ruta}`)).json();
const inicio = new Date();
const territorios = (await api("/territorios")).filter((t) => t.nivel === "comuna");

// Selección por riesgo: ausencia de dato, ceros observados y recuentos bajos.
const sin = territorios.filter((t) => !t.tiene_pronostico);
const conSerie = await Promise.all(territorios.filter((t) => t.tiene_pronostico)
  .map(async (t) => ({ ...t, serie: await api(`/series/${t.series_id}?semanas=104`) })));
const media26 = (s) => s.historico.slice(-26).reduce((a, h) => a + h.atenciones, 0) / 26;
const VENTANA_TABLA = 12; // la tabla de datos muestra las últimas 12 semanas observadas y 8 de pronóstico
const ceros = (s) => s.historico.slice(-VENTANA_TABLA).filter((h) => h.atenciones === 0).length;
const grupoCero = conSerie.filter((c) => ceros(c.serie) > 0).sort((a, b) => ceros(b.serie) - ceros(a.serie)).slice(0, 3);
const grupoBaja = conSerie.filter((c) => media26(c.serie) < 20).sort((a, b) => media26(a.serie) - media26(b.serie)).slice(0, 3);

const p = await abrirNavegador({ ancho: 1440, alto: 900 });
const hallazgos = [];
const bitacora = [];
const registro = (estado, c, pasos, obs, ok) => bitacora.push({ estado, comuna: `${c.nombre} (${c.series_id})`, pasos, obs, ok });

async function abrir(cod) {
  await p.ir("about:blank", 300);
  await p.cdp("Network.setCacheDisabled", { cacheDisabled: true });
  await p.ir(`${BASE}/#/tablero?territorio=${cod}`, 7000);
  await espera(3000);
}
const abrirDetalle = (re) => p.eval(`[...document.querySelectorAll('summary')].find(s=>/${re}/.test(s.textContent))?.click()`);
const filasTabla = () => p.eval(`JSON.stringify([...(document.querySelectorAll('table')[0]?.querySelectorAll('tbody tr')??[])].map(r=>[...r.children].map(c=>c.textContent.trim())))`).then(JSON.parse);
const pasosBase = (c) => [`Abrir \`#/tablero?territorio=${c.series_id}\` con la caché desactivada`, "Esperar a que cargue el panel de la comuna"];

// A. Sin datos
for (const c of sin) {
  await abrir(c.series_id);
  const texto = await p.eval("document.body.innerText");
  const motivo = texto.includes(c.motivo_sin_pronostico);
  const aviso = /Pronóstico no disponible/.test(texto);
  const cero = /se esperan 0 atenciones/.test(texto);
  const confuso = /No se pudo consultar la API|Verifique que el backend/.test(texto);
  await p.captura(join(OUT, `A-${c.series_id}.png`));
  registro("Sin datos", c, [...pasosBase(c), "Leer el aviso bajo el título", `Comparar con el motivo de GET /territorios (${c.motivo_sin_pronostico})`],
    `Aviso «Pronóstico no disponible»: ${aviso ? "sí" : "no"} · motivo visible: ${motivo ? "sí" : "no"} · dibuja pronóstico cero: ${cero ? "SÍ" : "no"}`, aviso && motivo && !cero);
  if (confuso) hallazgos.push({ id: "H-1", comuna: `${c.nombre} (${c.series_id})`, estado: "Sin datos",
    pasos: [...pasosBase(c), "Leer el texto bajo «Pronóstico no disponible»"],
    obs: "Junto al motivo se muestra «No se pudo consultar la API… Verifique que el backend esté corriendo (uvicorn src.api.main:app)…», un mensaje técnico de falla del sistema para una ausencia de dato esperada.",
    impacto: "Un usuario no técnico puede creer que el sistema está caído en lugar de entender que la comuna no se modela. No lleva a una conclusión clínica ni cambia ninguna cifra." });
}

// B. Cero observado
for (const c of grupoCero) {
  await abrir(c.series_id);
  await abrirDetalle("Ver los datos en tabla");
  await espera(600);
  const filas = await filasTabla();
  const nCeros = filas.filter((f) => f[2] === "0" && /Observado/.test(f[4] ?? "")).length;
  const sinValor = filas.filter((f) => /^[—–-]?$/.test(f[2] ?? "")).length;
  await p.captura(join(OUT, `B-${c.series_id}.png`));
  registro("Cero observado", c, [...pasosBase(c), "Abrir «Ver los datos en tabla» (últimas 12 semanas observadas y 8 de pronóstico)", "Buscar filas con Atenciones = 0 y Tipo = Observado"],
    `API: ${ceros(c.serie)} de las últimas ${VENTANA_TABLA} semanas observadas con 0 atenciones · tabla (${filas.length} filas): ${nCeros} filas «0 · Observado», ${sinValor} filas sin valor`, nCeros === ceros(c.serie) && nCeros > 0);
}

// C. Baja confianza
for (const c of grupoBaja) {
  await abrir(c.series_id);
  const texto = await p.eval("document.body.innerText");
  const intervalo = /se esperan [\d.,]+ atenciones, entre [\d.,]+ y [\d.,]+ con un intervalo de 80%/.test(texto);
  const confiabilidad = /Confiabilidad del intervalo/.test(texto) && /cubrió/.test(texto);
  await abrirDetalle("Cómo leer estas cifras");
  await espera(500);
  const orientativo = /Interpretar los límites como orientativos/.test(await p.eval("document.body.innerText"));
  await p.captura(join(OUT, `C-${c.series_id}.png`));
  registro("Baja confianza", c, [...pasosBase(c), "Leer la frase de pronóstico con su intervalo", "Leer «Confiabilidad del intervalo»", "Abrir «Cómo leer estas cifras»"],
    `Promedio ${media26(c.serie).toFixed(1)} atenciones/semana · intervalo declarado: ${intervalo ? "sí" : "no"} · confiabilidad observada fuera de muestra visible: ${confiabilidad ? "sí" : "no"} · advertencia «orientativos»: ${orientativo ? "sí" : "no"}`,
    intervalo && confiabilidad && orientativo);
}
await p.cerrar();

const fin = new Date();
const minutos = ((fin - inicio) / 60000).toFixed(1);
const ok = bitacora.every((b) => b.ok);
const estados = ["Sin datos", "Cero observado", "Baja confianza"];
const distingue = estados.every((e) => bitacora.some((b) => b.estado === e) && bitacora.filter((b) => b.estado === e).every((b) => b.ok));

const md = [
  `# Bitácora de exploración SAAD-CP-079 (${entorno.toUpperCase()})`,
  "",
  `Inicio ${inicio.toISOString().slice(0, 19)}Z · fin ${fin.toISOString().slice(0, 19)}Z · duración real ${minutos} min. ` +
  "La exploración se hizo con un barrido automatizado con Chrome (CDP) de las comunas de mayor riesgo de mala interpretación; **no es la sesión humana de 30 minutos** que describe el caso.",
  "",
  "## Selección",
  `- Sin datos: ${sin.map((c) => `${c.nombre} (${c.series_id})`).join(", ")}.`,
  `- Cero observado (más semanas en 0 entre las últimas 12 observadas): ${grupoCero.map((c) => `${c.nombre} (${ceros(c.serie)})`).join(", ")}.`,
  `- Baja confianza (menor promedio de las últimas 26 semanas): ${grupoBaja.map((c) => `${c.nombre} (${media26(c.serie).toFixed(1)}/sem)`).join(", ")}.`,
  "",
  "## Los tres estados",
  "| Estado | Comuna | Resultado | Cumple |", "|---|---|---|---|",
  ...bitacora.map((b) => `| ${b.estado} | ${b.comuna} | ${b.obs} | ${b.ok ? "sí" : "NO"} |`),
  "",
  "## Pasos reproducibles",
  ...bitacora.map((b) => `**${b.estado} · ${b.comuna}**\n${b.pasos.map((x, i) => `${i + 1}. ${x}`).join("\n")}\n`),
  "## Hallazgos",
  ...(hallazgos.length ? hallazgos.map((h) => `### ${h.id} · ${h.estado} · ${h.comuna}\n**Pasos:**\n${h.pasos.map((x, i) => `${i + 1}. ${x}`).join("\n")}\n\n**Observado:** ${h.obs}\n\n**Impacto:** ${h.impacto}\n`) : ["Ninguno."]),
  "Ninguna observación concluye sobre atención clínica individual.",
].join("\n");
writeFileSync(join(OUT, "SAAD-CP-079-bitacora.md"), md, "utf8");

const resultado = `${distingue ? "La interfaz distingue los tres estados" : "La interfaz NO distingue correctamente los tres estados"}: ` +
  `sin datos (${sin.length} comunas con aviso y motivo, sin pronóstico cero), cero observado (${grupoCero.length} comunas con las semanas en 0 visibles como «0 · Observado») y ` +
  `baja confianza (${grupoBaja.length} comunas con intervalo, confiabilidad observada y advertencia). ${hallazgos.length} hallazgo(s) de usabilidad en la bitácora. ` +
  `Duración real ${minutos} min con barrido automatizado, no sesión humana de 30 min.`;
const t = fin.toISOString();
writeFileSync(join(OUT, "entradas.json"), JSON.stringify([{
  id: "SAAD-CP-079", estado: distingue ? "APROBADO" : "FALLIDO", resultado_real: resultado,
  observaciones: hallazgos.map((h) => `${h.id}: ${h.obs}`).join(" "), snapshot: "", defecto: "",
  anexos: ["SAAD-CP-079-bitacora.md", `A-${sin[0]?.series_id}.png`, `B-${grupoCero[0]?.series_id}.png`, `C-${grupoBaja[0]?.series_id}.png`],
  inicio: inicio.toISOString(), fin: t }], null, 1), "utf8");
console.log(resultado);
console.log(`→ ${OUT}`);
