// Formato de cifras y fechas en convencion chilena (miles con punto, decimales con coma).

const entero = new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat("es-CL", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fechaCorta = new Intl.DateTimeFormat("es-CL", { day: "numeric", month: "short", timeZone: "UTC" });
const fechaLarga = new Intl.DateTimeFormat("es-CL", {
  day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
});

export const SIN_DATO = "sin dato";

export const fmtEntero = (v: number | null | undefined) => (v == null ? SIN_DATO : entero.format(v));
export const fmtDecimal = (v: number | null | undefined) => (v == null ? SIN_DATO : decimal.format(v));
export const fmtPct = (v: number | null | undefined) =>
  v == null ? SIN_DATO : `${v > 0 ? "+" : ""}${decimal.format(v)}%`;
export const fmtFechaCorta = (iso: string | null) => (iso ? fechaCorta.format(new Date(iso)) : SIN_DATO);
const mesCorto = new Intl.DateTimeFormat("es-CL", { month: "short", year: "2-digit", timeZone: "UTC" });
const mesLargo = new Intl.DateTimeFormat("es-CL", { month: "long", year: "numeric", timeZone: "UTC" });
export const fmtMesCorto = (iso: string | null) => (iso ? mesCorto.format(new Date(iso)) : SIN_DATO);
export const fmtMesLargo = (iso: string | null) => (iso ? mesLargo.format(new Date(iso)) : SIN_DATO);
export const fmtFechaLarga = (iso: string | null) => (iso ? fechaLarga.format(new Date(iso)) : SIN_DATO);
