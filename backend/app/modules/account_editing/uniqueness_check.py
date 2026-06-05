from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Account, AccountProfileState, Asset


WARNING_THRESHOLD = 0.80
BLOCKING_THRESHOLD = 0.95


@dataclass(frozen=True)
class ProfileSimilarityMatch:
    account: Account
    score: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ProfileUniquenessResult:
    severity: str
    matches: tuple[ProfileSimilarityMatch, ...]

    @property
    def max_score(self) -> float:
        return max((match.score for match in self.matches), default=0.0)

    @property
    def similar_count(self) -> int:
        return len(self.matches)

    @property
    def blocking_count(self) -> int:
        return sum(1 for match in self.matches if match.score >= BLOCKING_THRESHOLD)


def compute_bio_similarity(bio_a: str, bio_b: str) -> float:
    left = _normalize_text(bio_a)
    right = _normalize_text(bio_b)
    if not left or not right:
        return 0.0
    levenshtein = 1.0 - (_levenshtein_distance(left, right) / max(len(left), len(right)))
    return round(max(levenshtein, _token_jaccard(left, right)), 3)


def compute_photo_similarity(photo_hash_a: str | None, photo_hash_b: str | None) -> float:
    left = _normalize_hex_hash(photo_hash_a)
    right = _normalize_hex_hash(photo_hash_b)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    if len(left) != len(right):
        return 0.0
    total_bits = len(left) * 4
    distance = sum(
        (int(a, 16) ^ int(b, 16)).bit_count() for a, b in zip(left, right, strict=True)
    )
    return round(1.0 - distance / total_bits, 3)


def compute_bio_hash(bio: str | None) -> str | None:
    normalized = _normalize_text(bio or "")
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_photo_perceptual_hash(asset: Asset | None, *, path: str | None = None) -> str | None:
    if asset is None and not path:
        return None
    image_path = path or (asset.normalized_path if asset is not None else None)
    if image_path:
        dhash = _dhash_from_path(image_path)
        if dhash:
            return dhash
    return _normalize_hex_hash(asset.content_hash if asset is not None else None)


def compute_photo_perceptual_hash_from_bytes(content: bytes) -> str | None:
    if not content:
        return None
    with tempfile.TemporaryDirectory(prefix="stylisttg-profile-uniqueness-") as temp_dir:
        image_path = Path(temp_dir) / "profile_photo"
        image_path.write_bytes(content)
        dhash = _dhash_from_path(str(image_path))
        if dhash:
            return dhash
    return hashlib.sha256(content).hexdigest()


def find_similar_profiles(
    session: Session,
    workspace_id: str,
    *,
    bio: str | None,
    photo_hash: str | None,
    first_name: str | None = None,
    last_name: str | None = None,
    exclude_account_id: str | None = None,
    threshold: float = WARNING_THRESHOLD,
) -> list[Account]:
    return [
        match.account
        for match in evaluate_profile_uniqueness(
            session,
            workspace_id=workspace_id,
            bio=bio,
            photo_hash=photo_hash,
            first_name=first_name,
            last_name=last_name,
            exclude_account_id=exclude_account_id,
            threshold=threshold,
        ).matches
    ]


def evaluate_profile_uniqueness(
    session: Session,
    *,
    workspace_id: str,
    bio: str | None,
    photo_hash: str | None,
    first_name: str | None = None,
    last_name: str | None = None,
    exclude_account_id: str | None = None,
    threshold: float = WARNING_THRESHOLD,
) -> ProfileUniquenessResult:
    query = (
        select(Account)
        .where(Account.workspace_id == workspace_id)
        .options(joinedload(Account.profile_state))
    )
    if exclude_account_id:
        query = query.where(Account.id != exclude_account_id)

    matches: list[ProfileSimilarityMatch] = []
    for account in session.execute(query).scalars().unique():
        profile = account.profile_state
        if profile is None:
            continue
        reasons, score = _profile_score(
            session,
            profile=profile,
            bio=bio,
            photo_hash=photo_hash,
            first_name=first_name,
            last_name=last_name,
        )
        if score >= threshold:
            matches.append(ProfileSimilarityMatch(account=account, score=score, reasons=tuple(reasons)))

    matches.sort(key=lambda item: item.score, reverse=True)
    severity = "blocked" if any(item.score >= BLOCKING_THRESHOLD for item in matches) else "ok"
    if severity == "ok" and matches:
        severity = "warning"
    return ProfileUniquenessResult(severity=severity, matches=tuple(matches))


def _profile_score(
    session: Session,
    *,
    profile: AccountProfileState,
    bio: str | None,
    photo_hash: str | None,
    first_name: str | None,
    last_name: str | None,
) -> tuple[list[str], float]:
    scores: list[tuple[str, float]] = []
    bio_score = compute_bio_similarity(bio or "", profile.bio or "")
    if bio_score > 0:
        scores.append(("bio", bio_score))

    existing_photo_hash = profile.photo_perceptual_hash or _profile_photo_hash(session, profile)
    photo_score = compute_photo_similarity(photo_hash, existing_photo_hash)
    if photo_score > 0:
        scores.append(("photo", photo_score))

    name_score = _name_similarity(first_name, last_name, profile.first_name, profile.last_name)
    if name_score > 0:
        scores.append(("name", name_score))

    if not scores:
        return [], 0.0
    reasons = [reason for reason, score in scores if score >= WARNING_THRESHOLD]
    return reasons, max(score for _, score in scores)


def _profile_photo_hash(session: Session, profile: AccountProfileState) -> str | None:
    if not profile.profile_photo_asset_id:
        return None
    asset = session.get(Asset, profile.profile_photo_asset_id)
    return compute_photo_perceptual_hash(asset)


def _name_similarity(
    first_name_a: str | None,
    last_name_a: str | None,
    first_name_b: str | None,
    last_name_b: str | None,
) -> float:
    left = _normalize_text(" ".join(part for part in [first_name_a, last_name_a] if part))
    right = _normalize_text(" ".join(part for part in [first_name_b, last_name_b] if part))
    return 1.0 if left and left == right else 0.0


def _normalize_text(value: str) -> str:
    return " ".join(value.casefold().strip().split())


def _normalize_hex_hash(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized or any(char not in "0123456789abcdef" for char in normalized):
        return None
    return normalized


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[j - 1] + 1,
                    previous[j] + 1,
                    previous[j - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def _dhash_from_path(value: str) -> str | None:
    path = Path(value)
    if not path.exists():
        return None
    try:
        from PIL import Image

        image = Image.open(path).convert("L").resize((9, 8))
        pixels = list(image.getdata())
    except Exception:
        return None

    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            bits = (bits << 1) | int(left > right)
    return f"{bits:016x}"


def profile_uniqueness_payload(result: ProfileUniquenessResult) -> dict[str, Any]:
    return {
        "severity": result.severity,
        "similar_count": result.similar_count,
        "blocking_count": result.blocking_count,
        "max_score": round(result.max_score, 3),
        "matches": [
            {
                "account_id": match.account.id,
                "score": round(match.score, 3),
                "reasons": list(match.reasons),
            }
            for match in result.matches[:20]
        ],
    }
