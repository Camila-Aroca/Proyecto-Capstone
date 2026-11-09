import type { AreaPsiquiatria } from "./api";

/** Suma déficits por área; una cama libre en otra área nunca los compensa. */
export function resumirPropuestas(areas: AreaPsiquiatria[] | null, baseHospital: number) {
  const calculadas = (areas ?? []).filter((a) => a.propuesta_camas?.aumento_dotacion != null);
  const aumento = calculadas.length
    ? calculadas.reduce((suma, a) => suma + a.propuesta_camas!.aumento_dotacion!, 0) : null;
  const anos = new Set(calculadas.map((a) => a.propuesta_camas!.ano_objetivo));
  return {
    aumento,
    capacidadPropuesta: aumento == null ? null : baseHospital + aumento,
    areasConPropuesta: calculadas.length,
    areasTotales: areas?.length ?? 0,
    parcial: calculadas.length < (areas?.length ?? 0),
    ano: anos.size === 1 ? calculadas[0].propuesta_camas!.ano_objetivo : null,
  };
}
