interface ApproveProps {
  id?: string
  prompt?: string
  confirm_label?: string
  decline_label?: string
}

/**
 * v2-reserved approval shortcode (§9.5).
 *
 * MVP renders a disabled preview with a "Reserved for v2" badge. No POST
 * surface exists in MVP.
 */
export function Approve({
  prompt,
  confirm_label,
  decline_label,
}: ApproveProps) {
  return (
    <div
      aria-label="Reserved for v2 — approval preview"
      data-testid="approve"
      className="my-3 border border-bg-border p-3 opacity-70"
    >
      {prompt && (
        <p className="font-mono text-xs uppercase tracking-widest text-text-secondary mb-2">
          {prompt}
        </p>
      )}
      <div className="flex gap-2">
        <button
          type="button"
          disabled
          className="px-3 py-1 border border-accent-green text-accent-green font-mono text-xs uppercase tracking-widest opacity-50"
        >
          {confirm_label ?? 'Approve'}
        </button>
        <button
          type="button"
          disabled
          className="px-3 py-1 border border-accent-red text-accent-red font-mono text-xs uppercase tracking-widest opacity-50"
        >
          {decline_label ?? 'Reject'}
        </button>
      </div>
      <span className="inline-block mt-2 px-2 py-0.5 font-mono text-xs uppercase tracking-widest text-accent-yellow border border-accent-yellow">
        Reserved for v2
      </span>
    </div>
  )
}
