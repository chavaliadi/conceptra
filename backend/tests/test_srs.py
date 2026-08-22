import pytest
from app.services.srs import calculate_next_review
from app.services.scheduler import update_sm2

def test_srs_interval_progression():
    """Verify that interval progression follows 1 day -> 6 days -> ceil(interval * ease_factor)."""
    # Repetition 0 (First successful review)
    reps1, ef1, int1 = update_sm2(repetitions=0, ease_factor=2.5, interval_days=0, quality=5)
    assert reps1 == 1
    assert int1 == 1
    assert ef1 == pytest.approx(2.60, abs=1e-2)

    # Repetition 1 (Second successful review)
    reps2, ef2, int2 = update_sm2(repetitions=reps1, ease_factor=ef1, interval_days=int1, quality=5)
    assert reps2 == 2
    assert int2 == 6
    assert ef2 == pytest.approx(2.70, abs=1e-2)

    # Repetition 2 (Third successful review -> 6 * 2.7 = 16.2 -> ceil 17)
    reps3, ef3, int3 = update_sm2(repetitions=reps2, ease_factor=ef2, interval_days=int2, quality=5)
    assert reps3 == 3
    assert int3 == 17
    assert ef3 == pytest.approx(2.80, abs=1e-2)

def test_srs_ease_factor_floor():
    """Verify that ease factor cannot drop below 1.3 even after multiple failed reviews."""
    # Quality 0 causes maximum EF drop (-0.80)
    reps, ef, interval = update_sm2(repetitions=5, ease_factor=1.35, interval_days=20, quality=0)
    assert reps == 0
    assert interval == 1
    assert ef == 1.3

    # Starting already at 1.3 should remain clamped at 1.3
    reps2, ef2, interval2 = update_sm2(repetitions=0, ease_factor=1.3, interval_days=1, quality=0)
    assert reps2 == 0
    assert interval2 == 1
    assert ef2 == 1.3

def test_calculate_next_review_service():
    """Verify calculate_next_review in srs.py for success and reset behaviors."""
    # Success rating 5
    reps, ef, interval, next_rev = calculate_next_review(
        rating=5, current_repetitions=0, current_ease_factor=2.5, current_interval_days=0
    )
    assert reps == 1
    assert interval == 1
    assert ef == pytest.approx(2.60, abs=1e-2)
    assert next_rev is not None

    # Failed rating < 3 correctly penalizes ease factor (2.5 -> 2.18) and resets reps/interval
    reps_fail, ef_fail, interval_fail, next_rev_fail = calculate_next_review(
        rating=2, current_repetitions=3, current_ease_factor=2.5, current_interval_days=15
    )
    assert reps_fail == 0
    assert interval_fail == 1
    assert ef_fail == pytest.approx(2.18, abs=1e-2)
    assert next_rev_fail is not None
