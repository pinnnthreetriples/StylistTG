from __future__ import annotations

from dataclasses import dataclass

from app.modules.neuro_commenting.enums import NeuroTargetStatus


@dataclass(frozen=True)
class ChannelRuleDecision:
    allowed: bool
    reason: str | None
    matched_rule_id: str | None = None


@dataclass(frozen=True)
class ChannelRuleSnapshot:
    rule_type: str
    rule_id: str


class ChannelRulesPolicy:
    def check_target_allowed(
        self,
        *,
        target_status: str,
        rule: ChannelRuleSnapshot | None = None,
        whitelist_required: bool = False,
    ) -> ChannelRuleDecision:
        if target_status == NeuroTargetStatus.PAUSED.value:
            return ChannelRuleDecision(False, "target_paused")
        if target_status != NeuroTargetStatus.ACTIVE.value:
            return ChannelRuleDecision(False, "target_not_active")
        if rule is not None and rule.rule_type == "blacklist":
            return ChannelRuleDecision(False, "blacklisted", rule.rule_id)
        if whitelist_required and (rule is None or rule.rule_type != "whitelist"):
            return ChannelRuleDecision(False, "whitelist_required")
        return ChannelRuleDecision(True, None, rule.rule_id if rule is not None else None)


__all__ = ["ChannelRuleDecision", "ChannelRuleSnapshot", "ChannelRulesPolicy"]
