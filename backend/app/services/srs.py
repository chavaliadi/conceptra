"""
Spaced Repetition System (SRS) module.

NOTE: All SM-2 mathematics and scheduling logic have been consolidated into
`app.services.scheduler` as the single authoritative source of truth.
This module re-exports functions for backward compatibility.
"""

from app.services.scheduler import calculate_next_review, update_sm2

__all__ = ["calculate_next_review", "update_sm2"]

