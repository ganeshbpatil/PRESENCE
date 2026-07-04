// components/ui.tsx
//
// A handful of shared primitives so every panel section doesn't
// reimplement its own card/badge/table chrome. Deliberately small --
// this is a minimal read-only panel, not a design system.

export function Card({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-neutral-200 dark:border-neutral-800 p-4">
      <h2 className="text-sm font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wide mb-3">
        {title}
      </h2>
      {children}
    </section>
  );
}

const STATUS_STYLES: Record<string, string> = {
  healthy: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  degraded: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  broken: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  posted: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  pending: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  failed_no_connection: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

export function StatusBadge({ status }: { status: string }) {
  const style =
    STATUS_STYLES[status] ??
    "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}

export function EmptyState({ label }: { label: string }) {
  return <p className="text-sm text-neutral-500 dark:text-neutral-400">{label}</p>;
}

export function ErrorState({ message }: { message: string }) {
  return (
    <p className="text-sm text-red-700 dark:text-red-400" role="alert">
      {message}
    </p>
  );
}
