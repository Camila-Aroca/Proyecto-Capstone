// Cliente mínimo de Chrome DevTools Protocol para las pruebas de interfaz del catálogo SAAD-CP.
// Sin dependencias: usa el WebSocket nativo de Node 22 y Chrome/Chromium en modo headless.
import { spawn } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

export const espera = (ms) => new Promise((r) => setTimeout(r, ms));

export async function abrirNavegador({ ancho = 1440, alto = 900, escala = 1, puerto } = {}) {
  puerto ??= 9300 + Math.floor(Math.random() * 500);
  const perfil = mkdtempSync(join(tmpdir(), "saad-cdp-"));
  const binario = process.env.CHROME ?? "google-chrome";
  const proceso = spawn(binario, [
    "--headless=new", `--remote-debugging-port=${puerto}`, `--user-data-dir=${perfil}`, "--no-first-run",
    "--disable-gpu", "--hide-scrollbars", `--window-size=${ancho},${alto}`,
    // Sin esto headless informa hover:none y los tooltips con group-hover no se abren.
    "--blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4",
    "about:blank",
  ], { stdio: "ignore" });
  let destino;
  for (let i = 0; i < 75 && !destino; i++) {
    try {
      const lista = await (await fetch(`http://127.0.0.1:${puerto}/json/list`)).json();
      destino = lista.find((x) => x.type === "page")?.webSocketDebuggerUrl;
    } catch { /* aún no escucha */ }
    if (!destino) await espera(200);
  }
  if (!destino) throw new Error("Chrome no abrió el puerto de depuración");
  const pagina = await conectar(destino);
  pagina.proceso = proceso;
  pagina.version = (await (await fetch(`http://127.0.0.1:${puerto}/json/version`)).json()).Browser;
  await pagina.viewport(ancho, alto, escala);
  return pagina;
}

async function conectar(url) {
  const ws = new WebSocket(url);
  await new Promise((r, e) => { ws.onopen = r; ws.onerror = e; });
  let id = 0;
  const pendientes = new Map();
  const oyentes = new Map();
  ws.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pendientes.has(d.id)) {
      const { r, e } = pendientes.get(d.id);
      pendientes.delete(d.id);
      d.error ? e(new Error(`${d.error.message}`)) : r(d.result);
    } else if (d.method) for (const f of oyentes.get(d.method) ?? []) f(d.params);
  };
  const cdp = (method, params = {}) => new Promise((r, e) => {
    const i = ++id;
    pendientes.set(i, { r, e });
    ws.send(JSON.stringify({ id: i, method, params }));
  });
  const on = (evento, f) => oyentes.set(evento, [...(oyentes.get(evento) ?? []), f]);

  // Registro de peticiones /api/ con su código: es el oráculo HTTP de cada caso.
  const red = [];
  const porId = new Map();
  on("Network.requestWillBeSent", (p) => {
    if (p.request.url.includes("/api/")) porId.set(p.requestId, { url: p.request.url, metodo: p.request.method, t: Date.now() });
  });
  on("Network.responseReceived", (p) => {
    const r = porId.get(p.requestId);
    if (r) red.push({ ...r, codigo: p.response.status });
  });
  on("Network.loadingFailed", (p) => {
    const r = porId.get(p.requestId);
    if (r) red.push({ ...r, codigo: null, error: p.errorText });
  });
  await cdp("Page.enable");
  await cdp("Network.enable");
  await cdp("Runtime.enable");

  const pagina = {
    cdp, on, red,
    async viewport(ancho, alto, escala = 1, movil = false) {
      await cdp("Emulation.setDeviceMetricsOverride", { width: ancho, height: alto, deviceScaleFactor: escala, mobile: movil });
    },
    async tema(valor) {
      await cdp("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: valor }] });
    },
    async ir(url, ms = 9000) {
      await cdp("Page.navigate", { url });
      await espera(ms);
    },
    async eval(expr) {
      const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true });
      if (r.exceptionDetails) throw new Error(`${r.exceptionDetails.exception?.description ?? r.exceptionDetails.text}`);
      return r.result.value;
    },
    async esperar(expr, ms = 20000) {
      const fin = Date.now() + ms;
      while (Date.now() < fin) {
        try { if (await pagina.eval(expr)) return true; } catch { /* aún cargando */ }
        await espera(250);
      }
      return false;
    },
    async clic(selector, texto) {
      const ok = await pagina.eval(`(() => {
        const el = [...document.querySelectorAll(${JSON.stringify(selector)})]
          .find((e) => ${texto == null ? "true" : `e.textContent.trim().includes(${JSON.stringify(texto)})`});
        if (!el) return false; el.scrollIntoView({block: "center"}); el.click(); return true; })()`);
      if (!ok) throw new Error(`No se encontró ${selector} ${texto ?? ""}`);
    },
    async tecla(key, { shift = false } = {}) {
      const codigos = { Tab: 9, Enter: 13, Escape: 27, ArrowDown: 40, ArrowUp: 38, " ": 32 };
      const base = { key, code: key === " " ? "Space" : key, windowsVirtualKeyCode: codigos[key] ?? 0, modifiers: shift ? 8 : 0 };
      await cdp("Input.dispatchKeyEvent", { type: "keyDown", ...base, ...(key === "Enter" ? { text: "\r" } : {}) });
      await cdp("Input.dispatchKeyEvent", { type: "keyUp", ...base });
    },
    async mover(x, y) { await cdp("Input.dispatchMouseEvent", { type: "mouseMoved", x, y }); },
    async captura(ruta, { selector, completa = false } = {}) {
      let clip;
      if (selector) {
        const r = await pagina.eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)});
          if (!el) return null; el.scrollIntoView({block: "start"}); const b = el.getBoundingClientRect();
          return {x: b.x + scrollX, y: b.y + scrollY, width: b.width, height: b.height}; })()`);
        if (r) clip = { ...r, scale: 1 };
        await espera(400);
      }
      const opciones = { format: "png", captureBeyondViewport: completa || !!clip, ...(clip ? { clip } : {}) };
      const { data } = await cdp("Page.captureScreenshot", opciones);
      writeFileSync(ruta, Buffer.from(data, "base64"));
      return ruta;
    },
    async cerrar() {
      try { ws.close(); } catch { /* ya cerrado */ }
      pagina.proceso?.kill();
    },
  };
  return pagina;
}
