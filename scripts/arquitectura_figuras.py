"""Figuras del Documento de Arquitectura de Software, dibujadas desde código.

Las figuras se generan con Matplotlib a partir de las estructuras declaradas aquí, de modo
que el documento no dependa de imágenes editadas a mano: si cambia un componente, se edita
su entrada y se regenera. Usan la paleta del kit de identidad SAAD (`saad-tokens.css`).

El estado de un componente nunca se comunica solo con color: lo planificado lleva además
borde punteado y la palabra "planificado" en su etiqueta.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Sequence

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

# --- Paleta de marca (saad-tokens.css) -------------------------------------------------
PRIMARY_DEEP: Final[str] = "#0b4660"
PRIMARY: Final[str] = "#0f5a78"
SECONDARY: Final[str] = "#2f74a8"
MINT: Final[str] = "#86bea9"
ACCENT: Final[str] = "#eba845"
MINT_SOFT: Final[str] = "#e3f1eb"
SKY_SOFT: Final[str] = "#e3f0f8"
ACCENT_SOFT: Final[str] = "#fcf1dc"
SUCCESS: Final[str] = "#1f6b55"
WARNING: Final[str] = "#7a4f0a"
TEXT: Final[str] = "#0f2a38"
TEXT_SECONDARY: Final[str] = "#34505f"
MUTED: Final[str] = "#5e7685"
BORDER: Final[str] = "#d5e0e6"
BG_ALT: Final[str] = "#eef3f6"
SURFACE: Final[str] = "#ffffff"

# Relleno, borde y estilo de línea por estado del componente.
ESTILOS: Final[dict[str, tuple[str, str, str]]] = {
    "implementado": (MINT_SOFT, SUCCESS, "solid"),
    "planificado": (ACCENT_SOFT, WARNING, (0, (4, 2.5))),
    "externo": (SKY_SOFT, SECONDARY, "solid"),
    "neutro": (SURFACE, MUTED, "solid"),
}
ETIQUETAS: Final[dict[str, str]] = {
    "implementado": "Implementado y verificado",
    "planificado": "Planificado (borde punteado)",
    "externo": "Sistema o fuente externa",
}

# Inter es la fuente de texto de la marca; si no está instalada se usa la más
# cercana disponible, sin emitir una advertencia por cada figura.
_INSTALADAS: Final[set[str]] = {fuente.name for fuente in font_manager.fontManager.ttflist}
FUENTES: Final[list[str]] = [
    fuente for fuente in ("Inter", "Segoe UI", "DejaVu Sans") if fuente in _INSTALADAS
] or ["sans-serif"]
DPI: Final[int] = 220


@dataclass(frozen=True)
class Caja:
    """Un componente: su texto y su estado."""

    texto: str
    estado: str = "implementado"


def _lienzo(ancho: float, alto: float):
    plt.rcParams["font.family"] = FUENTES
    figura, eje = plt.subplots(figsize=(ancho, alto), dpi=DPI)
    eje.set_xlim(0, 100)
    eje.set_ylim(0, 100)
    eje.axis("off")
    figura.patch.set_facecolor(SURFACE)
    return figura, eje


def _caja(eje, x: float, y: float, w: float, h: float, caja: Caja, tamano: float = 7.6) -> None:
    relleno, borde, linea = ESTILOS[caja.estado]
    eje.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0,rounding_size=1.1",
            facecolor=relleno, edgecolor=borde, linewidth=1.1, linestyle=linea, zorder=3,
        )
    )
    eje.text(
        x + w / 2, y + h / 2, caja.texto, ha="center", va="center", fontsize=tamano,
        color=TEXT, linespacing=1.25, zorder=4,
    )


def _banda(eje, y: float, h: float, titulo: str, x: float = 1.0, w: float = 98.0) -> None:
    eje.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0,rounding_size=1.4",
            facecolor=BG_ALT, edgecolor=BORDER, linewidth=1.0, zorder=1,
        )
    )
    eje.text(x + 1.4, y + h - 1.5, titulo, ha="left", va="top", fontsize=8.6,
             fontweight="bold", color=PRIMARY_DEEP, zorder=2)


def _flecha(eje, origen: tuple[float, float], destino: tuple[float, float],
            punteada: bool = False, texto: str | None = None,
            desplazamiento: tuple[float, float] = (0.0, 0.0)) -> None:
    eje.add_patch(
        FancyArrowPatch(
            origen, destino, arrowstyle="-|>", mutation_scale=11, linewidth=1.2,
            color=TEXT_SECONDARY, linestyle=(0, (4, 2.5)) if punteada else "solid", zorder=5,
            shrinkA=0, shrinkB=0,
        )
    )
    if texto:
        eje.text(
            (origen[0] + destino[0]) / 2 + desplazamiento[0],
            (origen[1] + destino[1]) / 2 + desplazamiento[1],
            texto, ha="center", va="center", fontsize=6.8, color=TEXT_SECONDARY, zorder=6,
            bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 1.2},
        )


def _fila(eje, y: float, h: float, cajas: Sequence[Caja], x0: float = 3.0, x1: float = 97.0,
          separacion: float = 1.6, tamano: float = 7.6) -> list[tuple[float, float]]:
    """Reparte las cajas en una fila y devuelve el centro horizontal y ancho de cada una."""
    ancho = (x1 - x0 - separacion * (len(cajas) - 1)) / len(cajas)
    posiciones = []
    for indice, caja in enumerate(cajas):
        x = x0 + indice * (ancho + separacion)
        _caja(eje, x, y, ancho, h, caja, tamano)
        posiciones.append((x + ancho / 2, ancho))
    return posiciones


def _leyenda(eje, y: float, estados: Sequence[str] = ("implementado", "planificado", "externo")) -> None:
    x = 3.0
    for estado in estados:
        relleno, borde, linea = ESTILOS[estado]
        eje.add_patch(
            FancyBboxPatch((x, y), 3.2, 2.2, boxstyle="round,pad=0,rounding_size=0.5",
                           facecolor=relleno, edgecolor=borde, linewidth=1.0, linestyle=linea, zorder=3)
        )
        eje.text(x + 4.2, y + 1.1, ETIQUETAS[estado], ha="left", va="center", fontsize=6.8,
                 color=TEXT_SECONDARY)
        x += 31.5


def _guardar(figura, ruta: Path) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(ruta, dpi=DPI, bbox_inches="tight", pad_inches=0.12, facecolor=SURFACE)
    plt.close(figura)
    return ruta


# --------------------------------------------------------------------------------------
# Figura 1: vista lógica por capas
# --------------------------------------------------------------------------------------
CAPAS: Final[list[tuple[str, list[Caja]]]] = [
    (
        "Fuentes oficiales externas · consumo por lotes",
        [
            Caja("DEIS / MINSAL\nUrgencias, Egresos\ny Establecimientos", "externo"),
            Caja("INE\nCenso 2024 y\nproyecciones", "externo"),
            Caja("MDS\nCasen 2022", "externo"),
            Caja("Estadísticas\nde Género", "externo"),
            Caja("OpenStreetMap y GTFS\nplanificado", "planificado"),
        ],
    ),
    (
        "Capa de datos · src/data/ y scripts/run_pipeline.py",
        [
            Caja("Orquestador\ndel DAG\n32 etapas"),
            Caja("Ingesta y\nprocedencia"),
            Caja("Limpieza y\nnormalización"),
            Caja("Dimensiones\ny catálogos"),
            Caja("Marts\nanalíticos"),
            Caja("Contratos\nde output"),
        ],
    ),
    (
        "Almacenamiento · archivos versionables y regenerables",
        [
            Caja("data/raw/\nsnapshots con SHA256"),
            Caja("data/processed/\nParquet y GeoParquet"),
            Caja("data/processed/modeling/\npronóstico vigente\ny manifiesto"),
            Caja("PostgreSQL / PostGIS\nDDL diseñado · planificado", "planificado"),
        ],
    ),
    (
        "Capa analítica · src/models/ y scripts/",
        [
            Caja("EDA y\nperfilado"),
            Caja("Modelos de\ndemanda"),
            Caja("Benchmark\ny holdout"),
            Caja("Persistencia\ndel pronóstico"),
            Caja("Accesibilidad\nterritorial\nplanificado", "planificado"),
            Caja("Análisis de\nhospitalización\nplanificado", "planificado"),
        ],
    ),
    (
        "Capa de servicios · src/api/",
        [Caja("API REST de solo lectura · FastAPI · /api/v1 · responde desde memoria")],
    ),
    (
        "Capa de presentación · frontend/",
        [Caja("Aplicación web de una página · React · portada y tablero con serie, mapa comunal y tabla")],
    ),
]


def figura_capas(ruta: Path) -> Path:
    # El lienzo es angosto a propósito: en la página la figura se reduce poco y su
    # texto se sigue leyendo impreso.
    figura, eje = _lienzo(7.6, 7.9)
    altos = [14.0, 14.0, 14.0, 14.0, 9.5, 9.5]
    separacion = 3.4
    y = 96.0
    centros: list[float] = []
    for (titulo, cajas), alto in zip(CAPAS, altos):
        y -= alto
        _banda(eje, y, alto, titulo)
        _fila(eje, y + 1.4, alto - 5.4, cajas, tamano=7.0 if len(cajas) > 1 else 7.4)
        centros.append(y)
        y -= separacion
    # Una flecha entre cada par de capas consecutivas: la dependencia baja hacia la presentación.
    for superior, alto in zip(centros[:-1], altos[:-1]):
        _flecha(eje, (50.0, superior - 0.2), (50.0, superior - separacion + 0.2))
    _leyenda(eje, 0.6)
    return _guardar(figura, ruta)


# --------------------------------------------------------------------------------------
# Figura 2: vista de ejecución
# --------------------------------------------------------------------------------------
def figura_ejecucion(ruta: Path) -> Path:
    figura, eje = _lienzo(7.6, 5.7)

    _banda(eje, 56.0, 40.0, "A. Proceso por lotes · lo ejecuta el equipo con scripts/run_pipeline.py")
    lote = [
        Caja("Fuentes\noficiales", "externo"),
        Caja("Descarga y\nvalidación\nen temporal"),
        Caja("data/raw/\nsnapshot y\nprocedencia"),
        Caja("Limpieza,\ndimensiones\ny marts"),
        Caja("Benchmark y\nselección\ncongelada"),
        Caja("Pronóstico\npersistido y\nmanifiesto"),
    ]
    posiciones = _fila(eje, 64.0, 20.0, lote, separacion=3.4, tamano=7.2)
    for (x_a, w_a), (x_b, w_b) in zip(posiciones[:-1], posiciones[1:]):
        _flecha(eje, (x_a + w_a / 2, 74.0), (x_b - w_b / 2, 74.0))
    eje.text(50.0, 59.6,
             "Cada etapa hace SKIP si sus outputs existen y cumplen su contrato; --force la regenera.",
             ha="center", va="center", fontsize=6.8, color=TEXT_SECONDARY)

    _banda(eje, 4.0, 44.0, "B. Consulta en línea · cada visita a la plataforma")
    consulta = [
        Caja("Navegador\ndel usuario", "neutro"),
        Caja("Aplicación\nweb React"),
        Caja("API REST\n/api/v1"),
        Caja("Servicio en\nmemoria"),
    ]
    en_linea = _fila(eje, 16.0, 18.0, consulta, x0=3.0, x1=66.0, separacion=6.6, tamano=7.0)
    etiquetas = ["HTTP", "JSON", "filtra"]
    for ((x_a, w_a), (x_b, w_b)), etiqueta in zip(zip(en_linea[:-1], en_linea[1:]), etiquetas):
        _flecha(eje, (x_a + w_a / 2, 25.0), (x_b - w_b / 2, 25.0), texto=etiqueta,
                desplazamiento=(0.0, 3.4))
    _caja(eje, 73.0, 27.5, 24.0, 12.5, Caja("Marts, cartografía\ny selección"), tamano=7.0)
    _caja(eje, 73.0, 10.0, 24.0, 12.5, Caja("Pronóstico persistido\nsi sigue vigente"), tamano=7.0)
    x_servicio, w_servicio = en_linea[-1]
    _flecha(eje, (73.0, 33.0), (x_servicio + w_servicio / 2, 28.5), texto="lee al\narrancar",
            desplazamiento=(-0.6, 5.2))
    _flecha(eje, (73.0, 16.5), (x_servicio + w_servicio / 2, 21.5), texto="reutiliza o\nrecalcula",
            desplazamiento=(-0.6, -5.4))
    eje.text(34.5, 9.4,
             "Mientras los datos cargan o el pronóstico se calcula, la API responde 503 con Retry-After\n"
             "y la aplicación reintenta: nunca muestra un cero en lugar de un dato ausente.",
             ha="center", va="center", fontsize=6.6, color=TEXT_SECONDARY, linespacing=1.3)

    # Los outputs del pipeline son el único puente entre ambos procesos.
    _flecha(eje, (85.0, 56.0), (85.0, 40.0), punteada=True, texto="outputs del\npipeline",
            desplazamiento=(-8.0, 3.6))
    return _guardar(figura, ruta)


# --------------------------------------------------------------------------------------
# Figura 3: vista de despliegue
# --------------------------------------------------------------------------------------
def figura_despliegue(ruta: Path) -> Path:
    figura, eje = _lienzo(7.6, 6.0)

    # --- Vigente ----------------------------------------------------------------------
    _banda(eje, 14.0, 82.0, "Vigente · ejecución local de desarrollo", x=1.0, w=47.5)
    eje.text(2.4, 90.2, "Equipo del integrante (Windows o WSL2)", ha="left", va="top",
             fontsize=7.4, color=TEXT_SECONDARY)
    _caja(eje, 4.0, 74.0, 41.5, 10.0, Caja("Navegador", "neutro"))
    _caja(eje, 4.0, 57.0, 41.5, 11.0,
          Caja("Servidor de desarrollo Vite · 5173\nsirve la aplicación y reenvía /api"), tamano=7.2)
    _caja(eje, 4.0, 40.0, 41.5, 11.0, Caja("Uvicorn + FastAPI · 8000\nproceso único, estado en memoria"), tamano=7.2)
    _caja(eje, 4.0, 18.0, 19.5, 16.0, Caja("Sistema de archivos\ndata/ y reports/"))
    _caja(eje, 26.0, 18.0, 19.5, 16.0, Caja("Pipeline por lotes\nrun_pipeline.py"))
    _flecha(eje, (24.75, 74.0), (24.75, 68.0), texto="HTTP", desplazamiento=(4.6, 0.0))
    _flecha(eje, (24.75, 57.0), (24.75, 51.0), texto="proxy /api", desplazamiento=(6.4, 0.0))
    _flecha(eje, (13.75, 40.0), (13.75, 34.0), texto="lee", desplazamiento=(3.6, 0.0))
    _flecha(eje, (26.0, 26.0), (23.5, 26.0))

    # --- Objetivo ---------------------------------------------------------------------
    _banda(eje, 14.0, 82.0, "Objetivo · Docker Compose · planificado", x=51.5, w=47.5)
    eje.text(52.9, 90.2, "Host de despliegue", ha="left", va="top", fontsize=7.4, color=TEXT_SECONDARY)
    _caja(eje, 54.5, 74.0, 41.5, 10.0, Caja("Navegador", "neutro"))
    _caja(eje, 54.5, 57.0, 41.5, 11.0,
          Caja("Contenedor web · planificado\nestáticos y proxy inverso", "planificado"), tamano=7.2)
    _caja(eje, 54.5, 40.0, 41.5, 11.0, Caja("Contenedor api · planificado\nUvicorn + FastAPI", "planificado"), tamano=7.2)
    _caja(eje, 54.5, 18.0, 19.5, 16.0,
          Caja("Contenedor db\nPostgreSQL + PostGIS\nplanificado", "planificado"))
    _caja(eje, 76.5, 18.0, 19.5, 16.0,
          Caja("Tarea por lotes\npipeline y volumen\nplanificado", "planificado"))
    _flecha(eje, (75.25, 74.0), (75.25, 68.0), texto="HTTPS", desplazamiento=(5.2, 0.0))
    _flecha(eje, (75.25, 57.0), (75.25, 51.0), texto="/api", desplazamiento=(4.0, 0.0))
    _flecha(eje, (64.25, 40.0), (64.25, 34.0), punteada=True)
    _flecha(eje, (76.5, 26.0), (74.0, 26.0), punteada=True)

    # --- Servicios externos, comunes a ambos ------------------------------------------
    _caja(eje, 4.0, 2.0, 41.5, 8.6,
          Caja("Fuentes oficiales · HTTPS, por lotes\nDEIS, INE, MDS, Estadísticas de Género", "externo"),
          tamano=7.0)
    _caja(eje, 54.5, 2.0, 41.5, 8.6,
          Caja("CARTO Basemaps · HTTPS, teselas\nopcional, lo consume el navegador", "externo"),
          tamano=7.0)
    return _guardar(figura, ruta)


def generar_todas(directorio: Path) -> dict[str, Path]:
    """Genera las tres figuras y devuelve sus rutas por nombre."""
    return {
        "capas": figura_capas(directorio / "arquitectura_capas.png"),
        "ejecucion": figura_ejecucion(directorio / "arquitectura_ejecucion.png"),
        "despliegue": figura_despliegue(directorio / "arquitectura_despliegue.png"),
    }
