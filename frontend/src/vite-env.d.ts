/// <reference types="vite/client" />

// Variables de entorno del frontend. Se leen de frontend/.env.local (no versionado).
// Todo lo que empieza con VITE_ queda incrustado en el bundle y es visible en el
// navegador: aqui solo van claves pensadas para uso en el cliente.
interface ImportMetaEnv {
  /** Clave de CARTO Basemaps. Sin ella, el mapa se dibuja sin fondo. */
  readonly VITE_CARTO_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
