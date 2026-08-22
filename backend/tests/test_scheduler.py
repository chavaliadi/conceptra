from datetime import datetime, timezone, timedelta
import pytest
from app.services.scheduler import (
    calculate_blended_quality,
    calculate_mastery_delta,
    calculate_decayed_retention,
    update_sm2
)

def test_blended_quality_mapping_all_six_cases():
    """Verify all 6 bins of confidence + correctness mapping."""
    # 1. Correct + High Conf -> 5
    assert calculate_blended_quality(is_correct=True, confidence=0.9) == 5
    assert calculate_blended_quality(is_correct=True, confidence=0.7) == 5

    # 2. Correct + Med Conf -> 4
    assert calculate_blended_quality(is_correct=True, confidence=0.5) == 4
    assert calculate_blended_quality(is_correct=True, confidence=0.3) == 4

    # 3. Correct + Low Conf -> 3
    assert calculate_blended_quality(is_correct=True, confidence=0.2) == 3
    assert calculate_blended_quality(is_correct=True, confidence=0.0) == 3

    # 4. Incorrect + Low Conf -> 2
    assert calculate_blended_quality(is_correct=False, confidence=0.1) == 2
    assert calculate_blended_quality(is_correct=False, confidence=0.29) == 2

    # 5. Incorrect + Med Conf -> 1
    assert calculate_blended_quality(is_correct=False, confidence=0.3) == 1
    assert calculate_blended_quality(is_correct=False, confidence=0.69) == 1

    # 6. Incorrect + High Conf -> 0
    assert calculate_blended_quality(is_correct=False, confidence=0.7) == 0
    assert calculate_blended_quality(is_correct=False, confidence=1.0) == 0

def test_mastery_delta_values():
    """Verify mastery delta per SM-2 quality level."""
    assert calculate_mastery_delta(5) == 15.0
    assert calculate_mastery_delta(4) == 10.0
    assert calculate_mastery_delta(3) == 5.0
    assert calculate_mastery_delta(2) == -10.0
    assert calculate_mastery_delta(1) == -15.0
    assert calculate_mastery_delta(0) == -25.0

def test_decayed_retention_calculation():
    """Verify exponential retention decay against known fixtures."""
    now = datetime.now(timezone.utc)
    
    # 0 days elapsed -> retention equals 100% capped at mastery
    ret_0 = calculate_decayed_retention(now, interval_days=6, current_mastery=80.0)
    assert ret_0 == 80.0

    # Exactly interval_days elapsed -> retention is 100 * 0.9^1 = 90% (capped by mastery)
    past_6d = now - timedelta(days=6)
    ret_6d = calculate_decayed_retention(past_6d, interval_days=6, current_mastery=95.0)
    assert ret_6d == pytest.approx(90.0, abs=1e-1)

    # 12 days elapsed (2 * interval) -> retention is 100 * 0.9^2 = 81%
    past_12d = now - timedelta(days=12)
    ret_12d = calculate_decayed_retention(past_12d, interval_days=6, current_mastery=95.0)
    assert ret_12d == pytest.approx(81.0, abs=1e-1)

    # None last_reviewed_at returns 0.0
    assert calculate_decayed_retention(None, interval_days=6, current_mastery=80.0) == 0.0

def test_confident_incorrect_penalty_integration():
    """Verify that a confident incorrect response causes harsh EF drop and 1-day reset."""
    quality = calculate_blended_quality(is_correct=False, confidence=0.9)  # 0
    reps, new_ef, new_interval = update_sm2(repetitions=3, ease_factor=2.5, interval_days=10, quality=quality)
    
    assert reps == 0
    assert new_interval == 1
    # EF drops by 0.80: 2.50 - 0.80 = 1.70
    assert new_ef == pytest.approx(1.70, abs=1e-2)
