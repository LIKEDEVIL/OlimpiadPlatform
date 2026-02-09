def calculate_elo(winner_rating, loser_rating, is_draw=False):
    K = 32  # Коэффициент изменения рейтинга

    # Ожидаемый результат для победителя
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))

    actual_score = 0.5 if is_draw else 1.0

    # Новые рейтинги
    new_winner_rating = winner_rating + K * (actual_score - expected_winner)
    new_loser_rating = loser_rating + K * ((1 - actual_score) - (1 - expected_winner))

    return round(new_winner_rating), round(new_loser_rating)
