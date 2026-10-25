"""Inference interface. A backend maps chat messages plus decoding parameters to text.

Backends receive :class:`GenRequest` objects only: rendered messages and decoding settings.
No case id, follow-up id, contrast class or label crosses this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..schema import Completion, GenParams, Message


@dataclass(frozen=True)
class GenRequest:
    messages: tuple[Message, ...]
    gen: GenParams


class Backend(Protocol):
    #: Short label stored with every row, e.g. ``fake:visible_random`` or ``hf:<model>@<rev>``.
    label: str
    #: True for synthetic/fake backends (no model inference).
    synthetic: bool
    #: True only for privileged control policies that read gold labels (upper bounds/tests).
    privileged: bool

    def info(self) -> dict[str, Any]: ...

    def generate(self, requests: list[GenRequest]) -> list[Completion]: ...
