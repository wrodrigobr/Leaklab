import { TrendingUp, TrendingDown, Minus, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { StudentSummary } from "@/lib/api";

interface Props {
  student: StudentSummary;
}

const trendIcon = {
  improving: <TrendingUp className="size-3.5 text-primary" />,
  worsening: <TrendingDown className="size-3.5 text-destructive" />,
  stable:    <Minus className="size-3.5 text-muted-foreground" />,
};

export function StudentRow({ student }: Props) {
  return (
    <Link
      to={`/coach-dashboard/student/${student.id}`}
      className="flex items-center justify-between rounded-lg border border-border bg-hud-surface px-4 py-3 hover:border-primary/40 hover:bg-primary/5 transition-all group"
    >
      <div className="flex items-center gap-3">
        <div className="flex size-9 items-center justify-center rounded-full bg-primary/10 font-mono text-sm font-bold text-primary uppercase">
          {student.username[0]}
        </div>
        <div>
          <p className="font-medium text-sm text-foreground">{student.username}</p>
          <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">
            {student.total_tournaments} torneios
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        {student.trend && (
          <div className="hidden sm:flex items-center gap-1">
            {trendIcon[student.trend]}
            <span className="font-mono text-[10px] text-muted-foreground capitalize">
              {student.trend === "improving" ? "melhorando" : student.trend === "worsening" ? "piorando" : "estável"}
            </span>
          </div>
        )}
        {student.recent_tournament && (
          <div className="hidden md:block text-right">
            <p className="font-mono text-[10px] text-muted-foreground uppercase tracking-wider">Último torneio</p>
            <p className="font-mono text-xs text-foreground">
              {student.recent_tournament.avg_score != null
                ? `${student.recent_tournament.avg_score.toFixed(1)} pts`
                : "—"}
            </p>
          </div>
        )}
        <ChevronRight className="size-4 text-muted-foreground group-hover:text-primary transition-colors" />
      </div>
    </Link>
  );
}
