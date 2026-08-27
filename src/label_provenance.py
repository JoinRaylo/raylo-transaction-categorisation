"""Truthful label-origin vocabulary.

`human_reviewed` is only for a named human (Carlos, in this repo). Agent
consensus, tiebreak, and review packs are weak supervision and must not share
that name. Dictionary ingest and classifier training may still use the agent
tiers — they are not ground truth.
"""

HUMAN_REVIEWED = "human_reviewed"
AGENT_CONSENSUS = "agent_consensus"
AGENT_TIEBREAK = "agent_tiebreak"
AGENT_REVIEW = "agent_review"

DICTIONARY_ELIGIBLE_TIERS = frozenset({
    "auto_accept",
    "accepted",
    HUMAN_REVIEWED,
    AGENT_CONSENSUS,
    AGENT_TIEBREAK,
    AGENT_REVIEW,
})

CARLOS_REVIEWER_ID = "carlos"


def truthful_tier(tier: str, resolution_source: str) -> str:
    """Map a falsely-named human_reviewed row onto its real origin."""
    if tier != HUMAN_REVIEWED:
        return tier
    src = (resolution_source or "").strip()
    if src == CARLOS_REVIEWER_ID:
        return HUMAN_REVIEWED
    if "consensus" in src:
        return AGENT_CONSENSUS
    if "tiebreak" in src:
        return AGENT_TIEBREAK
    return AGENT_REVIEW


def reviewer_id_for(tier: str, resolution_source: str) -> str:
    if truthful_tier(tier, resolution_source) == HUMAN_REVIEWED:
        return CARLOS_REVIEWER_ID
    return ""
