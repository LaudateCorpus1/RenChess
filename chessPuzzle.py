import io

import chess.pgn
from chessGame import Game

class Puzzle(Game):
    def __init__(self, app, ui, game_info, pgn, is_white_to_move=True):
        Game.__init__(self, app, ui, game_info, "", is_white_to_move)
        self.player = 'White' if is_white_to_move else 'Black'
        pgn_str = io.StringIO(pgn)
        self.game = chess.pgn.read_game(pgn_str)
        self.board = self.game.board()
        self.ui = ui
        self.moves = []
        self.move_id = -1
        self.performance = [0, 0]   # [good_move, wrong_move]
        self.ui.window['puzzle_title'].Update("Puzzle %s" % self.game.headers["Event"])
        self.ui.window['puzzle_comment'].Update("")
        self.ui.window['puzzle_result'].Update("")
        self.ui.window['puzzle_moves'].update(values=self.moves)
        self.ui.window['puzzle_next'].update(disabled=True)

    def run(self):
        for pgn_move in self.game.mainline_moves():
            pgn_move_san = self.board.san(pgn_move)
            if self.is_exit_app:
                break
            if self.play_side != self.player:
                self.wait(1)
                self.moves[self.move_id][2] = pgn_move_san
                self.ui.window['puzzle_moves'].update(values=self.moves)
                self.update_board(pgn_move)
            else:
                while True:
                    move = self.get_user_input()
                    if self.is_exit_app:
                        break
                    san = self.board.san(move)
                    if san != pgn_move_san:
                        self.performance[1] += 1
                        self.ui.window['puzzle_comment'].Update("%s  Wrong move!" % san, text_color='red')
                        self.update_board(move, clear_move=True)
                    else:
                        self.performance[0] += 1
                        self.ui.window['puzzle_comment'].Update("%s  Good move!" % san, text_color='green')
                        self.move_id += 1
                        self.moves.append([str(self.move_id + 1), "", ""])                        
                        self.moves[self.move_id][1] = san
                        self.ui.window['puzzle_moves'].update(values=self.moves)                        
                        self.update_board(move)
                        break
            self.play_side = 'White' if self.play_side == 'Black' else 'Black'
        if not self.is_exit_app:
            ranks = ["S", "A", "B", "C"]
            rank = ranks[3 if self.performance[1] > 3 else self.performance[1]]
            self.ui.window["puzzle_result"].Update("%s-Rank Cleared" % rank, text_color='green')
            self.ui.window['puzzle_next'].update(disabled=False)
            while True:
                button, value = self.ui.window.Read(timeout=100)

                if button is None:
                    self.is_exit_app = True
                    break
                if button == "puzzle_next":
                    break
        return not self.is_exit_app