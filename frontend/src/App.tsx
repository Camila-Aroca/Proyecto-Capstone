import { useEffect, useState } from "react";
import { Landing } from "./components/Landing";
import { Tablero } from "./components/Tablero";

// Enrutado minimo por hash, sin dependencias: `#/tablero` abre la vista de
// analisis y cualquier otra cosa muestra la pagina de entrada. El hash funciona
// en cualquier alojamiento estatico, sin necesitar reescritura del servidor.
const RUTA_TABLERO = "#/tablero";

function rutaActual(): string {
  return window.location.hash;
}

export default function App() {
  const [ruta, setRuta] = useState(rutaActual);

  useEffect(() => {
    const alCambiar = () => setRuta(rutaActual());
    window.addEventListener("hashchange", alCambiar);
    return () => window.removeEventListener("hashchange", alCambiar);
  }, []);

  // El foco vuelve al inicio del documento al cambiar de vista: sin esto, quien
  // navega con teclado o lector de pantalla queda donde estaba en la pagina anterior.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [ruta]);

  if (ruta.startsWith(RUTA_TABLERO)) return <Tablero />;
  return <Landing onEntrar={() => { window.location.hash = RUTA_TABLERO; }} />;
}
