// Estado de cada vista en el hash (`#/establecimientos?comuna=13127&id=110`), para
// que un enlace lleve a la misma comuna o al mismo establecimiento, y para que el
// paso de una vista a la otra conserve el contexto.

export const RUTA_TABLERO = "#/tablero";
export const RUTA_ESTABLECIMIENTOS = "#/establecimientos";

export function parametros(): URLSearchParams {
  const hash = window.location.hash;
  const i = hash.indexOf("?");
  return new URLSearchParams(i === -1 ? "" : hash.slice(i + 1));
}

export function enlace(ruta: string, valores: Record<string, string | number | null | undefined>): string {
  const p = new URLSearchParams();
  for (const [clave, valor] of Object.entries(valores)) {
    if (valor != null && valor !== "") p.set(clave, String(valor));
  }
  const consulta = p.toString();
  return consulta ? `${ruta}?${consulta}` : ruta;
}

// replaceState no dispara `hashchange`: la URL refleja la seleccion sin volver a
// montar la vista ni sumar una entrada al historial por cada clic.
export function reflejar(ruta: string, valores: Record<string, string | number | null | undefined>): void {
  const destino = enlace(ruta, valores);
  if (window.location.hash !== destino) window.history.replaceState(null, "", destino);
}
