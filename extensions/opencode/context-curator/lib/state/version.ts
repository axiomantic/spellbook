/**
 * Current schema version for state persistence
 */
export const CURRENT_SCHEMA_VERSION = 1;

/**
 * Migration functions for upgrading state schemas
 */
type MigrationFn = (state: unknown) => unknown;

const migrations: Record<number, MigrationFn> = {
  // Version 1 is initial, no migration needed
  1: (state) => state,
};

/**
 * Migrate state from older version to current
 */
export function migrateState(state: unknown, fromVersion: number): unknown {
  let current = state;

  for (let v = fromVersion; v < CURRENT_SCHEMA_VERSION; v++) {
    const migrate = migrations[v + 1];
    if (migrate) {
      current = migrate(current);
    }
  }

  return current;
}

/**
 * Check if state needs migration
 */
export function needsMigration(version: number): boolean {
  return version < CURRENT_SCHEMA_VERSION;
}
