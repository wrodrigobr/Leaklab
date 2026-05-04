import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripHorizontal } from "lucide-react";
import { useTranslation } from "react-i18next";

interface DraggableCardProps {
  id: string;
  children: React.ReactNode;
  className?: string;
}

export function DraggableCard({ id, children, className }: DraggableCardProps) {
  const { t } = useTranslation("common");
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
    zIndex: isDragging ? 10 : undefined,
  };

  return (
    <div ref={setNodeRef} style={style} className={`group relative ${className ?? ""}`}>
      <button
        {...attributes}
        {...listeners}
        className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 z-20 opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing rounded-full px-2 py-0.5 bg-card border border-border hover:border-primary/40 shadow-sm"
        title={t("actions.dragToReorder")}
        tabIndex={-1}
      >
        <GripHorizontal className="size-3 text-muted-foreground" />
      </button>
      {children}
    </div>
  );
}
