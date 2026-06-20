import { useEffect, useState } from "react";
import type { TableOrientation } from "@/components/hud/PokerTableV3";

/**
 * Orientação da mesa do Replayer. "portrait" quando o viewport está em pé (mais alto que
 * largo) E abaixo do breakpoint do layout mobile (1024px = `lg`, o mesmo do Replayer) →
 * casa a geometria da mesa com o layout. Viewport deitado (largura ≥ altura) ou desktop
 * (≥1024) usam "landscape" (geometria existente). Reage a resize e rotação do device.
 */
function read(): TableOrientation {
  if (typeof window === "undefined") return "landscape";
  return window.innerWidth < 1024 && window.innerHeight > window.innerWidth ? "portrait" : "landscape";
}

export function useTableOrientation(): TableOrientation {
  const [orientation, setOrientation] = useState<TableOrientation>(read);
  useEffect(() => {
    const onChange = () => setOrientation(read());
    window.addEventListener("resize", onChange);
    window.addEventListener("orientationchange", onChange);
    return () => {
      window.removeEventListener("resize", onChange);
      window.removeEventListener("orientationchange", onChange);
    };
  }, []);
  return orientation;
}
