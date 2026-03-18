import { useState, useCallback } from 'react'
import { useConfig, useConfigSchema, useUpdateConfig } from '../hooks/useConfig'
import type { ConfigSchemaKey } from '../hooks/useConfig'
import { LoadingSpinner } from '../components/shared/LoadingSpinner'

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

  return (
    <div className="flex items-center justify-between py-3 px-4 border-b border-bg-border last:border-b-0">
      <div className="flex-1 mr-4">
        <div className="font-mono text-sm text-text-primary">{schema.key}</div>
        <div className="text-xs text-text-dim mt-0.5">{schema.description}</div>
      </div>
      <div className="flex items-center gap-2">
        <input
          type={schema.type === 'number' ? 'number' : 'text'}
          step={schema.type === 'number' ? '0.1' : undefined}
          value={editValue}
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

const SECTIONS: { title: string; keys: string[] }[] = [
  {
    title: 'Text-to-Speech',
    keys: ['tts_enabled', 'tts_voice', 'tts_volume'],
  },
  {
    title: 'Notifications',
    keys: ['notify_enabled', 'notify_title'],
  },
  {
    title: 'General',
    keys: ['telemetry_enabled', 'auto_update', 'session_mode', 'admin_enabled'],
  },
]

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

  if (configLoading || schemaLoading) {
    return (
      <div className="p-8 flex items-center justify-center">
        <LoadingSpinner />
      </div>
    )
  }

  if (configError) {
    return (
      <div className="p-8">
        <div className="text-accent-red font-mono text-sm">
          Failed to load config: {(configError as Error).message}
        </div>
      </div>
    )
  }

  const config = configData?.config ?? {}
  const schemaKeys = schemaData?.keys ?? []
  const schemaMap = new Map(schemaKeys.map((k) => [k.key, k]))

  return (
    <div className="p-8 max-w-3xl">
      <h1 className="text-2xl font-sans text-text-primary mb-1">// CONFIG</h1>
      <p className="text-sm text-text-secondary mb-6">
        Spellbook configuration. Changes are saved to spellbook.json immediately.
      </p>

      {SECTIONS.map((section) => {
        const sectionKeys = section.keys
          .map((k) => schemaMap.get(k))
          .filter((s): s is ConfigSchemaKey => s !== undefined)

        if (sectionKeys.length === 0) return null

        return (
          <div key={section.title} className="mb-6">
            <h2 className="font-mono text-xs uppercase tracking-widest text-text-dim mb-2">
              {section.title}
            </h2>
            <div className="bg-bg-surface border border-bg-border rounded">
              {sectionKeys.map((schema) => (
                <ConfigField
                  key={schema.key}
                  schema={schema}
                  value={config[schema.key]}
                  onSave={handleSave}
                  saving={updateConfig.isPending}
                  savedKey={savedKey}
                  errorKey={errorKey}
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
