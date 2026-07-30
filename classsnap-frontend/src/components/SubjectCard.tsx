/**
 * Subject card mirroring the original Streamlit subject_card: white body,
 * thick pink left border, thin black outline, lavender code badge, and pink
 * stat chips with emoji icons.
 */
export function SubjectCard({
  name,
  code,
  section,
  stats,
  footer,
}: {
  name: string;
  code: string | null;
  section: string | null;
  stats?: { icon: string; label: string; value: number }[];
  footer?: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-3 rounded-[20px] border border-black border-l-8 border-l-snappink bg-white p-6">
        <h3 className="m-0 text-2xl font-semibold text-ink">{name}</h3>
        <p className="my-2.5 text-slate-500">
          Code:{" "}
          <span className="rounded-[5px] bg-lavender px-2 py-0.5 text-blurple">{code ?? "—"}</span>{" "}
          | Section: {section ?? "—"}
        </p>
        {stats && stats.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {stats.map((s) => (
              <div
                key={s.label}
                className="inline-flex items-center gap-1 rounded-xl bg-snappink px-3 py-1 text-sm text-white"
              >
                {s.icon} <b>{s.value}</b> {s.label}
              </div>
            ))}
          </div>
        ) : null}
      </div>
      {footer}
    </div>
  );
}
