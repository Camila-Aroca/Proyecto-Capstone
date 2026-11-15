# Diccionario de datos: `contraste_camas_psiquiatria_rm`

- **Ruta:** `data/processed/marts/contraste_camas_psiquiatria_rm.parquet`.
- **Constructor:** `src/data/build_contraste_camas_psiquiatria_rm.py`, stage `build_contraste_camas_psiquiatria_rm` (upstream: `build_egresos_f00_f99`, `build_mart_ocupacion_psiquiatria_hospital_rm`). Pruebas: `tests/test_mart_egresos_f00_f99_rm.py`. EDA: `reports/eda/eda_mart_egresos_f00_f99_rm.md`.
- **Propósito:** respaldar con una segunda fuente la escala de la propuesta de camas, que usa REM-20. Compara, por año, las camas de psiquiatría ocupadas en promedio según Egresos y según REM-20. Si ambas dan el mismo orden de magnitud, la escala queda respaldada; no deben coincidir exactamente.
- **Fuente:** `egresos_f00_f99_nacional_2020_2025` (residentes RM) y `mart_ocupacion_psiquiatria_hospital_rm`.

**Grano:** una fila por año de la RM (6 filas, 2020-2025), solo años con REM-20 de los 12 meses. **Llave lógica verificada:** `ano`. No es territorial.

| Columna | Tipo | Semántica |
|---|---|---|
| `ano` | int32 | Año. |
| `egresos_residentes_rm` | int64 | Egresos F00-F99 de residentes RM en el año (registros publicados, no pacientes únicos). |
| `camas_equivalentes_egresos` | float64 | Suma de `dias_estada_acotado_anual` de esos egresos dividida por los días del año. **Cota superior**: Egresos publica el año, no la fecha, así que una estadía larga puede haber empezado el año anterior. |
| `camas_equivalentes_egresos_snss` | float64 | Igual, solo egresos en establecimientos del SNSS. |
| `camas_ocupadas_rem20` | float64 | Días cama ocupados de las áreas de psiquiatría de los hospitales de la oferta RM (REM-20) divididos por los días del año. |
| `camas_ocupadas_rem20_sin_forense` | float64 | Igual, sin las áreas forenses (códigos 423 a 426), cuyos pacientes rara vez egresan dentro del año. |
| `razon_egresos_snss_rem20_sin_forense` | float64 | `camas_equivalentes_egresos_snss / camas_ocupadas_rem20_sin_forense`. Redondeada a 3 decimales; las camas, a 1. |

## Por qué no coinciden exactamente

- Egresos cuenta pacientes con diagnóstico psiquiátrico también en camas no psiquiátricas (p. ej. delirium en medicina interna) y de hospitales fuera del SNSS; por eso se publica la variante solo SNSS.
- REM-20 cuenta las áreas forenses; por eso se publica la variante sin forense.
- Egresos ubica al paciente por residencia y REM-20 por hospital: la RM recibe pacientes de otras regiones en sus centros de referencia.

## Advertencias de interpretación

- Es estadística anual consolidada, no ocupación ni disponibilidad en tiempo real; no es gestión de cupos.
- No enlaza Egresos con establecimientos: la comparación es agregada por año.
- Una medida no positiva hace fallar la etapa.
