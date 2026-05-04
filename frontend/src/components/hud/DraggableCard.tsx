import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";
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
        className="absolute top-3 left-3 z-20 opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing rounded p-1 hover:bg-muted"
        title={t("actions.dragToReorder")}
        tabIndex={-1}
      >
        <GripVertical className="size-3.5 text-muted-foreground" />
      </button>
      {children}
    </div>
  );
}
