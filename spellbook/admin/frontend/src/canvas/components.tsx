import { Chart } from './shortcodes/Chart'
import { Diagram } from './shortcodes/Diagram'
import { Callout } from './shortcodes/Callout'
import { Tabs, Tab } from './shortcodes/Tabs'
import { Choice } from './shortcodes/Choice'
import { Approve } from './shortcodes/Approve'
import { Collapsible } from './shortcodes/Collapsible'

/**
 * Components-prop dispatch table (§2.2 override mechanism; §7.1 grammar lock).
 *
 * Keys are the lowercased HTML tag names that `rehype-raw` passes
 * through. Values are the React components defined under
 * `./shortcodes/`. The map covers all eight shortcodes from the locked
 * grammar (§7.1): chart, diagram, callout, tabs, tab, choice, approve, collapsible.
 *
 * Hoisted into its own module (§4.6 GATE-2) so the `renderChildren`
 * re-parse fix can import the shared map without forming an import
 * cycle through `render.tsx`.
 */
export const components = {
  chart: Chart,
  diagram: Diagram,
  callout: Callout,
  tabs: Tabs,
  tab: Tab,
  choice: Choice,
  approve: Approve,
  collapsible: Collapsible,
}
