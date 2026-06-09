import { Input, Select } from '@stylisttg/ui'
import { Search } from 'lucide-react'

export function AccountFiltersBar({
  countries,
  country,
  hideInWork,
  onCountryChange,
  onHideInWorkChange,
  onProxyOkOnlyChange,
  onRoleChange,
  onSearchChange,
  proxyOkOnly,
  role,
  roles,
  search,
}: {
  countries: string[]
  country: string
  hideInWork: boolean
  onCountryChange: (value: string) => void
  onHideInWorkChange: (value: boolean) => void
  onProxyOkOnlyChange: (value: boolean) => void
  onRoleChange: (value: string) => void
  onSearchChange: (value: string) => void
  proxyOkOnly: boolean
  role: string
  roles: string[]
  search: string
}) {
  return (
    <div className="grid gap-2 border-b border-border px-3 py-3 lg:grid-cols-[minmax(12rem,1fr)_8rem_10rem_auto_auto]">
      <label className="relative grid gap-1">
        <span className="text-xs font-semibold uppercase text-muted-foreground">Поиск</span>
        <Search className="pointer-events-none absolute bottom-2.5 left-2.5 size-4 text-muted-foreground" />
        <Input
          className="pl-8"
          placeholder="ID, телефон, username"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
        />
      </label>
      <label className="grid gap-1">
        <span className="text-xs font-semibold uppercase text-muted-foreground">Страна</span>
        <Select value={country} onChange={(event) => onCountryChange(event.target.value)}>
          <option value="">Все страны</option>
          {countries.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </Select>
      </label>
      <label className="grid gap-1">
        <span className="text-xs font-semibold uppercase text-muted-foreground">Роль</span>
        <Select value={role} onChange={(event) => onRoleChange(event.target.value)}>
          <option value="">Все роли</option>
          {roles.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </Select>
      </label>
      <label className="flex items-end gap-2 pb-2 text-sm text-foreground">
        <input checked={proxyOkOnly} className="size-4" type="checkbox" onChange={(event) => onProxyOkOnlyChange(event.target.checked)} />
        Рабочие прокси
      </label>
      <label className="flex items-end gap-2 pb-2 text-sm text-foreground">
        <input checked={hideInWork} className="size-4" type="checkbox" onChange={(event) => onHideInWorkChange(event.target.checked)} />
        Скрыть в работе
      </label>
    </div>
  )
}
