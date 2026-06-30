from datetime import datetime, timedelta, timezone
import math

def calculate_blended_quality(is_correct: bool, confidence: float) -> int:
    """
    Blends quiz correctness and self-reported confidence into a 0-5 SM-2 quality score.
    - Correct + High Conf (>= 0.7) -> 5
    - Correct + Med Conf (0.3 - 0.7) -> 4
    - Correct + Low Conf (< 0.3) -> 3
    - Incorrect + Low Conf (< 0.3) -> 2
    - Incorrect + Med Conf (0.3 - 0.7) -> 1
    - Incorrect + High Conf (>= 0.7) -> 0 (Complete blackout/false confidence - strongest drop)
    """
    if is_correct:
        if confidence >= 0.7:
            return 5
        elif confidence >= 0.3:
            return 4
        else:
            return 3
    else:
        if confidence < 0.3:
            return 2
        elif confidence < 0.7:
            return 1
        else:
            return 0

def update_sm2(
    repetitions: int,
    ease_factor: float,
    interval_days: int,
    quality: int
) -> tuple[int, float, int]:
    """
    Classic SM-2 spaced repetition calculation.
    Returns (new_repetitions, new_ease_factor, new_interval_days)
    """
    # Clamp ease factor minimum to 1.3
    ease_factor = max(1.3, ease_factor)
    
    if quality >= 3:
        if repetitions == 0:
            interval_days = 1
        elif repetitions == 1:
            interval_days = 6
        else:
            interval_days = int(math.ceil(interval_days * ease_factor))
        repetitions += 1
    else:
        repetitions = 0
        interval_days = 1
        
    # Adjust ease factor
    ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease_factor = max(1.3, ease_factor)
    
    return repetitions, ease_factor, interval_days

def calculate_mastery_delta(quality: int) -> float:
    """
    Returns the change in mastery percentage based on SM-2 quality.
    """
    if quality == 5:
        return 15.0
    elif quality == 4:
        return 10.0
    elif quality == 3:
        return 5.0
    elif quality == 2:
        return -10.0
    elif quality == 1:
        return -15.0
    else:  # quality == 0
        return -25.0

def calculate_decayed_retention(last_reviewed_at: datetime | None, interval_days: int, current_mastery: float) -> float:
    """
    Exponential retention decay based on time elapsed since last review.
    At 0 days: retention = 100%
    At interval_days: retention = 90%
    Beyond interval_days: retention decays rapidly towards 0%
    """
    if not last_reviewed_at:
        return 0.0
        
    now = datetime.now(timezone.utc)
    # Ensure timezone awareness matches
    if last_reviewed_at.tzinfo is None:
        last_reviewed_at = last_reviewed_at.replace(tzinfo=timezone.utc)
        
    days_elapsed = (now - last_reviewed_at).total_seconds() / 86400.0
    days_elapsed = max(0.0, days_elapsed)
    
    if interval_days <= 0:
        interval_days = 1
        
    # Exponential forgetting curve
    retention = 100.0 * (0.9 ** (days_elapsed / interval_days))
    # Cap at current mastery level to keep it grounded
    return max(0.0, min(retention, current_mastery))
