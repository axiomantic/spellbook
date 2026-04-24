import { useEffect, useMemo, useState, useCallback } from 'react'
import { useConfig, useConfigSchema, useUpdateConfig } from '../hooks/useConfig'
import type { ConfigSchemaKey } from '../hooks/useConfig'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'
import { PageLayout } from '../components/layout/PageLayout'

function ToggleSwitch({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean
  onChange: (value: boolean) => void
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-accent-green focus:ring-offset-2 focus:ring-offset-bg-base ${
        checked ? 'bg-accent-green' : 'bg-bg-elevated'
      } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      <span
        className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
          checked ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  )
}

function AdminWarning() {
  return (
    <div className="mt-1 px-3 py-2 bg-accent-yellow/10 border border-accent-yellow/30 rounded text-xs text-accent-yellow">
      Disabling this will prevent the admin interface from mounting on next server restart.
    </div>
  )
}

function ConfigField({
  schema,
  value,
  onSave,
  saving,
  savedKey,
  errorKey,
}: {
  schema: ConfigSchemaKey
  value: unknown
  onSave: (key: string, value: unknown) => void
  saving: boolean
  savedKey: string | null
  errorKey: string | null
}) {
  const [editValue, setEditValue] = useState<string>(
    value !== undefined && value !== null ? String(value) : ''
  )
  const [dirty, setDirty] = useState(false)

  // Resync local state when the prop changes externally (e.g., after a
  // successful save refetches config, or a sibling field's save
  // invalidates the config query). Without this, editValue stays frozen
  // at mount value and the displayed input drifts from the authoritative
  // config for the lifetime of the component.
  //
  // Guarded by ``dirty``: if the user is actively editing, a background
  // refetch must not clobber their in-progress keystrokes. The save path
  // clears ``dirty`` on success so the next ``value`` tick resyncs
  // normally. The cancel path (not currently exposed in UI) would also
  // clear ``dirty``.
  useEffect(() => {
    if (dirty) return
    setEditValue(value !== undefined && value !== null ? String(value) : '')
  }, [value, dirty])

  const handleSave = useCallback(() => {
    let parsed: unknown = editValue
    if (schema.type === 'number') {
      parsed = parseFloat(editValue)
      if (isNaN(parsed as number)) return
    }
    onSave(schema.key, parsed)
    setDirty(false)
  }, [editValue, schema, onSave])

  const isSaved = savedKey === schema.key
  const isError = errorKey === schema.key

  if (schema.type === 'boolean') {
    const boolValue = value === true
    return (
      <div className="flex items-center justify-between py-3 px-4 border-b border-bg-border last:border-b-0">
        <div className="flex-1">
          <div className="font-mono text-sm text-text-primary">{schema.key}</div>
          <div className="text-xs text-text-dim mt-0.5">{schema.description}</div>
          {schema.key === 'admin_enabled' && !boolValue && <AdminWarning />}
        </div>
        <div className="flex items-center gap-2">
          {saving && savedKey === schema.key && (
            <span className="text-xs text-text-dim">Saving...</span>
          )}
          {isSaved && !saving && (
            <span className="text-xs text-accent-green">Saved</span>
          )}
          {isError && (
            <span className="text-xs text-accent-red">Error</span>
          )}
          <ToggleSwitch
            checked={boolValue}
            onChange={(val) => {
              if (schema.key === 'admin_enabled' && !val) {
                if (!window.confirm('Disabling admin_enabled will prevent the admin interface from mounting on next restart. Continue?')) {
                  return
                }
              }
              onSave(schema.key, val)
            }}
            disabled={saving}
          />
        </div>
      </div>
    )
  }

  const inputType =
    schema.secret
      ? 'password'
      : schema.type === 'number'
      ? 'number'
      : 'text'

  return (
    <div className="flex items-center justify-between py-3 px-4 border-b border-bg-border last:border-b-0">
      <div className="flex-1 mr-4">
        <div className="font-mono text-sm text-text-primary">
          {schema.key}
          {schema.secret && (
            <span className="ml-2 px-1.5 py-0.5 text-[10px] uppercase tracking-wider bg-accent-yellow/10 border border-accent-yellow/30 rounded text-accent-yellow">
              secret
            </span>
          )}
        </div>
        <div className="text-xs text-text-dim mt-0.5">{schema.description}</div>
      </div>
      <div className="flex items-center gap-2">
        <input
          type={inputType}
          step={schema.type === 'number' ? '0.1' : undefined}
          value={editValue}
          autoComplete={schema.secret ? 'new-password' : undefined}
          onChange={(e) => {
            setEditValue(e.target.value)
            setDirty(true)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && dirty) handleSave()
          }}
          className="bg-bg-elevated border border-bg-border rounded px-2 py-1 text-sm text-text-primary font-mono w-40 focus:outline-none focus:border-accent-green"
        />
        <button
          onClick={handleSave}
          disabled={!dirty || saving}
          className={`px-3 py-1 text-xs font-mono rounded transition-colors ${
            dirty && !saving
              ? 'bg-accent-green text-bg-base hover:bg-accent-green/80'
              : 'bg-bg-elevated text-text-dim cursor-not-allowed'
          }`}
        >
          Save
        </button>
        {isSaved && !saving && (
          <span className="text-xs text-accent-green">Saved</span>
        )}
        {isError && (
          <span className="text-xs text-accent-red">Error</span>
        )}
      </div>
    </div>
  )
}

/**
 * Convert a dotted config key into a human-readable section title.
 *
 * ``security.spotlighting.tier`` -> ``Security / Spotlighting``
 * ``notify_enabled``             -> ``General``
 */
function sectionTitleForKey(key: string): string {
  if (!key.includes('.')) {
    // worker_llm_* keys get their own logical group so the worker-llm panel
    // does not dominate "General". Anything else without a dot falls into
    // "General".
    if (key.startsWith('worker_llm_')) return 'Worker LLM'
    if (key.startsWith('notify_')) return 'Notifications'
    return 'General'
  }
  const parts = key.split('.')
  // Keep the first two segments: security.spotlighting.* -> "Security / Spotlighting".
  const head = parts.slice(0, 2).map((p) => p.charAt(0).toUpperCase() + p.slice(1))
  return head.join(' / ')
}

interface Section {
  title: string
  keys: ConfigSchemaKey[]
}

function groupKeys(keys: ConfigSchemaKey[]): Section[] {
  const map = new Map<string, ConfigSchemaKey[]>()
  for (const k of keys) {
    const title = sectionTitleForKey(k.key)
    if (!map.has(title)) map.set(title, [])
    map.get(title)!.push(k)
  }

  // Stable ordering: General first, Notifications second, Worker LLM third,
  // then everything else alphabetically. Inside a section, preserve the
  // schema-declared order so admins read them consistently.
  const priority: Record<string, number> = {
    General: 0,
    Notifications: 1,
    'Worker LLM': 2,
  }
  return Array.from(map.entries())
    .map(([title, entries]) => ({ title, keys: entries }))
    .sort((a, b) => {
      const pa = priority[a.title] ?? 10
      const pb = priority[b.title] ?? 10
      if (pa !== pb) return pa - pb
      return a.title.localeCompare(b.title)
    })
}

function CollapsibleSection({
  section,
  config,
  onSave,
  saving,
  savedKey,
  errorKey,
}: {
  section: Section
  config: Record<string, unknown>
  onSave: (key: string, value: unknown) => void
  saving: boolean
  savedKey: string | null
  errorKey: string | null
}) {
  // Default expanded; admins can collapse noisier sections they rarely touch.
  const [open, setOpen] = useState(true)

  return (
    <div className="mb-6">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 mb-2 font-mono text-xs uppercase tracking-widest text-text-dim hover:text-text-primary focus:outline-none"
        aria-expanded={open}
      >
        <span className="inline-block w-3 text-accent-green">
          {open ? 'v' : '>'}
        </span>
        <span>{section.title}</span>
        <span className="text-text-dim/50">({section.keys.length})</span>
      </button>
      {open && (
        <div className="bg-bg-surface border border-bg-border rounded">
          {section.keys.map((schema) => (
            <ConfigField
              key={schema.key}
              schema={schema}
              value={config[schema.key]}
              onSave={onSave}
              saving={saving}
              savedKey={savedKey}
              errorKey={errorKey}
            />
          ))}
        </div>
      )}
    </div>
  )
}

export function ConfigEditor() {
  const { data: configData, isLoading: configLoading, error: configError } = useConfig()
  const { data: schemaData, isLoading: schemaLoading } = useConfigSchema()
  const updateConfig = useUpdateConfig()
  const [savedKey, setSavedKey] = useState<string | null>(null)
  const [errorKey, setErrorKey] = useState<string | null>(null)

  const handleSave = useCallback(
    (key: string, value: unknown) => {
      setSavedKey(key)
      setErrorKey(null)
      updateConfig.mutate(
        { key, value },
        {
          onSuccess: () => {
            setSavedKey(key)
            setTimeout(() => setSavedKey(null), 2000)
          },
          onError: () => {
            setSavedKey(null)
            setErrorKey(key)
            setTimeout(() => setErrorKey(null), 3000)
          },
        },
      )
    },
    [updateConfig],
  )

  const sections = useMemo(
    () => groupKeys(schemaData?.keys ?? []),
    [schemaData],
  )

  if (configLoading || schemaLoading) {
    return (
      <PageLayout segments={[{ label: 'CONFIG' }]}>
        <div className="flex items-center justify-center">
          <LoadingSpinner />
        </div>
      </PageLayout>
    )
  }

  if (configError) {
    return (
      <PageLayout segments={[{ label: 'CONFIG' }]}>
        <div className="text-accent-red font-mono text-sm">
          Failed to load config: {(configError as Error).message}
        </div>
      </PageLayout>
    )
  }

  const config = configData?.config ?? {}

  return (
    <PageLayout segments={[{ label: 'CONFIG' }]}>
      <div className="max-w-3xl">
        <p className="text-sm text-text-secondary mb-6">
          Spellbook configuration. Changes are saved to spellbook.json immediately.
          Secret values (e.g. API keys) are stored in plaintext locally but masked in this view.
        </p>

        {sections.map((section) => (
          <CollapsibleSection
            key={section.title}
            section={section}
            config={config}
            onSave={handleSave}
            saving={updateConfig.isPending}
            savedKey={savedKey}
            errorKey={errorKey}
          />
        ))}
      </div>
    </PageLayout>
  )
}
