#!/usr/bin/env python3
""" 
python_easy_chess_gui.py

Requirements:
    Python 3.7.3 and up

PySimpleGUI Square Mapping
board = [
    56, 57, ... 63
    ...
    8, 9, ...
    0, 1, 2, ...
]

row = [
    0, 0, ...
    1, 1, ...
    ...
    7, 7 ...
]

col = [
    0, 1, 2, ... 7
    0, 1, 2, ...
    ...
    0, 1, 2, ... 7
]


Python-Chess Square Mapping
board is the same as in PySimpleGUI
row is reversed
col is the same as in PySimpleGUI

"""

import PySimpleGUI as sg
import subprocess
import threading
from pathlib import Path, PurePath  # Python 3.4 and up
import queue
import copy
import time
from datetime import datetime
import json
import pyperclip
import chess.pgn
import chess.engine
import chess.polyglot

from globals import *
from engine import RunEngine
from interface import RenChessInterface
import chessGame
import chessPuzzle

class Timer:
    def __init__(self, tc_type='fischer', base=300000, inc=10000,
                 period_moves=40):
        """
        :param tc_type: time control type ['fischer, delay, classical']
        :param base: base time in ms
        :param inc: increment time in ms can be negative and 0
        :param period_moves: number of moves in a period
        """
        self.tc_type = tc_type  # ['fischer', 'delay', 'timepermove']
        self.base = base
        self.inc = inc
        self.period_moves = period_moves
        self.elapse = 0
        self.init_base_time = self.base

    def update_base(self):
        """
        Update base time after every move

        :return:
        """
        if self.tc_type == 'delay':
            self.base += min(0, self.inc - self.elapse)
        elif self.tc_type == 'fischer':
            self.base += self.inc - self.elapse
        elif self.tc_type == 'timepermove':
            self.base = self.init_base_time
        else:
            self.base -= self.elapse

        self.base = max(0, self.base)
        self.elapse = 0


class GuiBook:
    def __init__(self, book_file, board, is_random=True):
        """
        Handle gui polyglot book for engine opponent.

        :param book_file: polgylot book filename
        :param board: given board position
        :param is_random: randomly select move from book
        """
        self.book_file = book_file
        self.board = board
        self.is_random = is_random
        self.__book_move = None

    def get_book_move(self):
        """ Returns book move either random or best move """
        reader = chess.polyglot.open_reader(self.book_file)
        try:
            if self.is_random:
                entry = reader.weighted_choice(self.board)
            else:
                entry = reader.find(self.board)
            self.__book_move = entry.move
        except IndexError:
            logging.warning('No more book move.')
        except Exception:
            logging.exception('Failed to get book move.')
        finally:
            reader.close()

        return self.__book_move

    def get_all_moves(self):
        """
        Read polyglot book and get all legal moves from a given positions.

        :return: move string
        """
        is_found = False
        total_score = 0
        book_data = {}
        cnt = 0

        if os.path.isfile(self.book_file):
            moves = '{:4s}   {:<5s}   {}\n'.format('move', 'score', 'weight')
            with chess.polyglot.open_reader(self.book_file) as reader:
                for entry in reader.find_all(self.board):
                    is_found = True
                    san_move = self.board.san(entry.move)
                    score = entry.weight
                    total_score += score
                    bd = {cnt: {'move': san_move, 'score': score}}
                    book_data.update(bd)
                    cnt += 1
        else:
            moves = '{:4s}  {:<}\n'.format('move', 'score')

        # Get weight for each move
        if is_found:
            for _, v in book_data.items():
                move = v['move']
                score = v['score']
                weight = score/total_score
                moves += '{:4s}   {:<5d}   {:<2.1f}%\n'.format(move, score,
                                                            100*weight)

        return moves, is_found


class RenChessApp:
    queue = queue.Queue()
    is_user_white = True  # White is at the bottom in board layout

    def __init__(self, theme, engine_config_file, user_config_file,
                 gui_book_file, computer_book_file, human_book_file,
                 is_use_gui_book, is_random_book, max_book_ply,
                 max_depth=MAX_DEPTH):
        self.theme = theme
        self.user_config_file = user_config_file
        self.engine_config_file = engine_config_file
        self.gui_book_file = gui_book_file
        self.computer_book_file = computer_book_file
        self.human_book_file = human_book_file
        self.max_depth = max_depth
        self.is_use_gui_book = is_use_gui_book
        self.is_random_book = is_random_book
        self.max_book_ply = max_book_ply
        self.opp_path_and_file = None
        self.opp_file = None
        self.opp_id_name = None
        self.adviser_file = None
        self.adviser_path_and_file = None
        self.adviser_id_name = None
        self.adviser_hash = 128
        self.adviser_threads = 1
        self.adviser_movetime_sec = 10
        self.pecg_auto_save_game = 'pecg_auto_save_games.pgn'
        self.my_games = 'pecg_my_games.pgn'
        self.repertoire_file = {'white': 'pecg_white_repertoire.pgn', 'black': 'pecg_black_repertoire.pgn'}
        self.init_game()
        self.fen = None
        self.engine_id_name_list = []
        self.engine_file_list = []
        self.username = 'Human'

        self.human_base_time_ms = 5 * 60 * 1000  # 5 minutes
        self.human_inc_time_ms = 10 * 1000  # 10 seconds
        self.human_period_moves = 0
        self.human_tc_type = 'fischer'

        self.engine_base_time_ms = 3 * 60 * 1000  # 5 minutes
        self.engine_inc_time_ms = 2 * 1000  # 10 seconds
        self.engine_period_moves = 0
        self.engine_tc_type = 'fischer'

        self.is_save_time_left = False
        self.is_save_user_comment = True

        self.interface = RenChessInterface(self)
        self.game = None

    def update_game(self, mc, user_move, time_left, user_comment):
        """
        Used for saving moves in the game.

        :param mc: move count
        :param user_move:
        :param time_left:
        :param user_comment: Can be a 'book' from the engine
        :return:
        """
        # Save user comment
        if self.is_save_user_comment:
            # If comment is empty
            if not (user_comment and user_comment.strip()):
                if mc == 1:
                    self.node = self.game.add_variation(user_move)
                else:
                    self.node = self.node.add_variation(user_move)

                # Save clock (time left after a move) as move comment
                if self.is_save_time_left:
                    rem_time = self.get_time_h_mm_ss(time_left, False)
                    self.node.comment = '[%clk {}]'.format(rem_time)
            else:
                if mc == 1:
                    self.node = self.game.add_variation(user_move)
                else:
                    self.node = self.node.add_variation(user_move)

                # Save clock, add clock as comment after a move
                if self.is_save_time_left:
                    rem_time = self.get_time_h_mm_ss(time_left, False)
                    self.node.comment = '[%clk {}] {}'.format(rem_time,
                                                         user_comment)
                else:
                    self.node.comment = user_comment
        # Do not save user comment
        else:
            if mc == 1:
                self.node = self.game.add_variation(user_move)
            else:
                self.node = self.node.add_variation(user_move)

            # Save clock, add clock as comment after a move
            if self.is_save_time_left:
                rem_time = self.get_time_h_mm_ss(time_left, False)
                self.node.comment = '[%clk {}]'.format(rem_time)

    def delete_player(self, name, pgn, que):
        """
        Delete games of player name in pgn.

        :param name:
        :param pgn:
        :param que:
        :return:
        """
        logging.info(f'Enters delete_player()')

        pgn_path = Path(pgn)
        folder_path = pgn_path.parents[0]

        file = PurePath(pgn)
        pgn_file = file.name

        # Create backup of orig
        backup = pgn_file + '.backup'
        backup_path = Path(folder_path, backup)
        backup_path.touch()
        origfile_text = Path(pgn).read_text()
        backup_path.write_text(origfile_text)
        logging.info(f'backup copy {backup_path} is successfully created.')

        # Define output file
        output = 'out_' + pgn_file
        output_path = Path(folder_path, output)
        logging.info(f'output {output_path} is successfully created.')

        logging.info(f'Deleting player {name}.')
        gcnt = 0

        # read pgn and save each game if player name to be deleted is not in
        # the game, either white or black.
        with open(output_path, 'a') as f:
            with open(pgn_path) as h:
                game = chess.pgn.read_game(h)
                while game:
                    gcnt += 1
                    que.put('Delete, {}, processing game {}'.format(
                        name, gcnt))
                    wp = game.headers['White']
                    bp = game.headers['Black']

                    # If this game has no player with name to be deleted
                    if wp != name and bp != name:
                        f.write('{}\n\n'.format(game))
                    game = chess.pgn.read_game(h)

        if output_path.exists():
            logging.info('Deleting player {} is successful.'.format(name))

            # Delete the orig file and rename the current output to orig file
            pgn_path.unlink()
            logging.info('Delete orig pgn file')
            output_path.rename(pgn_path)
            logging.info('Rename output to orig pgn file')

        que.put('Done')

    def get_players(self, pgn, q):
        logging.info(f'Enters get_players()')
        players = []
        games = 0
        with open(pgn) as h:
            while True:
                headers = chess.pgn.read_headers(h)
                if headers is None:
                    break

                wp = headers['White']
                bp = headers['Black']

                players.append(wp)
                players.append(bp)
                games += 1

        p = list(set(players))
        ret = [p, games]

        q.put(ret)

    def get_engine_id_name(self, path_and_file, q):
        """ Returns id name of uci engine """
        id_name = None
        folder = Path(path_and_file)
        folder = folder.parents[0]

        try:
            if platform == 'win32':
                engine = chess.engine.SimpleEngine.popen_uci(
                    path_and_file, cwd=folder,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                engine = chess.engine.SimpleEngine.popen_uci(
                    path_and_file, cwd=folder)
            id_name = engine.id['name']
            engine.quit()
        except Exception:
            logging.exception('Failed to get id name.')

        q.put(['Done', id_name])

    def get_engine_hash(self, eng_id_name):
        """ Returns hash value from engine config file """
        eng_hash = None
        with open(self.engine_config_file, 'r') as json_file:
            data = json.load(json_file)
            for p in data:
                if p['name'] == eng_id_name:
                    # There engines without options
                    try:
                        for n in p['options']:
                            if n['name'].lower() == 'hash':
                                return n['value']
                    except KeyError:
                        logging.info('This engine {} has no options.'.format(
                            eng_id_name))
                        break
                    except Exception:
                        logging.exception('Failed to get engine hash.')

        return eng_hash

    def get_engine_threads(self, eng_id_name):
        """
        Returns number of threads of eng_id_name from pecg_engines.json.

        :param eng_id_name: the engine id name
        :return: number of threads
        """
        eng_threads = None
        with open(self.engine_config_file, 'r') as json_file:
            data = json.load(json_file)
            for p in data:
                if p['name'] == eng_id_name:
                    try:
                        for n in p['options']:
                            if n['name'].lower() == 'threads':
                                return n['value']
                    except KeyError:
                        logging.info('This engine {} has no options.'.format(
                            eng_id_name))
                        break
                    except Exception:
                        logging.exception('Failed to get engine threads.')

        return eng_threads

    def get_engine_file(self, eng_id_name):
        """
        Returns eng_id_name's filename and path from pecg_engines.json file.

        :param eng_id_name: engine id name
        :return: engine file and its path
        """
        eng_file, eng_path_and_file = None, None
        with open(self.engine_config_file, 'r') as json_file:
            data = json.load(json_file)
            for p in data:
                if p['name'] == eng_id_name:
                    eng_file = p['command']
                    eng_path_and_file = Path(p['workingDirectory'],
                                             eng_file).as_posix()
                    break

        return eng_file, eng_path_and_file

    def get_engine_id_name_list(self):
        """
        Read engine config file.

        :return: list of engine id names
        """
        eng_id_name_list = []
        with open(self.engine_config_file, 'r') as json_file:
            data = json.load(json_file)
            for p in data:
                if p['protocol'] == 'uci':
                    eng_id_name_list.append(p['name'])

        eng_id_name_list = sorted(eng_id_name_list)

        return eng_id_name_list

    def update_user_config_file(self, username):
        """
        Update user config file. If username does not exist, save it.
        :param username:
        :return:
        """
        with open(self.user_config_file, 'r') as json_file:
            data = json.load(json_file)

        # Add the new entry if it does not exist
        is_name = False
        for i in range(len(data)):
            if data[i]['username'] == username:
                is_name = True
                break

        if not is_name:
            data.append({'username': username})

            # Save
            with open(self.user_config_file, 'w') as h:
                json.dump(data, h, indent=4)

    def check_user_config_file(self):
        """
        Check presence of pecg_user.json file, if nothing we will create
        one with ['username': 'Human']

        :return:
        """
        user_config_file_path = Path(self.user_config_file)
        if user_config_file_path.exists():
            with open(self.user_config_file, 'r') as json_file:
                data = json.load(json_file)
                for p in data:
                    username = p['username']
            self.username = username
        else:
            # Write a new user config file
            data = []
            data.append({'username': 'Human'})

            # Save data to pecg_user.json
            with open(self.user_config_file, 'w') as h:
                json.dump(data, h, indent=4)

    def update_engine_to_config_file(self, eng_path_file, new_name, old_name, user_opt):
        """
        Update engine config file based on params.

        :param eng_path_file: full path of engine
        :param new_name: new engine id name
        :param new_name: old engine id name
        :param user_opt: a list of dict, i.e d = ['a':a, 'b':b, ...]
        :return:
        """
        folder = Path(eng_path_file)
        folder = folder.parents[0]
        folder = Path(folder)
        folder = folder.as_posix()

        file = PurePath(eng_path_file)
        file = file.name

        with open(self.engine_config_file, 'r') as json_file:
            data = json.load(json_file)

        for p in data:
            command = p['command']
            work_dir = p['workingDirectory']

            if file == command and folder == work_dir and old_name == p['name']:
                p['name'] = new_name
                for k, v in p.items():
                    if k == 'options':
                        for d in v:
                            # d = {'name': 'Ponder', 'default': False,
                            # 'value': False, 'type': 'check'}
                            
                            default_type = type(d['default'])                            
                            opt_name = d['name']
                            opt_value = d['value']
                            for u in user_opt:
                                # u = {'name': 'CDrill 1400'}
                                for k1, v1 in u.items():
                                    if k1 == opt_name:
                                        v1 = int(v1) if default_type == int else v1
                                        if v1 != opt_value:
                                            d['value'] = v1
                break

        # Save data to pecg_engines.json
        with open(self.engine_config_file, 'w') as h:
            json.dump(data, h, indent=4)

    def is_name_exists(self, name):
        """

        :param name: The name to check in pecg.engines.json file.
        :return:
        """
        with open(self.engine_config_file, 'r') as json_file:
            data = json.load(json_file)

        for p in data:
            jname = p['name']
            if jname == name:
                return True

        return False

    def add_engine_to_config_file(self, engine_path_and_file, pname, que):
        """
        Add pname config in pecg_engines.json file.

        :param engine_path_and_file:
        :param pname: id name of uci engine
        :return:
        """
        folder = Path(engine_path_and_file).parents[0]
        file = PurePath(engine_path_and_file)
        file = file.name

        option = []

        with open(self.engine_config_file, 'r') as json_file:
            data = json.load(json_file)

        try:
            if platform == 'win32':
                engine = chess.engine.SimpleEngine.popen_uci(
                    engine_path_and_file, cwd=folder,
                    creationflags=subprocess.CREATE_NO_WINDOW)
            else:
                engine = chess.engine.SimpleEngine.popen_uci(
                    engine_path_and_file, cwd=folder)
        except Exception:
            logging.exception('Failed to add {} in config file.'.format(pname))
            que.put('Failure')
            return

        try:
            opt_dict = engine.options.items()
        except Exception:
            logging.exception('Failed to get engine options.')
            que.put('Failure')
            return

        engine.quit()

        for opt in opt_dict:
            o = opt[1]

            if o.type == 'spin':
                # Adjust hash and threads values
                if o.name.lower() == 'threads':
                    value = 1
                    logging.info('config {} is set to {}'.format(o.name,
                                                                 value))
                elif o.name.lower() == 'hash':
                    value = 32
                    logging.info('config {} is set to {}'.format(o.name,
                                                                 value))
                else:
                    value = o.default

                option.append({'name': o.name,
                               'default': o.default,
                               'value': value,
                               'type': o.type,
                               'min': o.min,
                               'max': o.max})
            elif o.type == 'combo':
                option.append({'name': o.name,
                               'default': o.default,
                               'value': o.default,
                               'type': o.type,
                               'choices':o.var})
            else:
                option.append({'name': o.name,
                               'default': o.default,
                               'value': o.default,
                               'type': o.type})

        # Save engine filename, working dir, name and options
        wdir = Path(folder).as_posix()
        protocol = 'uci'  # Only uci engine is supported so far
        self.engine_id_name_list.append(pname)
        data.append({'command': file, 'workingDirectory': wdir,
                     'name': pname, 'protocol': protocol,
                     'options': option})

        # Save data to pecg_engines.json
        with open(self.engine_config_file, 'w') as h:
            json.dump(data, h, indent=4)

        que.put('Success')

    def check_engine_config_file(self):
        """
        Check presence of engine config file pecg_engines.json. If not
        found we will create it, with entries from engines in Engines folder.

        :return:
        """
        ec = Path(self.engine_config_file)
        if ec.exists():
            return

        data = []
        cwd = Path.cwd()

        self.engine_file_list = self.get_engines()

        for fn in self.engine_file_list:
            # Run engine and get id name and options
            option = []

            # cwd=current working dir, engines=folder, fn=exe file
            epath = Path(cwd, 'Engines', fn)
            engine_path_and_file = str(epath)
            folder = epath.parents[0]

            try:
                if platform == 'win32':
                    engine = chess.engine.SimpleEngine.popen_uci(
                        engine_path_and_file, cwd=folder,
                        creationflags=subprocess.CREATE_NO_WINDOW)
                else:
                    engine = chess.engine.SimpleEngine.popen_uci(
                        engine_path_and_file, cwd=folder)
            except Exception:
                logging.exception(f'Failed to start engine {fn}!')
                continue

            engine_id_name = engine.id['name']
            opt_dict = engine.options.items()
            engine.quit()

            for opt in opt_dict:
                o = opt[1]

                if o.type == 'spin':
                    # Adjust hash and threads values
                    if o.name.lower() == 'threads':
                        value = 1
                    elif o.name.lower() == 'hash':
                        value = 32
                    else:
                        value = o.default

                    option.append({'name': o.name,
                                   'default': o.default,
                                   'value': value,
                                   'type': o.type,
                                   'min': o.min,
                                   'max': o.max})
                elif o.type == 'combo':
                    option.append({'name': o.name,
                                   'default': o.default,
                                   'value': o.default,
                                   'type': o.type,
                                   'choices':o.var})
                else:
                    option.append({'name': o.name,
                                   'default': o.default,
                                   'value': o.default,
                                   'type': o.type})

            # Save engine filename, working dir, name and options
            wdir = Path(cwd, 'Engines').as_posix()
            name = engine_id_name
            protocol = 'uci'
            self.engine_id_name_list.append(name)
            data.append({'command': fn, 'workingDirectory': wdir,
                         'name': name, 'protocol': protocol,
                         'options': option})

        # Save data to pecg_engines.json
        with open(self.engine_config_file, 'w') as h:
            json.dump(data, h, indent=4)

    def get_time_mm_ss_ms(self, time_ms):
        """ Returns time in min:sec:millisec given time in millisec """
        s, ms = divmod(int(time_ms), 1000)
        m, s = divmod(s, 60)

        # return '{:02d}m:{:02d}s:{:03d}ms'.format(m, s, ms)
        return '{:02d}m:{:02d}s'.format(m, s)

    def get_time_h_mm_ss(self, time_ms, symbol=True):
        """
        Returns time in h:mm:ss format.

        :param time_ms:
        :param symbol:
        :return:
        """
        s, ms = divmod(int(time_ms), 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)

        if not symbol:
            return '{:01d}:{:02d}:{:02d}'.format(h, m, s)
        return '{:01d}h:{:02d}m:{:02d}s'.format(h, m, s)

    def update_text_box(self, window, msg, is_hide):
        """ Update text elements """
        best_move = None
        msg_str = str(msg)

        if not 'bestmove ' in msg_str:
            if 'info_all' in msg_str:
                info_all = ' '.join(msg_str.split()[0:-1]).strip()
                msg_line = '{}\n'.format(info_all)
                window.FindElement('search_info_all_k').Update(
                        '' if is_hide else msg_line)
        else:
            # Best move can be None because engine dies
            try:
                best_move = chess.Move.from_uci(msg.split()[1])
            except Exception:
                logging.exception('Engine sent {}.'.format(best_move))
                sg.Popup('Engine error, it sent a {} bestmove.\n'.format(
                    best_move) + 'Back to Neutral mode, it is better to '
                                 'change engine {}.'.format(
                    self.opp_id_name), icon=ico_path[platform]['pecg'],
                    title=BOX_TITLE)

        return best_move

    def get_tag_date(self):
        """ Return date in pgn tag date format """
        return datetime.today().strftime('%Y.%m.%d')

    def init_game(self):
        """ Initialize game with initial pgn tag values """
        self.game = chess.pgn.Game()
        self.node = None
        self.game.headers['Event'] = INIT_PGN_TAG['Event']
        self.game.headers['Date'] = self.get_tag_date()
        self.game.headers['White'] = INIT_PGN_TAG['White']
        self.game.headers['Black'] = INIT_PGN_TAG['Black']

    def set_new_game(self):
        """ Initialize new game but save old pgn tag values"""
        old_event = self.game.headers['Event']
        old_white = self.game.headers['White']
        old_black = self.game.headers['Black']

        # Define a game object for saving game in pgn format
        self.game = chess.pgn.Game()

        self.game.headers['Event'] = old_event
        self.game.headers['Date'] = self.get_tag_date()
        self.game.headers['White'] = old_white
        self.game.headers['Black'] = old_black

    def clear_elements(self, window):
        """ Clear movelist, score, pv, time, depth and nps boxes """
        window.FindElement('search_info_all_k').Update('')
        window.FindElement('_movelist_').Update(disabled=False)
        window.FindElement('_movelist_').Update('', disabled=True)
        window.FindElement('polyglot_book1_k').Update('')
        window.FindElement('polyglot_book2_k').Update('')
        window.FindElement('advise_info_k').Update('')
        window.FindElement('comment_k').Update('')
        window.Element('w_base_time_k').Update('')
        window.Element('b_base_time_k').Update('')
        window.Element('w_elapse_k').Update('')
        window.Element('b_elapse_k').Update('')    

    def get_fen(self):
        """ Get fen from clipboard """
        self.fen = pyperclip.paste()

        # Remove empty char at the end of FEN
        if self.fen.endswith(' '):
            self.fen = self.fen[:-1]

    def fen_to_psg_board(self):
        """ Update psg_board based on FEN """
        psgboard = []

        # Get piece locations only to build psg board
        pc_locations = self.fen.split()[0]

        board = chess.BaseBoard(pc_locations)
        old_r = None

        for s in chess.SQUARES:
            r = chess.square_rank(s)

            if old_r is None:
                piece_r = []
            elif old_r != r:
                psgboard.append(piece_r)
                piece_r = []
            elif s == 63:
                psgboard.append(piece_r)

            try:
                pc = board.piece_at(s^56)
            except Exception:
                pc = None
                logging.exception('Failed to get piece.')

            if pc is not None:
                pt = pc.piece_type
                c = pc.color
                if c:
                    if pt == chess.PAWN:
                        piece_r.append(PAWNW)
                    elif pt == chess.KNIGHT:
                        piece_r.append(KNIGHTW)
                    elif pt == chess.BISHOP:
                        piece_r.append(BISHOPW)
                    elif pt == chess.ROOK:
                        piece_r.append(ROOKW)
                    elif pt == chess.QUEEN:
                        piece_r.append(QUEENW)
                    elif pt == chess.KING:
                        piece_r.append(KINGW)
                else:
                    if pt == chess.PAWN:
                        piece_r.append(PAWNB)
                    elif pt == chess.KNIGHT:
                        piece_r.append(KNIGHTB)
                    elif pt == chess.BISHOP:
                        piece_r.append(BISHOPB)
                    elif pt == chess.ROOK:
                        piece_r.append(ROOKB)
                    elif pt == chess.QUEEN:
                        piece_r.append(QUEENB)
                    elif pt == chess.KING:
                        piece_r.append(KINGB)

            # Else if pc is None or square is empty
            else:
                piece_r.append(BLANK)

            old_r = r

        self.psg_board = psgboard
        self.interface.redraw_board()    
           
    def define_timer(self, window, name='human'):
        """
        Returns Timer object for either human or engine.
        """
        if name == 'human':
            timer = Timer(self.human_tc_type, self.human_base_time_ms,
                          self.human_inc_time_ms, self.human_period_moves)           
        else:
            timer = Timer(self.engine_tc_type, self.engine_base_time_ms,
                      self.engine_inc_time_ms, self.engine_period_moves)

        elapse_str = self.get_time_h_mm_ss(timer.base)
        is_white_base = self.is_user_white and name == 'human' or \
                not self.is_user_white and name != 'human'
        window.Element('w_base_time_k' if is_white_base else 'b_base_time_k').Update(
                elapse_str)
            
        return timer

    def play_puzzle(self):
        self.psg_board = copy.deepcopy(initial_board)
        window = self.interface.window

        f = open('E:\Workshop\project\RenChess\data\polgar_5334.dat', 'r')
        context = f.readlines()
        i = 0
        puzzles = []
        while i < len(context):
            line = context[i]
            if len(line.strip()) == 0:
                i += 1
            else:
                puzzles.append([context[i].strip(), context[i+1].strip(), context[i+2].strip()])
                i += 3

        id = 0
        while id < 10:
            button, value = window.Read(timeout=100)

            window.FindElement('_gamestatus_').Update('Mode     Play')
            window.FindElement('_movelist_').Update(disabled=False)
            window.FindElement('_movelist_').Update('', disabled=True)
            self.fen = puzzles[id][1]
            self.fen_to_psg_board()

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
            """ % (puzzles[id][0], self.fen, puzzles[id][2])
            if chessPuzzle.Puzzle(self, self.interface, {}, pgn).run() == False:
                return False
            id += 1

    def play_game(self):
        # Change menu from Neutral to Play
        self.psg_board = copy.deepcopy(initial_board)
        window = self.interface.window
        while True:
            button, value = window.Read(timeout=100)

            window.FindElement('_gamestatus_').Update('Mode     Play')
            window.FindElement('_movelist_').Update(disabled=False)
            window.FindElement('_movelist_').Update('', disabled=True)

            if chessGame.Game(self, self.interface, {}).run() == False:
                return False
            window.FindElement('_gamestatus_').Update('Mode     Neutral')

            self.psg_board = copy.deepcopy(initial_board)
            self.interface.redraw_board()
            self.set_new_game()
    
    def save_game(self):
        """ Save game in append mode """
        with open(self.pecg_auto_save_game, mode = 'a+') as f:
            f.write('{}\n\n'.format(self.game))

    def get_engines(self):
        """
        Get engine filenames [a.exe, b.exe, ...]

        :return: list of engine filenames
        """
        engine_list = []
        engine_path = Path('Engines')
        files = os.listdir(engine_path)
        for file in files:
            if not file.endswith('.gz') and not file.endswith('.dll') \
                    and not file.endswith('.bin') \
                    and not file.endswith('.dat'):
                engine_list.append(file)

        return engine_list
    
    def set_default_adviser_engine(self):    
        try:
            self.adviser_id_name = self.engine_id_name_list[1] \
                   if len(self.engine_id_name_list) >= 2 \
                   else self.engine_id_name_list[0]
            self.adviser_file, self.adviser_path_and_file = \
                self.get_engine_file(self.adviser_id_name)
        except IndexError as e:
            logging.warning(e)
        except Exception:
            logging.exception('Error in getting adviser engine!')
    
    def get_default_engine_opponent(self):
        engine_id_name = None
        try:
            engine_id_name = self.opp_id_name = self.engine_id_name_list[0]
            self.opp_file, self.opp_path_and_file = self.get_engine_file(
                engine_id_name)
        except IndexError as e:
            logging.warning(e)
        except Exception:
            logging.exception('Error in getting opponent engine!')
            
        return engine_id_name

    def main_loop(self):
        """
        Build GUI, read user and engine config files and take user inputs.

        :return:
        """
        engine_id_name = None
        window = self.interface.create_default_window()

        # Read user config file, if missing create and new one
        self.check_user_config_file()

        # If engine config file (pecg_engines.json) is missing, then create it        
        self.check_engine_config_file()
        self.engine_id_name_list = self.get_engine_id_name_list()

        # Define default opponent engine, user can change this later.
        engine_id_name = self.get_default_engine_opponent()

        # Define default adviser engine, user can change this later.
        self.set_default_adviser_engine()

        self.init_game()

        # Initialize White and black boxes
        while True:
            button, value = window.Read(timeout=50)
            self.interface.update_labels_and_game_tags(window, human=self.username)
            break

        # Mode: Neutral, main loop starts here
        while True:
            button, value = window.Read(timeout=50)

            if button == 'main_puzzles':
                window.FindElement('main_page').Update(visible=False)                
                window.FindElement('game_column').Update(visible=False)
                window.FindElement('puzzle_column').Update(visible=True)
                window.FindElement('play_page').Update(visible=True)
                if self.play_puzzle() == False:
                    break
                continue
            if button == 'main_game':
                window.FindElement('main_page').Update(visible=False)
                window.FindElement('game_column').Update(visible=True)
                if self.play_game() == False:
                    # Exit app
                    break
                continue

            # Mode: Neutral
            if button is None:
                logging.info('Quit app from main loop, X is pressed.')
                break
                                               
        window.Close()


def main():
    engine_config_file = 'pecg_engines.json'
    user_config_file = 'pecg_user.json'

    pecg_book = 'Book/pecg_book.bin'
    book_from_computer_games = 'Book/computer.bin'
    book_from_human_games = 'Book/human.bin'

    is_use_gui_book = True
    is_random_book = True  # If false then use best book move
    max_book_ply = 8
    theme = 'Reddit'

    pecg = RenChessApp(theme, engine_config_file, user_config_file,
                        pecg_book, book_from_computer_games,
                        book_from_human_games, is_use_gui_book, is_random_book,
                        max_book_ply)

    pecg.main_loop()


if __name__ == "__main__":
    main()