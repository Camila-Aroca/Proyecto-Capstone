# Frontend SAAD

Tablero web que consume la API del SAAD (`src/api/`): serie semanal con
pronóstico a 4–8 semanas, mapa comunal de variación esperada y tabla resumen.

Stack: React 19, TypeScript, Vite, Tailwind CSS 4, Recharts y React Leaflet.

## Requisitos

- Node.js 20 o superior.
- Backend corriendo (ver el README raíz). En desarrollo, Vite reenvía `/api`
  a `http://127.0.0.1:8000`; para otro destino, definir `SAAD_API_URL`.

## Uso

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # typecheck + build de producción en dist/
npm run typecheck
```

## Convenciones

- Los tipos de `src/api.ts` reflejan `src/api/schemas.py`; si cambia el
  contrato del backend, actualizarlos juntos.
- Un valor ausente se muestra como "sin dato" o "sin pronóstico", nunca como 0.
- Los colores se definen como tokens por rol en `src/index.css` (claro y
  oscuro) y se resuelven en `src/tokens.ts` para Recharts y Leaflet.
- El mapa base de CARTO es opcional (ver abajo). Sin clave, el mapa se dibuja
  solo con los límites comunales del Censo 2024 que entrega la API.

## Mapa base de CARTO

Desde septiembre de 2026 CARTO exige una clave para sus mapas base; sin ella
las teselas salen marcadas con "API KEY REQUIRED".

1. Pedir la clave gratuita en <https://carto.com/basemaps/apikey/>.
2. Copiar `frontend/.env.example` a `frontend/.env.local` y completar
   `VITE_CARTO_API_KEY`.
3. Reiniciar `npm run dev`: Vite lee las variables de entorno solo al arrancar.

El mapa usa `light_all` en modo claro y `dark_all` en modo oscuro, con la
atribución a CARTO y OpenStreetMap visible, que es condición del plan gratuito
(5 millones de teselas al mes para uso no comercial).

`frontend/.env.local` está excluido de git. Aun así, toda variable `VITE_*`
queda incrustada en el JavaScript y es visible en el navegador: no poner ahí
claves que no estén pensadas para uso en el cliente.
