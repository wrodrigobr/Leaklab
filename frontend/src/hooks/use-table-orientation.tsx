import { useEffect, useState } from "react";
import type { TableOrientation } from "@/components/hud/PokerTableV3";

/**
 * Orientação da mesa do Replayer. "portrait" SÓ em phone em pé (estreito E mais alto que
 * largo) → geometria vertical nova. Phone deitado (largura > altura) e desktop usam
 * "landscape" (geometria existente). Reage a resize e rotação do device.
 */
function read(): TableOrientation {
  if (typeof window === "undefined") return "landscape";
  return window.innerWidth < 768 && window.innerHeight > window.innerWidth ? "portrait" : "landscape";
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
