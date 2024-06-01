class VictoryDrawResult:
    DRAW = 'D'
    
    WINNER = 'W'
    LOSER = 'L'
    
    @classmethod
    def get_win_lose_list(cls, player_count, *winner_indices):
        l = [cls.LOSER]*player_count
        for w in winner_indices:
            l[w] = cls.WINNER
        
        return l
