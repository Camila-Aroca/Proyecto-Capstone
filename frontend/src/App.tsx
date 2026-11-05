import { useEffect, useRef, useState } from "react";
import { Landing } from "./components/Landing";
import { Tablero } from "./components/Tablero";
import { VistaEstablecimientos } from "./components/VistaEstablecimientos";
import { RUTA_ESTABLECIMIENTOS, RUTA_TABLERO } from "./ruta";

// Enrutado minimo por hash, sin dependencias: `#/tablero` abre la vista comunal,
// `#/establecimientos` la vista por establecimiento y cualquier otra cosa muestra
// la pagina de entrada. El hash funciona en cualquier alojamiento estatico, sin
// necesitar reescritura del servidor. Los parametros de cada vista viven despues
// del `?` (ver ruta.ts).

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

  // Al cambiar de vista, la pagina vuelve arriba y el foco pasa al contenido
  // principal: sin esto, quien navega con teclado o lector de pantalla queda donde
  // estaba en la pagina anterior. En la carga inicial el foco no se mueve.
  const vista = ruta.split("?")[0];
  const primera = useRef(true);
  useEffect(() => {
    window.scrollTo(0, 0);
    if (primera.current) {
      primera.current = false;
      return;
    }
    document.getElementById("contenido")?.focus({ preventScroll: true });
  }, [vista]);

  if (ruta.startsWith(RUTA_TABLERO)) return <Tablero />;
  if (ruta.startsWith(RUTA_ESTABLECIMIENTOS)) return <VistaEstablecimientos />;
  return <Landing />;
}
