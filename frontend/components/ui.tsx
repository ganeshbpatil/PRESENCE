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

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "danger";
}) {
  const styles = {
    primary:
      "bg-neutral-900 dark:bg-neutral-100 text-white dark:text-neutral-900 hover:opacity-90",
    secondary:
      "border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-50 dark:hover:bg-neutral-900",
    danger: "bg-red-700 text-white hover:bg-red-800",
  }[variant];

  return (
    <button
      {...props}
      className={`rounded px-3 py-1.5 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed ${styles} ${className}`}
    >
      {children}
    </button>
  );
}

// Money/message/access-changing actions get a native confirm() prompt
// before firing -- deliberately not a custom modal, this is a minimal
// admin panel, not a design system (see this file's header comment).
export function ConfirmButton({
  confirmMessage,
  onConfirm,
  children,
  variant = "danger",
  ...props
}: Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "onClick"> & {
  confirmMessage: string;
  onConfirm: () => void;
  variant?: "primary" | "secondary" | "danger";
}) {
  return (
    <Button
      {...props}
      variant={variant}
      onClick={() => {
        if (window.confirm(confirmMessage)) onConfirm();
      }}
    >
      {children}
    </Button>
  );
}

export function TextInput(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`w-full rounded border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-1.5 text-sm ${props.className ?? ""}`}
    />
  );
}

export function Select({
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      {...props}
      className={`w-full rounded border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-1.5 text-sm ${props.className ?? ""}`}
    >
      {children}
    </select>
  );
}
