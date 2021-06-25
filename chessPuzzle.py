import io
import os

import chess.pgn
from chessGame import Game

class PuzzleManager:
    def __init__(self, app):
        self.app = app
        self.puzzles = []        

    def load_puzzles(self, filename):
        with open(filename, 'r') as f:
            context = f.readlines()
            i = 0
            while i < len(context):
                line = context[i]
                if len(line.strip()) == 0:
                    i += 1
                else:
                    self.puzzles.append([context[i].strip(), context[i+1].strip(), context[i+2].strip()])
                    i += 3

    def prepare_play_puzzle(self, event, fen, moves, progress_str):
        pgn = """
[Event "%s"]
[Site ""]
[Date ""]
[Round ""]
[White ""]
[Black "Black"]
[Result ""]
[SetUp "1"]
[FEN "%s"]

%s
        """ % (event, fen, moves)
        items = event.split(" ")
        self.app.interface.window['puzzle_title'].Update("Puzzle %s %s" \
            % (items[0], progress_str))
        self.app.interface.window['puzzle_instruction'].Update(" ".join(items[1:]))
        return Puzzle(self.app, self.app.interface, {}, pgn)

    def play_puzzle(self, puzzle_count):
        if len(self.puzzles) == 0:
            puzzle_file = os.path.join(os.getcwd(), "data\\polgar_5334.dat")
            self.load_puzzles(puzzle_file)

        puzzle_finished = int(self.app.user.config['Polgar5334']['Puzzle_Finished'])
        id = puzzle_finished
        while id < puzzle_finished + puzzle_count:
            p = self.prepare_play_puzzle(self.puzzles[id][0], self.puzzles[id][1], self.puzzles[id][2], \
                "(%d/%d)" % (id - puzzle_finished + 1, puzzle_count))
            ret = p.run()
            if p.rank != "":    # user completes the puzzle
                self.app.user.add_activity("Polgar5334", id, p.rank)
                id += 1
            self.app.user.config['Polgar5334']['Puzzle_Finished'] = str(id)
            if ret == False:    # user exits the app
                self.app.user.save_files()
                return False
        self.app.user.save_files()
        return True

    def review_puzzles(self, review_items):
        print(review_items)
        if len(self.puzzles) == 0:
            puzzle_file = os.path.join(os.getcwd(), "data\\polgar_5334.dat")
            self.load_puzzles(puzzle_file)

        puzzle_count = len(review_items)
        for i, item in enumerate(review_items):
            id = int(item[1])
            p = self.prepare_play_puzzle(self.puzzles[id][0], self.puzzles[id][1], self.puzzles[id][2], \
                "(%d/%d)" % (i + 1, puzzle_count))
            ret = p.run()
            if p.rank != "":    # user completes the puzzle
                self.app.user.add_activity("Polgar5334", id, p.rank)
            if ret == False:    # user exits the app
                self.app.user.save_files()
                return False
        self.app.user.save_files()
        return True

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
        self.rank = ""        
        self.ui.window['puzzle_comment'].Update("")
        self.ui.window['puzzle_moves'].update(values=self.moves)
        self.ui.window['puzzle_next'].update(disabled=True)
        self.fen_to_psg_board(self.game.headers["FEN"])     

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
            self.rank = ranks[3 if self.performance[1] > 3 else self.performance[1]]
            self.ui.window["puzzle_comment"].Update("%s-Rank Cleared" % self.rank, text_color='green')
            self.ui.window['puzzle_next'].update(disabled=False)
            while True:
                button, value = self.ui.window.Read(timeout=100)

                if button is None:
                    self.is_exit_app = True
                    break
                if button == "puzzle_next":
                    break
                elif button == "back_to_main":
                    return True
        return not self.is_exit_app