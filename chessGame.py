import io
import copy
import time
import chess
import chess.pgn

from globals import *

class Game:
    def __init__(self, app, ui, game_info, fen='', is_white_to_move=True):
        self.game = chess.pgn.Game()
        self.app = app
        self.ui = ui
        self.board = chess.Board() if len(fen) == 0 else chess.Board(fen)
        self.play_side = 'White' if is_white_to_move else 'Black'
        self.move_cnt = 0
        self.is_exit_app = False
        self.is_user_resigns = False
        self.is_user_wins = False
        self.is_user_draws = False
        if 'White' in game_info:
            self.game.headers['White'] = game_info['White']            
        if 'Black' in game_info:
            self.game.headers['Black'] = game_info['Black']
        if 'Event' in game_info:
            self.game.headers['Event'] = game_info['Event']
        if 'Date' in game_info:
            self.game.headers['Date'] = game_info['Date']

    def run(self):
        while not self.board.is_game_over(claim_draw=True):
            if self.game.headers[self.play_side] == '@Engine':
                self.get_engine_move()
            else:
                move = self.get_user_input()
                self.update_board(move)
                self.move_cnt += 1
            self.play_side = 'White' if self.play_side == 'Black' else 'Black'
            if self.is_exit_app:
                break
        return not self.is_exit_app

    def get_row(self, s):
        """
        This row is based on PySimpleGUI square mapping that is 0 at the
        top and 7 at the bottom.
        In contrast Python-chess square mapping is 0 at the bottom and 7
        at the top. chess.square_rank() is a method from Python-chess that
        returns row given square s.

        :param s: square
        :return: row
        """
        return 7 - chess.square_rank(s)

    def get_col(self, s):
        """ Returns col given square s """
        return chess.square_file(s)

    def relative_row(self, s, stm):
        """
        The board can be viewed, as white at the bottom and black at the
        top. If stm is white the row 0 is at the bottom. If stm is black
        row 0 is at the top.
        :param s: square
        :param stm: side to move
        :return: relative row
        """
        return 7 - self.get_row(s) if stm else self.get_row(s)

    def update_ep(self, move, stm):
        """
        Update board for e.p move.

        :param window:
        :param move: python-chess format
        :param stm: side to move
        :return:
        """
        to = move.to_square
        if stm:
            capture_sq = to - 8
        else:
            capture_sq = to + 8

        self.app.psg_board[self.get_row(capture_sq)][self.get_col(capture_sq)] = BLANK
        self.ui.redraw_board()

    def update_rook(self, move):
        """
        Update rook location for castle move.

        :param window:
        :param move: uci move format
        :return:
        """
        if move == 'e1g1':
            fr = chess.H1
            to = chess.F1
            pc = ROOKW
        elif move == 'e1c1':
            fr = chess.A1
            to = chess.D1
            pc = ROOKW
        elif move == 'e8g8':
            fr = chess.H8
            to = chess.F8
            pc = ROOKB
        elif move == 'e8c8':
            fr = chess.A8
            to = chess.D8
            pc = ROOKB

        self.app.psg_board[self.get_row(fr)][self.get_col(fr)] = BLANK
        self.app.psg_board[self.get_row(to)][self.get_col(to)] = pc
        self.ui.redraw_board()

    def get_promo_piece(self, move, stm, human):
        """
        Returns promotion piece.

        :param move: python-chess format
        :param stm: side to move
        :param human: if side to move is human this is True
        :return: promoted piece in python-chess and pythonsimplegui formats
        """
        # If this move is from a user, we will show a window with piece images
        if human:
            psg_promo = self.ui.select_promotion_piece(stm)

            # If user pressed x we set the promo to queen
            if psg_promo is None:
                logging.info('User did not select a promotion piece, '
                             'set this to queen.')
                psg_promo = QUEENW if stm else QUEENB

            pyc_promo = promote_psg_to_pyc[psg_promo]
        # Else if move is from computer
        else:
            pyc_promo = move.promotion  # This is from python-chess           

        return pyc_promo

    def pyc_to_psg(self, pyc, stm):
        if stm:
            if pyc == chess.QUEEN:
                psg = QUEENW
            elif pyc == chess.ROOK:
                psg = ROOKW
            elif pyc == chess.BISHOP:
                psg = BISHOPW
            elif pyc == chess.KNIGHT:
                psg = KNIGHTW
        else:
            if pyc == chess.QUEEN:
                psg = QUEENB
            elif pyc == chess.ROOK:
                psg = ROOKB
            elif pyc == chess.BISHOP:
                psg = BISHOPB
            elif pyc == chess.KNIGHT:
                psg = KNIGHTB
        return psg
    
    def get_user_input(self):
        move_state = 0
        window = self.ui.window
        while True:
            button, value = window.Read(timeout=100)

            if button is None:
                logging.info('Quit app X is pressed.')
                self.is_exit_app = True
                break

            if type(button) is tuple:
                # If fr_sq button is pressed
                if move_state == 0:
                    move_from = button
                    fr_row, fr_col = move_from

                    # Change the color of the "fr" board square
                    self.ui.change_square_color(fr_row, fr_col)

                    move_state = 1
                    moved_piece = self.board.piece_type_at(chess.square(fr_col, 7-fr_row))  # Pawn=1
                    
                # Else if to_sq button is pressed
                elif move_state == 1:
                    is_promote = False
                    move_to = button
                    to_row, to_col = move_to
                    button_square = window.FindElement(key=(fr_row, fr_col))
                    
                    # If move is cancelled, pressing same button twice
                    if move_to == move_from:
                        # Restore the color of the pressed board square
                        color = self.ui.sq_dark_color if (to_row + to_col) % 2 else self.ui.sq_light_color

                        # Restore the color of the fr square
                        button_square.Update(button_color=('white', color))
                        move_state = 0
                        continue

                    # Create a move in python-chess format based from user input
                    user_move = None

                    # Get the fr_sq and to_sq of the move from user, based from this info
                    # we will create a move based from python-chess format.
                    # Note chess.square() and chess.Move() are from python-chess module
                    fr_row, fr_col = move_from
                    fr_sq = chess.square(fr_col, 7-fr_row)
                    to_sq = chess.square(to_col, 7-to_row)

                    # If user move is a promote
                    if self.relative_row(to_sq, self.board.turn) == RANK_8 and \
                            moved_piece == chess.PAWN:
                        is_promote = True
                        pyc_promo, psg_promo = self.get_promo_piece(
                                user_move, self.board.turn, True)
                        user_move = chess.Move(fr_sq, to_sq, promotion=pyc_promo)
                    else:
                        user_move = chess.Move(fr_sq, to_sq)

                    # Check if user move is legal
                    if user_move in self.board.legal_moves:
                        return user_move

                    # Else if move is illegal
                    else:
                        move_state = 0
                        color = self.ui.sq_dark_color \
                            if (move_from[0] + move_from[1]) % 2 else self.ui.sq_light_color

                        # Restore the color of the fr square
                        button_square.Update(button_color=('white', color))
                        continue

    def update_board(self, move, clear_move=False):
        fr_sq, to_sq = move.from_square, move.to_square
        fr_col, fr_row = chess.square_file(fr_sq), 7 - chess.square_rank(fr_sq)
        to_col, to_row = chess.square_file(to_sq), 7 - chess.square_rank(to_sq)
        if  clear_move:
            color = self.ui.sq_dark_color if (fr_row + fr_col) % 2 else self.ui.sq_light_color
            button_square = self.ui.window.FindElement(key=(fr_row, fr_col))
            button_square.Update(button_color=('white', color))
            return

        piece = self.app.psg_board[fr_row][fr_col]  # get the move-from piece

        # Update rook location if this is a castle move
        if self.board.is_castling(move):
            self.update_rook(self.ui.window, str(move))

        # Update board if e.p capture
        elif self.board.is_en_passant(move):
            self.update_ep(move, self.board.turn)

        # Empty the board from_square, applied to any types of move
        self.app.psg_board[fr_row][fr_col] = BLANK

        # Update board to_square if move is a promotion
        if move.promotion:
            self.app.psg_board[to_row][to_col] = self.pyc_to_psg(move.promotion, self.board.turn)
        # Update the to_square if not a promote move
        else:
            # Place piece in the move to_square
            self.app.psg_board[to_row][to_col] = piece

        self.ui.redraw_board()

        self.board.push(move)
        
        # Change the color of the "fr" and "to" board squares
        self.ui.change_square_color(fr_row, fr_col)
        self.ui.change_square_color(to_row, to_col)

    def wait(self, seconds):
        cur_time = time.time()
        while time.time() < cur_time + seconds:
            button, value = self.ui.window.Read(timeout=100)