import { useEffect, useState } from "react";

/**
 * true quando o viewport é de CELULAR DEITADO: abaixo do breakpoint do layout mobile
 * (1024px = `lg`) E mais largo que alto. Nesse caso o Replayer usa o modo "tela cheia":
 * a mesa preenche a tela e os controles/pill flutuam sobrepondo o feltro. Desktop (≥1024)
 * e celular em pé não entram. Reage a resize e rotação.
 */
function read(): boolean {
  if (typeof window === "undefined") return false;
  return window.innerWidth < 1024 && window.innerWidth > window.innerHeight;
}

export function useIsLandscapeMobile(): boolean {
  const [value, setValue] = useState<boolean>(read);
  useEffect(() => {
    const onChange = () => setValue(read());
    window.addEventListener("resize", onChange);
    window.addEventListener("orientationchange", onChange);
    return () => {
      window.removeEventListener("resize", onChange);
      window.removeEventListener("orientationchange", onChange);
    };
  }, []);
  return value;
}
