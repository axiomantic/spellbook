interface ChoiceOption {
  value: string
  label: string
}

interface ChoiceProps {
  id?: string
  prompt?: string
  // `react-markdown` delivers HTML attributes as strings; we parse JSON
  // out of `options` on render.
  options?: string
}

function parseOptions(raw: string | undefined): ChoiceOption[] {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (o): o is ChoiceOption =>
        !!o &&
        typeof o === 'object' &&
        typeof (o as ChoiceOption).value === 'string' &&
        typeof (o as ChoiceOption).label === 'string',
    )
  } catch {
    return []
  }
}

/**
 * v2-reserved single-choice radio shortcode (§9.5).
 *
 * MVP renders a disabled preview with a "Reserved for v2" badge. There
 * is no POST surface; clicking a radio does nothing.
 */
export function Choice({ id, prompt, options }: ChoiceProps) {
  const opts = parseOptions(options)
  const name = id ?? 'choice'
  return (
    <fieldset
      disabled
      aria-label="Reserved for v2 — choice preview"
      data-testid="choice"
      className="my-3 border border-bg-border p-3 opacity-70"
    >
      {prompt && (
        <legend className="px-2 font-mono text-xs uppercase tracking-widest text-text-secondary">
          {prompt}
        </legend>
      )}
      <ul role="radiogroup" className="space-y-1 mt-1">
        {opts.map((opt, i) => (
          <li key={`${opt.value}-${i}`}>
            <label className="flex items-center gap-2 text-sm text-text-primary">
              <input type="radio" name={name} value={opt.value} disabled />
              {opt.label}
            </label>
          </li>
        ))}
      </ul>
      <span className="inline-block mt-2 px-2 py-0.5 font-mono text-xs uppercase tracking-widest text-accent-yellow border border-accent-yellow">
        Reserved for v2
      </span>
    </fieldset>
  )
}
