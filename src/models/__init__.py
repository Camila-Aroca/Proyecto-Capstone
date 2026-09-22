"""Modelos de demanda de urgencia en salud mental para la Region Metropolitana.

Organizacion del paquete:

- `features`: construccion del panel y de la matriz supervisada (estrategia
  directa por horizonte, sin fuga de informacion futura).
- `metrics`: metricas puntuales y de intervalo, incluidas MASE y cobertura.
- `backtesting`: motor de validacion con origenes de pronostico deslizantes.
- `baseline`: baseline estacional ingenuo, referencia obligatoria del alcance.
- `gradient_boosting`: modelo global multi-serie (LightGBM) sobre el panel.
- `hierarchy`: reconciliacion jerarquica entre el agregado RM y las comunas.

Contrato analitico fijado en `reports/eda/eda_series_demanda_sm.md`:
grano jerarquico (RM + comunas), target conteo `atenciones_id36` con ID37
incluido, horizonte 4-8 semanas, periodo cerrado 2021-2025 y calendario
semanal DEIS de 52 semanas regulares por anio.
"""

from __future__ import annotations

# Semilla unica del paquete: todo componente estocastico debe derivar de ella
# para que el backtesting sea reproducible entre ejecuciones y entornos.
RANDOM_SEED: int = 42

__all__ = ["RANDOM_SEED"]
