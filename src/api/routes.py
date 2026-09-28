"""Endpoints de la API v1.

Todas las rutas son de solo lectura y responden desde memoria. Los errores
esperables se modelan como HTTP explicitos:

- `503` mientras los datos cargan o el pronostico se calcula, con
  `Retry-After`, para que el cliente reintente en vez de mostrar un cero.
- `404` para una serie que no existe o que no es modelable, con el motivo.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from src.api.schemas import (
    Meta,
    PronosticoSerie,
    ResumenComuna,
    Salud,
    SerieConPronostico,
    Territorio,
)
from src.api.service import (
    ServicioDemanda,
    cobertura_holdout,
    formatear_pronostico,
    historico,
    registros,
    resumen_comunal,
)
from src.models.features import RM_SERIES_ID

router = APIRouter(prefix="/api/v1")

# Segundos sugeridos al cliente antes de reintentar mientras hay un calculo en curso.
REINTENTO_SEGUNDOS = "5"


def obtener_servicio(request: Request) -> ServicioDemanda:
    return request.app.state.servicio


Servicio = Annotated[ServicioDemanda, Depends(obtener_servicio)]


def _exigir_datos(servicio: ServicioDemanda) -> None:
    if servicio.estado_datos.estado == "listo":
        return
    if servicio.estado_datos.estado == "error":
        raise HTTPException(status_code=503, detail=servicio.estado_datos.detalle)
    raise HTTPException(
        status_code=503,
        detail="Cargando datos del pipeline.",
        headers={"Retry-After": REINTENTO_SEGUNDOS},
    )


def _exigir_pronostico(servicio: ServicioDemanda) -> None:
    _exigir_datos(servicio)
    if servicio.estado_pronostico.estado == "listo":
        return
    if servicio.estado_pronostico.estado == "error":
        raise HTTPException(status_code=503, detail=servicio.estado_pronostico.detalle)
    raise HTTPException(
        status_code=503,
        detail="Calculando el pronostico con el modelo seleccionado.",
        headers={"Retry-After": REINTENTO_SEGUNDOS},
    )


@router.get("/salud", response_model=Salud)
def salud(servicio: Servicio) -> Salud:
    detalle = servicio.estado_datos.detalle or servicio.estado_pronostico.detalle
    return Salud(
        estado_datos=servicio.estado_datos.estado,
        estado_pronostico=servicio.estado_pronostico.estado,
        detalle=detalle,
    )


@router.get("/meta", response_model=Meta)
def meta(servicio: Servicio) -> Meta:
    """Que modelo se sirve, hasta que semana hay datos y cuanto confiar en los intervalos."""
    _exigir_datos(servicio)
    seleccion = servicio.seleccion or {}
    datos = servicio.datos
    panel = datos.panel
    ultima = historico(panel, datos.calendario, RM_SERIES_ID, 1)
    modelo = seleccion.get("modelo_recomendado")
    nivel = seleccion.get("nivel_intervalo")
    cobertura = (
        cobertura_holdout(servicio.rutas.holdout_resumen, modelo, float(nivel))
        if modelo and nivel
        else None
    )

    advertencias = [
        "Las cifras son atenciones de urgencia (eventos), no personas únicas ni prevalencia.",
    ]
    for c in cobertura or []:
        if not c["dentro_de_tolerancia"]:
            advertencias.append(
                f"Intervalo {int(float(nivel) * 100)}%: fuera de muestra cubrió "
                f"{c['cobertura_observada']:.0%} en el nivel "
                f"{'regional' if c['nivel'] == 'region' else 'comunal'}. Interpretar los "
                "límites como orientativos."
            )
    if servicio.motivos:
        advertencias.append(
            f"{len(servicio.motivos)} comuna(s) sin pronóstico por falta de datos; "
            "se muestran como 'sin pronóstico', nunca como cero."
        )

    return Meta(
        modelo=modelo,
        horizontes=seleccion.get("horizontes", []),
        nivel_intervalo=nivel,
        ultima_semana_observada=registros(ultima)[0] if not ultima.empty else None,
        pronostico_calculado_en=(
            servicio.estado_pronostico.actualizado_en
            if servicio.estado_pronostico.estado == "listo"
            else None
        ),
        comunas_con_pronostico=int(panel.loc[panel["nivel"] == "comuna", "series_id"].nunique()),
        metricas_backtest=seleccion.get("metricas_backtest"),
        cobertura_holdout=cobertura,
        advertencias=advertencias,
    )


@router.get("/territorios", response_model=list[Territorio])
def territorios(servicio: Servicio) -> list[Territorio]:
    """Region y las 52 comunas RM, indicando cuales tienen pronostico y por que no."""
    _exigir_datos(servicio)
    modelables = set(servicio.nombres)
    salida = [Territorio(series_id=RM_SERIES_ID, nombre=servicio.nombres[RM_SERIES_ID],
                         nivel="region", tiene_pronostico=True)]
    for fila in servicio.territorial.sort_values("comuna_glosa").itertuples():
        codigo = str(fila.comuna_codigo)
        salida.append(
            Territorio(
                series_id=codigo,
                nombre=fila.comuna_glosa,
                nivel="comuna",
                tiene_pronostico=codigo in modelables,
                motivo_sin_pronostico=(
                    None if codigo in modelables
                    else servicio.motivos.get(codigo, "Sin serie modelable en el período evaluado.")
                ),
            )
        )
    return salida


@router.get("/series/{series_id}", response_model=SerieConPronostico)
def serie(
    series_id: str,
    servicio: Servicio,
    semanas: Annotated[int, Query(ge=1, le=520, description="Semanas historicas a devolver.")] = 104,
) -> SerieConPronostico:
    """Historia observada de una serie y, si ya esta calculado, su pronostico."""
    _exigir_datos(servicio)
    if series_id not in servicio.nombres:
        motivo = servicio.motivos.get(series_id, "La serie no existe.")
        raise HTTPException(status_code=404, detail=motivo)

    pasado = historico(servicio.datos.panel, servicio.datos.calendario, series_id, semanas)
    pronostico = None
    if servicio.estado_pronostico.estado == "listo":
        propio = servicio.pronostico[servicio.pronostico["series_id"] == series_id]
        pronostico = registros(formatear_pronostico(propio, servicio.nombres).drop(
            columns=["series_id", "nombre", "nivel"]
        ))
    return SerieConPronostico(
        series_id=series_id,
        nombre=servicio.nombres[series_id],
        nivel="region" if series_id == RM_SERIES_ID else "comuna",
        historico=registros(pasado),
        pronostico=pronostico,
        estado_pronostico=servicio.estado_pronostico.estado,
    )


@router.get("/pronosticos", response_model=list[PronosticoSerie])
def pronosticos(
    servicio: Servicio,
    nivel: Annotated[str | None, Query(pattern="^(region|comuna)$")] = None,
    horizonte: Annotated[int | None, Query(ge=1)] = None,
) -> list[dict[str, Any]]:
    """Pronostico de todas las series, filtrable por nivel y horizonte."""
    _exigir_pronostico(servicio)
    tabla = formatear_pronostico(servicio.pronostico, servicio.nombres)
    if nivel:
        tabla = tabla[tabla["nivel"] == nivel]
    if horizonte is not None:
        tabla = tabla[tabla["horizonte"] == horizonte]
    return registros(tabla)


@router.get("/resumen-comunal", response_model=list[ResumenComuna])
def resumen(servicio: Servicio) -> list[dict[str, Any]]:
    """Ranking comunal: nivel reciente, pronostico, variacion y contexto territorial."""
    _exigir_pronostico(servicio)
    tabla = resumen_comunal(
        servicio.datos.panel, servicio.pronostico, servicio.territorial, servicio.motivos
    )
    return registros(tabla)


@router.get("/geo/comunas")
def geo_comunas(servicio: Servicio) -> JSONResponse:
    """Limites comunales RM (Censo 2024) simplificados, en GeoJSON."""
    _exigir_datos(servicio)
    return JSONResponse(content=servicio.geojson, media_type="application/geo+json")
