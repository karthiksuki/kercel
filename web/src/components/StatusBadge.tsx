type Props = {
  status: string;
};

const STATUS_MAP: Record<string, string> = {
  queued: "badge-queued",
  building: "badge-building",
  deploying: "badge-building",
  live: "badge-live",
  failed: "badge-failed",
};

export function StatusBadge({ status }: Props) {
  const cls = STATUS_MAP[status.toLowerCase()] ?? "badge-default";
  const isActive = ["building", "deploying", "queued"].includes(
    status.toLowerCase(),
  );

  return (
    <span className={`badge ${cls}`}>
      {isActive && <span className="badge-dot" />}
      {status}
    </span>
  );
}
