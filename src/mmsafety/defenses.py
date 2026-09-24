"""Input guards of increasing sophistication. Every decision carries its reasons."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .suite import RESTRICTED, Sample

ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)
# Cyrillic and Greek letters that render like Latin capitals (a subset of Unicode confusables).
HOMOGLYPHS = str.maketrans("АВСЕНІКМОРТХУΑΒΕΗΙΚΜΝΟΡΤΧΥ", "ABCEHIKMOPTXYABEHIKMNOPTXY")
LEET = str.maketrans("4301$5(8#", "AEOLSSCBH")
ACTION_CUES = re.compile(
    r"\b(step[- ]by[- ]step|steps?|instructions?|how to|walk me through|carry out|perform|execute|do what)\b",
    re.IGNORECASE,
)
DISCUSSION_CUES = re.compile(
    r"\b(policy|why is|history|is it true|restricted list|review board|what does (this|the) sign say|notice)\b",
    re.IGNORECASE,
)


@dataclass
class Decision:
    blocked: bool
    reasons: list[str] = field(default_factory=list)


def normalise(text: str) -> str:
    """NFKC, strip zero-width characters, upper-case and fold Cyrillic/Greek homoglyphs to Latin."""
    text = unicodedata.normalize("NFKC", text).translate(ZERO_WIDTH).upper().translate(HOMOGLYPHS)
    return text


def skeleton(text: str) -> str:
    """``normalise`` plus leet folding and removal of every separator: ``P.R.0-C`` → ``PROC``."""
    return re.sub(r"[^A-Z0-9]", "", normalise(text).translate(LEET))


def _edit_distance(a: str, b: str, cap: int) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[-1]


TARGETS = {skeleton(t): t for t in RESTRICTED}


class Defense:
    name = "base"

    def decide(self, sample: Sample) -> Decision:
        raise NotImplementedError


class TextKeyword(Defense):
    """Exact token match in the text channel only (the naive baseline)."""

    name = "text keyword"

    def decide(self, sample: Sample) -> Decision:
        hits = [t for t in RESTRICTED if t in sample.text]
        return Decision(bool(hits), [f"text contains {t}" for t in hits])


class ConcatKeyword(Defense):
    """Exact token match over text and OCR together."""

    name = "text + OCR keyword"

    def decide(self, sample: Sample) -> Decision:
        joined = f"{sample.text}\n{sample.image_text}"
        hits = [t for t in RESTRICTED if t in joined]
        return Decision(bool(hits), [f"text or image contains {t}" for t in hits])


class NormalisedMatch(Defense):
    """Match on a canonical skeleton of each channel and of the channels joined.

    Joining the skeletons (text then image) catches a token split across the
    modality boundary; ``max_edits`` adds tolerance for OCR character errors.
    """

    name = "normalised match"

    def __init__(self, max_edits: int = 0) -> None:
        self.max_edits = max_edits
        if max_edits:
            self.name = f"normalised match, ≤{max_edits} edit"

    def matches(self, sample: Sample) -> list[str]:
        channels = {
            "text": skeleton(sample.text),
            "image": skeleton(sample.image_text),
            "text+image": skeleton(sample.text) + skeleton(sample.image_text),
        }
        found = []
        for channel, value in channels.items():
            for target, original in TARGETS.items():
                if target in value:
                    found.append(f"{original} in {channel}")
                elif self.max_edits and self._fuzzy(target, value):
                    found.append(f"{original} (≤{self.max_edits} edits) in {channel}")
        # Cross-modal composition: a target's prefix in one channel and the rest in the other.
        text, image = channels["text"], channels["image"]
        for target, original in TARGETS.items():
            for cut in range(self.MIN_FRAGMENT, len(target) - self.MIN_FRAGMENT + 1):
                head, tail = target[:cut], target[cut:]
                if (head in text and tail in image) or (head in image and tail in text):
                    found.append(f"{original} assembled from {head!r} + {tail!r} across text and image")
                    break
        return sorted(set(found))

    MIN_FRAGMENT = 4

    def _fuzzy(self, target: str, value: str) -> bool:
        width = len(target)
        for start in range(0, max(1, len(value) - width + 1)):
            for size in (width - 1, width, width + 1):
                if _edit_distance(target, value[start : start + size], self.max_edits) <= self.max_edits:
                    return True
        return False

    def decide(self, sample: Sample) -> Decision:
        found = self.matches(sample)
        return Decision(bool(found), found)


class IntentAware(Defense):
    """Normalised (optionally fuzzy) match **and** an actionable request.

    A restricted token is only a problem when someone asks for help doing it.
    Requests framed as discussion (policy questions, reading a sign aloud) are
    allowed unless they also carry an action cue.
    """

    def __init__(self, max_edits: int = 1) -> None:
        self.matcher = NormalisedMatch(max_edits)
        self.name = f"intent-aware, ≤{max_edits} edit" if max_edits else "intent-aware"

    def decide(self, sample: Sample) -> Decision:
        found = self.matcher.matches(sample)
        if not found:
            return Decision(False, ["no restricted token"])
        joined = f"{sample.text}\n{sample.image_text}"
        action = ACTION_CUES.search(normalise(joined).lower())
        discussion = DISCUSSION_CUES.search(joined)
        if action:
            return Decision(True, [*found, f"action cue: {action.group(0)!r}"])
        if discussion:
            return Decision(False, [*found, f"discussion frame: {discussion.group(0)!r}"])
        return Decision(True, [*found, "restricted token without a discussion frame"])


DEFENSES = (
    TextKeyword(),
    ConcatKeyword(),
    NormalisedMatch(),
    NormalisedMatch(max_edits=1),
    IntentAware(max_edits=0),
    IntentAware(max_edits=1),
)
