# Ciclo 15 — retest de DEF-12, DEF-13 y DEF-14 en AWS

**Fecha:** 2026-11-16 (UTC)  
**Ejecutora:** Catalina  
**Código:** commit `1c5c191`; frontend publicado con `infra/aws/scripts/desplegar.sh 95d00f8 1`
(pila `Saad`, sin cambios en la API: imagen `95d00f8`, 1 tarea, 512 CPU, 2048 MB)  
**Versión verificada:** el sitio en AWS sirve `assets/index-CIZljhEQ.js`, el mismo bundle que el build local del commit.

## Método

Chrome headless controlado por CDP, con un perfil nuevo por ejecución (sin sesión previa) y
configurado como dispositivo con mouse (`--blink-settings=primaryHoverType=2,…`), porque sin eso
Chrome headless reporta `hover: none` y los tooltips no se pueden probar. Se espera 12 s a que
cargue cada vista. La URL de CloudFront se omite a propósito; en este registro va como `<base>`.

- **Desborde:** `document.documentElement.scrollWidth` frente a `innerWidth`, más la lista de
  elementos que salen por la derecha sin estar dentro de un contenedor desplazable.
- **Contraste:** se calcula con los colores computados del texto y del primer fondo opaco, con la
  fórmula de luminancia relativa de WCAG 2.x.

## Resultados

| Caso | Defecto | Verificación | Resultado | Estado |
|---|---|---|---|---|
| SAAD-CP-004 | DEF-12 | `<base>/#/establecimientos?id=999999999&semanas=52` | La URL pasa a `id=109102` y no queda ningún `role="alert"` | APROBADO |
| SAAD-CP-073 | DEF-13 | «· 4 advertencias» (`#/tablero`) | Claro 6,36:1 · oscuro 10,63:1 (mínimo 4,5:1) | APROBADO |
| SAAD-CP-073 | DEF-13 | «en desarrollo» (`#/` y `#/tablero`) | Claro 7,64:1 · oscuro 9,18:1 | APROBADO |
| SAAD-CP-071 | DEF-14 | Ventana de 360×800: `#/`, `#/tablero`, `#/establecimientos` y `#/establecimientos?id=111100` | Documento de 345 px en las cuatro vistas (la diferencia es la barra de desplazamiento); ningún elemento fuera de pantalla | APROBADO |
| SAAD-CP-072 | DEF-14 | Ventana de 640 px (equivale a 1280 px al 200 % de zoom), `#/tablero` | Documento de 625 px, sin desborde | APROBADO |
| — | Regresión de DEF-14 | Tooltip del encabezado «Reciente» | Con mouse: `display: block`, opacidad 1. Con foco de teclado (`:focus-visible`): `display: block`, opacidad 1 | APROBADO |

## Antes y después

| Medición | Ciclo 10 (AWS, antes) | Ciclo 15 (AWS, después) |
|---|---|---|
| Ancho del documento en `#/tablero` a 360 px | 533 px (173 px de desborde) | 345 px (0) |
| Ancho del documento en `#/tablero` a 640 px | 674–684 px (34–44 px) | 625 px (0) |
| Contraste de «advertencias», tema claro | 4,09:1 | 6,36:1 |
| Contraste de «en desarrollo», tema claro | 4,26:1 | 7,64:1 |
| Alerta persistente en SAAD-CP-004 | Sí | No |
