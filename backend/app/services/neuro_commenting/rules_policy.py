from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import NeuroCommentTarget
from app.services.neuro_commenting.channel_rules_service import ChannelRulesService
from app.services.neuro_commenting.enums import NeuroTargetStatus


@dataclass(frozen=True)
class ChannelRuleDecision:
    allowed: bool
    reason: str | None
    matched_rule_id: str | None = None


class ChannelRulesPolicy:
    def __init__(self, service: ChannelRulesService | None = None) -> None:
        self._service = service or ChannelRulesService()

    def check_target_allowed(
        self,
        session: Session,
        *,
        workspace_id: str,
        target: NeuroCommentTarget,
        whitelist_required: bool = False,
    ) -> ChannelRuleDecision:
        if target.status == NeuroTargetStatus.PAUSED.value:
            return ChannelRuleDecision(False, "target_paused")
        if target.status != NeuroTargetStatus.ACTIVE.value:
            return ChannelRuleDecision(False, "target_not_active")
        rule = self._service.find_rule(
            session, workspace_id=workspace_id, target_ref=target.channel_ref
        )
        if rule is not None and rule.rule_type == "blacklist":
            return ChannelRuleDecision(False, "blacklisted", rule.id)
        if whitelist_required and (rule is None or rule.rule_type != "whitelist"):
            return ChannelRuleDecision(False, "whitelist_required")
        return ChannelRuleDecision(True, None, rule.id if rule is not None else None)
