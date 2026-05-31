import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, test } from 'vitest'

import { Badge, Button, Card, EmptyState, Input, PageHeader, Skeleton, StatusCard, StatusPill } from './index'

describe('@stylisttg/ui primitives', () => {
  test('render shared dashboard primitives', () => {
    const html = renderToStaticMarkup(
      <div>
        <PageHeader title="Accounts" description="Workspace accounts" />
        <Button>Save</Button>
        <Badge tone="success">ok</Badge>
        <Card>panel</Card>
        <Input aria-label="name" defaultValue="Ada" />
        <Skeleton className="h-4" />
        <StatusCard title="Runtime" value="online" />
        <StatusPill tone="ok">ready</StatusPill>
        <EmptyState title="No rows" />
      </div>,
    )

    expect(html).toContain('Accounts')
    expect(html).toContain('Save')
    expect(html).toContain('ready')
  })
})
