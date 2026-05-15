import { VegaLite, type VisualizationSpec } from 'react-vega'

interface ChartImplProps {
  spec: object
}

/**
 * Lazy-loaded Vega-Lite chart renderer. Imported via
 * `lazy(() => import())` from `Chart.tsx` so `react-vega`, `vega`, and
 * `vega-lite` live in their own Vite chunks and stay out of the initial
 * admin bundle.
 *
 * The shortcode upstream (`Chart`) is responsible for JSON parsing /
 * validation; this component receives an already-parsed spec object.
 */
export default function ChartImpl({ spec }: ChartImplProps) {
  return (
    <div data-testid="vega-chart">
      <VegaLite spec={spec as VisualizationSpec} actions={false} />
    </div>
  )
}
