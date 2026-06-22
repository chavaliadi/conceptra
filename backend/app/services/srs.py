from datetime import datetime, timedelta

def calculate_next_review(
    rating: int,
    current_repetitions: int,
    current_ease_factor: float,
    current_interval_days: int
) -> tuple[int, float, int, datetime]:
    """
    Implements the SM-2 spaced repetition algorithm.
    - rating: quality of response, between 1 and 5 (1 is forgot completely, 5 is perfect response)
    - current_repetitions: number of times reviewed in a row
    - current_ease_factor: difficulty factor (default 2.5)
    - current_interval_days: days between current review and next review
    
    Returns:
        (new_repetitions, new_ease_factor, new_interval_days, next_review_at)
    """
    if rating < 3:
        # Repetition failed; restart interval and repetitions
        new_repetitions = 0
        new_interval_days = 1
        new_ease_factor = current_ease_factor
    else:
        # Repetition succeeded
        if current_repetitions == 0:
            new_interval_days = 1
        elif current_repetitions == 1:
            new_interval_days = 6
        else:
            new_interval_days = max(1, round(current_interval_days * current_ease_factor))
            
        new_repetitions = current_repetitions + 1
        
        # Calculate new ease factor: EF' = EF + (0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02))
        new_ease_factor = current_ease_factor + (0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02))
        if new_ease_factor < 1.3:
            new_ease_factor = 1.3
            
    next_review_at = datetime.now() + timedelta(days=new_interval_days)
    return new_repetitions, new_ease_factor, new_interval_days, next_review_at
