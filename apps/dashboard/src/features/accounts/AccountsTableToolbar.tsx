import { Button, Input, TableToolbar, Tabs, TabsList, TabsTrigger } from '@stylisttg/ui'
import { Search, Play, ShieldAlert, RefreshCw } from 'lucide-react'

export type AccountsView = 'all' | 'ready' | 'high_risk'

export function AccountsTableToolbar({
  globalFilter,
  onGlobalFilterChange,
  activeView,
  onViewChange,
  selectedCount,
}: {
  globalFilter: string
  onGlobalFilterChange: (value: string) => void
  activeView: AccountsView
  onViewChange: (view: AccountsView) => void
  selectedCount: number
}) {
  const unavailableReason =
    selectedCount === 0 ? 'Выберите аккаунты' : 'Будет доступно после подключения безопасного массового действия'

  return (
    <div className="flex flex-col gap-4 mb-4">
      <div className="flex items-center justify-between">
        <Tabs value={activeView} onValueChange={(v) => onViewChange(v as AccountsView)}>
          <TabsList>
            <TabsTrigger value="all">Все аккаунты</TabsTrigger>
            <TabsTrigger value="ready">Готовы к работе</TabsTrigger>
            <TabsTrigger value="high_risk">Высокий риск</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      <TableToolbar
        search={
          <div className="relative">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              className="pl-9 h-9 w-[250px]"
              onChange={(event) => onGlobalFilterChange(event.target.value)}
              placeholder="Поиск аккаунтов..."
              type="text"
              value={globalFilter}
            />
          </div>
        }
        actions={
          <div className="flex items-center gap-2">
            <Button
              aria-label={`Обновить риск. ${unavailableReason}`}
              className="h-8 text-xs"
              disabled
              title={unavailableReason}
              variant="secondary"
            >
              <RefreshCw className="size-4 mr-2" />
              Обновить риск
            </Button>
            <Button
              aria-label={`Запустить аудит. ${unavailableReason}`}
              className="h-8 text-xs"
              disabled
              title={unavailableReason}
              variant="secondary"
            >
              <ShieldAlert className="size-4 mr-2" />
              Запустить аудит
            </Button>
            <Button
              aria-label={`Проверить готовность. ${unavailableReason}`}
              className="h-8 text-xs"
              disabled
              title={unavailableReason}
            >
              <Play className="size-4 mr-2" />
              Проверить готовность
            </Button>
            <span className="text-xs text-muted-foreground">{unavailableReason}</span>
          </div>
        }
      />
    </div>
  )
}
