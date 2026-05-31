from __future__ import annotations

from dataclasses import dataclass, field



_RESERVE_SCRIPT = """
-- reserve_limit_v2
local reservation_key = ARGV[1]
local reservation_payload = ARGV[2]
local reservation_ttl = tonumber(ARGV[3])
local limit_count = tonumber(ARGV[4])
local cursor = 5

if redis.call("EXISTS", reservation_key) == 1 then
  return {0, "reservation_conflict", reservation_ttl}
end

for i = 1, limit_count do
  local key = KEYS[i]
  local name = ARGV[cursor]
  local max_value = tonumber(ARGV[cursor + 1])
  cursor = cursor + 3
  local current = tonumber(redis.call("GET", key) or "0")
  if current >= max_value then
    return {0, name, redis.call("TTL", key)}
  end
end

local min_delay_count = tonumber(ARGV[cursor])
cursor = cursor + 1
for i = 1, min_delay_count do
  local key = KEYS[limit_count + i]
  local name = ARGV[cursor]
  cursor = cursor + 2
  if redis.call("GET", key) then
    return {0, name, redis.call("TTL", key)}
  end
end

cursor = 5
for i = 1, limit_count do
  local key = KEYS[i]
  cursor = cursor + 1
  local window_seconds = tonumber(ARGV[cursor + 1])
  redis.call("INCRBY", key, 1)
  if redis.call("TTL", key) < 0 then
    redis.call("EXPIRE", key, window_seconds)
  end
  cursor = cursor + 2
end

cursor = 5 + (limit_count * 3) + 1
local reserved_min_delay_keys = {}
for i = 1, min_delay_count do
  local key = KEYS[limit_count + i]
  local name = ARGV[cursor]
  local reserve_ttl = tonumber(ARGV[cursor + 1])
  if not redis.call("SET", key, reservation_key, "EX", reserve_ttl, "NX") then
    for j = 1, limit_count do
      redis.call("DECRBY", KEYS[j], 1)
    end
    for _, reserved_key in ipairs(reserved_min_delay_keys) do
      if redis.call("GET", reserved_key) == reservation_key then
        redis.call("DEL", reserved_key)
      end
    end
    return {0, name, redis.call("TTL", key)}
  end
  table.insert(reserved_min_delay_keys, key)
  cursor = cursor + 2
end

if not redis.call("SET", reservation_key, reservation_payload, "EX", reservation_ttl, "NX") then
  for i = 1, limit_count do
    redis.call("DECRBY", KEYS[i], 1)
  end
  for _, reserved_key in ipairs(reserved_min_delay_keys) do
    if redis.call("GET", reserved_key) == reservation_key then
      redis.call("DEL", reserved_key)
    end
  end
  return {0, "reservation_conflict", reservation_ttl}
end

return {1, "", 0}
"""

RATE_LIMIT_COUNTER_SCAN_PATTERN = "neuro:*:limit:*"


@dataclass(frozen=True)
class RateLimitCounterKey:
    workspace_id: str
    scope_type: str
    scope_id: str
    scope_key: str
    window_number: int


def parse_rate_limit_counter_key(key: str) -> RateLimitCounterKey | None:
    parts = key.split(":")
    if len(parts) != 7:
        return None
    if parts[0] != "neuro" or parts[2] != "limit":
        return None
    try:
        window_number = int(parts[6])
    except ValueError:
        return None
    return RateLimitCounterKey(
        workspace_id=parts[1],
        scope_type=parts[3],
        scope_id=parts[4],
        scope_key=parts[5],
        window_number=window_number,
    )


def build_rate_limit_counter_key(
    *,
    workspace_id: str,
    scope_type: str,
    scope_id: str,
    scope_key: str,
    window_number: int,
) -> str:
    return f"neuro:{workspace_id}:limit:{scope_type}:{scope_id}:{scope_key}:{window_number}"


def build_rate_limit_counter_metadata_key(
    *,
    workspace_id: str,
    scope_type: str,
    scope_id: str,
    scope_key: str,
    window_number: int,
) -> str:
    return f"neuro:{workspace_id}:limit_meta:{scope_type}:{scope_id}:{scope_key}:{window_number}"


@dataclass(frozen=True)
class RateLimitScope:
    workspace_id: str
    campaign_id: str
    account_id: str | None
    target_id: str | None
    campaign_account_id: str | None = None
    campaign_target_id: str | None = None


@dataclass(frozen=True)
class RateLimitReservation:
    reservation_id: str | None
    allowed: bool
    reason: str | None = None
    retry_after_seconds: int | None = None
    checked_limits: list[str] = field(default_factory=lambda: [])


