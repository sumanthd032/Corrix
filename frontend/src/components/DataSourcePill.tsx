import { Cable, Database, Radio } from 'lucide-react'
import { Tooltip } from './Tooltip'

/**
 * Honest data-source labeling for the Live Command Center, per
 * CORRIX_REAL_DATA_BUILD_PLAN.md Step 23 and CORRIX_REAL_DATA.md §3.4:
 * every screen showing live-factory data says, permanently and without
 * a way to dismiss it, exactly what's feeding it, including that the
 * device is simulated where applicable. Matches ConnectionPill.tsx's
 * small bordered eyebrow-pill pattern for visual consistency, not the
 * same component: ConnectionPill reads the global live/offline
 * connection state, this reads a specific factory's own data_source.
 */

type DataSource = 'csv' | 'mqtt' | 'opcua'

const LABELS: Record<DataSource, { text: string; hint: string; Icon: typeof Database }> = {
  csv: {
    text: 'LIVE FACTORY DATA · UPLOADED CSV',
    hint: 'Streaming from a real uploaded historian CSV, replayed in chronological order. No simulated device involved.',
    Icon: Database,
  },
  mqtt: {
    text: 'LIVE FACTORY DATA · SIMULATED DEVICE (MQTT)',
    hint: 'A real MQTT broker and protocol carry every message. The device publishing to it is a simulated virtual sensor, not physical hardware.',
    Icon: Radio,
  },
  opcua: {
    text: 'LIVE FACTORY DATA · SIMULATED DEVICE (OPC-UA)',
    hint: 'A real OPC-UA server and protocol carry every message. The device behind it is simulated, not physical hardware.',
    Icon: Cable,
  },
}

export function DataSourcePill({ dataSource }: { dataSource: DataSource }) {
  const { text, hint, Icon } = LABELS[dataSource]
  return (
    <Tooltip label="Data source" hint={hint}>
      <span
        className="flex items-center gap-1.5 rounded-[var(--radius-sharp)] border px-2 py-1 eyebrow"
        style={{ borderColor: 'var(--color-hairline-strong)', color: 'var(--color-text-secondary)' }}
      >
        <Icon size={12} aria-hidden="true" />
        {text}
      </span>
    </Tooltip>
  )
}
