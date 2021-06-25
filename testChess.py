import io
import chess.pgn

pgn = """
[Event "test"]
[Site ""]
[Date ""]
[Round ""]
[White ""]
[Black "Black"]
[Result ""]
[SetUp "1"]
[FEN "3q1rk1/5pbp/5Qp1/8/8/2B5/5PPP/6K1 w - - 0 1"]

1. Qxg7m

"""
pgn_str = io.StringIO(pgn)
game = chess.pgn.read_game(pgn_str)
board = game.board()
for move in game.mainline_moves():
    print(board.san(move))