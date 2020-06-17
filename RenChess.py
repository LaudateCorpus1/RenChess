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
        self.psg_board = None
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

        # Default board color is brown
        self.sq_light_color = '#F0D9B5'
        self.sq_dark_color = '#B58863'

        # Move highlight, for brown board
        self.move_sq_light_color = '#E8E18E'
        self.move_sq_dark_color = '#B8AF4E'

        self.is_save_time_left = False
        self.is_save_user_comment = True

        self.interface = RenChessInterface(self)

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

    def fen_to_psg_board(self, window):
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
        self.redraw_board(window)

    def change_square_color(self, window, row, col):
        """ 
        Change the color of a square based on square row and col.
        """
        btn_sq = window.FindElement(key=(row, col))
        is_dark_square = True if (row + col) % 2 else False
        bd_sq_color = self.move_sq_dark_color if is_dark_square else \
                      self.move_sq_light_color
        btn_sq.Update(button_color=('white', bd_sq_color))

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

    def redraw_board(self, window):
        """
        Redraw board at start and afte a move.

        :param window:
        :return:
        """
        for i in range(8):
            for j in range(8):
                color = self.sq_dark_color if (i + j) % 2 else \
                        self.sq_light_color
                piece_image = images[self.psg_board[i][j]]
                elem = window.FindElement(key=(i, j))
                elem.Update(button_color=('white', color),
                            image_filename=piece_image, )

    

    def select_promotion_piece(self, stm):
        """
        Allow user to select a piece type to promote to.

        :param stm: side to move
        :return: promoted piece, i.e QUEENW, QUEENB ...
        """
        piece = None
        board_layout, row = [], []

        psg_promote_board = copy.deepcopy(white_init_promote_board) if stm \
                else copy.deepcopy(black_init_promote_board)

        # Loop through board and create buttons with images        
        for i in range(1):
            for j in range(4):
                piece_image = images[psg_promote_board[i][j]]
                row.append(self.render_square(piece_image, key=(i, j),
                                              location=(i, j)))

            board_layout.append(row)

        promo_window = sg.Window('{} {}'.format(APP_NAME, APP_VERSION),
                                 board_layout,
                                 default_button_element_size=(12, 1),
                                 auto_size_buttons=False,
                                 icon=ico_path[platform]['pecg'])

        while True:
            button, value = promo_window.Read(timeout=0)
            if button is None:
                break
            if type(button) is tuple:
                move_from = button
                fr_row, fr_col = move_from
                piece = psg_promote_board[fr_row][fr_col]
                logging.info('promote piece: {}'.format(piece))
                break

        promo_window.Close()

        return piece

    def update_rook(self, window, move):
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

        self.psg_board[self.get_row(fr)][self.get_col(fr)] = BLANK
        self.psg_board[self.get_row(to)][self.get_col(to)] = pc
        self.redraw_board(window)

    def update_ep(self, window, move, stm):
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

        self.psg_board[self.get_row(capture_sq)][self.get_col(capture_sq)] = BLANK
        self.redraw_board(window)

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
            psg_promo = self.select_promotion_piece(stm)

            # If user pressed x we set the promo to queen
            if psg_promo is None:
                logging.info('User did not select a promotion piece, '
                             'set this to queen.')
                psg_promo = QUEENW if stm else QUEENB

            pyc_promo = promote_psg_to_pyc[psg_promo]
        # Else if move is from computer
        else:
            pyc_promo = move.promotion  # This is from python-chess
            if stm:
                if pyc_promo == chess.QUEEN:
                    psg_promo = QUEENW
                elif pyc_promo == chess.ROOK:
                    psg_promo = ROOKW
                elif pyc_promo == chess.BISHOP:
                    psg_promo = BISHOPW
                elif pyc_promo == chess.KNIGHT:
                    psg_promo = KNIGHTW
            else:
                if pyc_promo == chess.QUEEN:
                    psg_promo = QUEENB
                elif pyc_promo == chess.ROOK:
                    psg_promo = ROOKB
                elif pyc_promo == chess.BISHOP:
                    psg_promo = BISHOPB
                elif pyc_promo == chess.KNIGHT:
                    psg_promo = KNIGHTB

        return pyc_promo, psg_promo
        
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

    def play_game_main_loop(self, window, engine_id_name):
        # Change menu from Neutral to Play
        self.interface.menu_elem.Update(menu_def_play)
        self.psg_board = copy.deepcopy(initial_board)
        board = chess.Board()

        while True:
            button, value = window.Read(timeout=100)

            window.FindElement('_gamestatus_').Update('Mode     Play')
            window.FindElement('_movelist_').Update(disabled=False)
            window.FindElement('_movelist_').Update('', disabled=True)

            start_new_game = self.play_game(window, engine_id_name, board)
            window.FindElement('_gamestatus_').Update('Mode     Neutral')

            self.psg_board = copy.deepcopy(initial_board)
            self.redraw_board(window)
            board = chess.Board()
            self.set_new_game()

            if not start_new_game:
                break

    def play_game(self, window, engine_id_name, board):
        """
        User can play a game against and engine.

        :param window:
        :param engine_id_name:
        :param board: current board position
        :return:
        """
        window.FindElement('_movelist_').Update(disabled=False)
        window.FindElement('_movelist_').Update('', disabled=True)

        is_human_stm = True if self.is_user_white else False

        move_state = 0
        move_from, move_to = None, None
        is_new_game, is_exit_game, is_exit_app = False, False, False

        # Do not play immediately when stm is computer
        is_engine_ready = True if is_human_stm else False

        # For saving game
        move_cnt = 0

        is_user_resigns = False
        is_user_wins = False
        is_user_draws = False
        is_search_stop_for_exit = False
        is_search_stop_for_new_game = False
        is_search_stop_for_neutral = False
        is_search_stop_for_resign = False
        is_search_stop_for_user_wins = False
        is_search_stop_for_user_draws = False
        is_hide_book1 = True
        is_hide_book2 = True
        is_hide_search_info = True

        # Init timer
        human_timer = self.define_timer(window)
        engine_timer = self.define_timer(window, 'engine')

        # Game loop
        while not board.is_game_over(claim_draw=True):
            moved_piece = None

            # Mode: Play, Hide book 1
            if is_hide_book1:
                window.Element('polyglot_book1_k').Update('')
            else:
                # Load 2 polyglot book files        
                ref_book1 = GuiBook(self.computer_book_file, board,
                                    self.is_random_book)
                all_moves, is_found = ref_book1.get_all_moves()
                if is_found:
                    window.Element('polyglot_book1_k').Update(all_moves)
                else:
                    window.Element('polyglot_book1_k').Update('no book moves')

            # Mode: Play, Hide book 2
            if is_hide_book2:
                window.Element('polyglot_book2_k').Update('')
            else:
                ref_book2 = GuiBook(self.human_book_file, board,
                                    self.is_random_book)
                all_moves, is_found = ref_book2.get_all_moves()
                if is_found:
                    window.Element('polyglot_book2_k').Update(all_moves)
                else:
                    window.Element('polyglot_book2_k').Update('no book moves')

            # Mode: Play, Stm: computer (first move), Allow user to change settings.
            # User can start the engine by Engine->Go.
            if not is_engine_ready:
                window.FindElement('_gamestatus_').Update(
                        'Mode     Play, press Engine->Go')
                while True:
                    button, value = window.Read(timeout=100)

                    # Mode: Play, Stm: computer (first move)
                    if button == 'New::new_game_k':
                        is_new_game = True
                        break

                    # Mode: Play, Stm: Computer first move
                    if button == 'Neutral':
                        is_exit_game = True
                        break

                    if button == 'About':
                        sg.PopupScrolled(HELP_MSG, title=BOX_TITLE)
                        continue

                    if button == 'Paste':
                        try:
                            self.get_fen()
                            self.set_new_game()
                            board = chess.Board(self.fen)
                        except Exception:
                            logging.exception('Error in parsing FEN from clipboard.')
                            continue

                        self.fen_to_psg_board(window)

                        # If user is black and side to move is black
                        if not self.is_user_white and not board.turn:
                            is_human_stm = True
                            window.FindElement('_gamestatus_').Update(
                                'Mode     Play')

                        # Elif user is black and side to move is white
                        elif not self.is_user_white and board.turn:
                            is_human_stm = False
                            window.FindElement('_gamestatus_').Update(
                                    'Mode     Play, press Engine->Go')

                        # When computer is to move in the first move, don't
                        # allow the engine to search immediately, wait for the
                        # user to press Engine->Go menu.
                        is_engine_ready = True if is_human_stm else False

                        self.game.headers['FEN'] = self.fen
                        break

                    if button == 'Go':
                        is_engine_ready = True
                        break

                    if button is None:
                        logging.info('Quit app X is pressed.')
                        is_exit_app = True
                        break

                if is_exit_app or is_exit_game or is_new_game:
                    break

            # If side to move is human
            if is_human_stm:
                move_state = 0

                while True:
                    button, value = window.Read(timeout=100)

                    # Update elapse box in m:s format
                    elapse_str = self.get_time_mm_ss_ms(human_timer.elapse)
                    k = 'w_elapse_k'
                    if not self.is_user_white:
                        k = 'b_elapse_k'
                    window.Element(k).Update(elapse_str)
                    human_timer.elapse += 100

                    if not is_human_stm:
                        break

                    # Mode: Play, Stm: User, Run adviser engine
                    if button == 'Start::right_adviser_k':
                        self.adviser_threads = self.get_engine_threads(
                            self.adviser_id_name)
                        self.adviser_hash = self.get_engine_hash(
                            self.adviser_id_name)
                        adviser_base_ms = self.adviser_movetime_sec * 1000
                        adviser_inc_ms = 0

                        search = RunEngine(self.queue, self.engine_config_file,
                            self.adviser_path_and_file, self.adviser_id_name,
                            self.max_depth, adviser_base_ms, adviser_inc_ms,
                                           tc_type='timepermove',
                                           period_moves=0,
                                           is_stream_search_info=True)
                        search.get_board(board)
                        search.daemon = True
                        search.start()

                        while True:
                            button, value = window.Read(timeout=10)

                            if button == 'Stop::right_adviser_k':
                                search.stop()

                            # Exit app while adviser is thinking                    
                            if button is None:
                                search.stop()                                
                                is_search_stop_for_exit = True
                            try:
                                msg = self.queue.get_nowait()
                                if 'pv' in msg:
                                    # Reformat msg, remove the word pv at the end
                                    msg_line = ' '.join(msg.split()[0:-1])
                                    window.Element('advise_info_k').Update(msg_line)
                            except Exception:
                                continue

                            if 'bestmove' in msg:
                                # bestmove can be None so we do try/except
                                try:
                                    # Shorten msg line to 3 ply moves
                                    msg_line = ' '.join(msg_line.split()[0:3])
                                    msg_line += ' - ' + self.adviser_id_name
                                    window.Element('advise_info_k').Update(msg_line)
                                except Exception:
                                    logging.exception('Adviser engine error')
                                    sg.Popup('Adviser engine {} error.\n'.format(
                                            self.adviser_id_name) + \
                                            'It is better to change this engine.\n' +
                                            'Change to Neutral mode first.',
                                            icon=ico_path[platform]['pecg'],
                                            title=BOX_TITLE)
                                break

                        search.join()
                        search.quit_engine()
                        break

                    # Mode: Play, Stm: user
                    if button == 'Show::right_search_info_k':
                        is_hide_search_info = False
                        break

                    # Mode: Play, Stm: user
                    if button == 'Hide::right_search_info_k':
                        is_hide_search_info = True
                        window.Element('search_info_all_k').Update('')
                        break

                    # Mode: Play, Stm: user
                    if button == 'Show::right_book1_k':
                        is_hide_book1 = False
                        break

                    # Mode: Play, Stm: user
                    if button == 'Hide::right_book1_k':
                        is_hide_book1 = True
                        break

                    # Mode: Play, Stm: user
                    if button == 'Show::right_book2_k':
                        is_hide_book2 = False
                        break

                    # Mode: Play, Stm: user
                    if button == 'Hide::right_book2_k':
                        is_hide_book2 = True
                        break

                    if button is None:
                        logging.info('Quit app X is pressed.')
                        is_exit_app = True
                        break

                    if is_search_stop_for_exit:
                        is_exit_app = True
                        break

                    # Mode: Play, Stm: User
                    if button == 'New::new_game_k' or is_search_stop_for_new_game:
                        is_new_game = True
                        self.clear_elements(window)
                        break

                    if button == 'Save to My Games::save_game_k':
                        logging.info('Saving game manually')
                        with open(self.my_games, mode = 'a+') as f:
                            self.game.headers['Event'] = 'My Games'
                            f.write('{}\n\n'.format(self.game))
                        break

                    # Mode: Play, Stm: user
                    if button == 'Save to White Repertoire':
                        with open(self.repertoire_file['white'], mode = 'a+') as f:
                            self.game.headers['Event'] = 'White Repertoire'
                            f.write('{}\n\n'.format(self.game))
                        break

                    # Mode: Play, Stm: user
                    if button == 'Save to Black Repertoire':
                        with open(self.repertoire_file['black'], mode = 'a+') as f:
                            self.game.headers['Event'] = 'Black Repertoire'
                            f.write('{}\n\n'.format(self.game))
                        break

                    # Mode: Play, stm: User
                    if button == 'Resign::resign_game_k' or is_search_stop_for_resign:
                        logging.info('User resigns')

                        # Verify resign
                        reply = sg.Popup('Do you really want to resign?',
                                         button_type=sg.POPUP_BUTTONS_YES_NO,
                                         title=BOX_TITLE,
                                         icon=ico_path[platform]['pecg'])
                        if reply == 'Yes':
                            is_user_resigns = True
                            break
                        else:
                            if is_search_stop_for_resign:
                                is_search_stop_for_resign = False
                            continue

                    # Mode: Play, stm: User
                    if button == 'User Wins::user_wins_k' or is_search_stop_for_user_wins:
                        logging.info('User wins by adjudication')
                        is_user_wins = True
                        break

                    # Mode: Play, stm: User
                    if button == 'User Draws::user_draws_k' or is_search_stop_for_user_draws:
                        logging.info('User draws by adjudication')
                        is_user_draws = True
                        break

                    # Mode: Play, Stm: User
                    if button == 'Neutral' or is_search_stop_for_neutral:
                        is_exit_game = True
                        self.clear_elements(window)
                        break

                    # Mode: Play, stm: User
                    if button == 'About':
                        sg.PopupScrolled(HELP_MSG, title=BOX_TITLE,)
                        break

                    # Mode: Play, stm: User
                    if button == 'Go':
                        if is_human_stm:
                            is_human_stm = False
                        else:
                            is_human_stm = True
                        is_engine_ready = True
                        window.FindElement('_gamestatus_').Update(
                                'Mode     Play, Engine is thinking ...')
                        break

                    # Mode: Play, stm: User
                    if button == 'Paste':
                        # Pasting fen is only allowed before the game starts.
                        if len(self.game.variations):
                            sg.Popup('Press Game->New then paste your fen.',
                                     title='Mode Play')
                            continue
                        try:
                            self.get_fen()
                            self.set_new_game()
                            board = chess.Board(self.fen)
                        except Exception:
                            logging.exception('Error in parsing FEN from clipboard.')
                            continue

                        self.fen_to_psg_board(window)

                        is_human_stm = True if board.turn else False
                        is_engine_ready = True if is_human_stm else False

                        window.FindElement('_gamestatus_').Update(
                                'Mode     Play, side: {}'.format(
                                        'white' if board.turn else 'black'))

                        self.game.headers['FEN'] = self.fen
                        break

                    # Mode: Play, stm: User, user starts moving
                    if type(button) is tuple:
                        # If fr_sq button is pressed
                        if move_state == 0:
                            move_from = button
                            fr_row, fr_col = move_from
                            piece = self.psg_board[fr_row][fr_col]  # get the move-from piece

                            # Change the color of the "fr" board square
                            self.change_square_color(window, fr_row, fr_col)

                            move_state = 1
                            moved_piece = board.piece_type_at(chess.square(fr_col, 7-fr_row))  # Pawn=1

                        # Else if to_sq button is pressed
                        elif move_state == 1:
                            is_promote = False
                            move_to = button
                            to_row, to_col = move_to
                            button_square = window.FindElement(key=(fr_row, fr_col))

                            # If move is cancelled, pressing same button twice
                            if move_to == move_from:
                                # Restore the color of the pressed board square
                                color = self.sq_dark_color if (to_row + to_col) % 2 else self.sq_light_color

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
                            if self.relative_row(to_sq, board.turn) == RANK_8 and \
                                    moved_piece == chess.PAWN:
                                is_promote = True
                                pyc_promo, psg_promo = self.get_promo_piece(
                                        user_move, board.turn, True)
                                user_move = chess.Move(fr_sq, to_sq, promotion=pyc_promo)
                            else:
                                user_move = chess.Move(fr_sq, to_sq)

                            # Check if user move is legal
                            if user_move in board.legal_moves:
                                # Update rook location if this is a castle move
                                if board.is_castling(user_move):
                                    self.update_rook(window, str(user_move))

                                # Update board if e.p capture
                                elif board.is_en_passant(user_move):
                                    self.update_ep(user_move, board.turn)

                                # Empty the board from_square, applied to any types of move
                                self.psg_board[move_from[0]][move_from[1]] = BLANK

                                # Update board to_square if move is a promotion
                                if is_promote:
                                    self.psg_board[to_row][to_col] = psg_promo
                                # Update the to_square if not a promote move
                                else:
                                    # Place piece in the move to_square
                                    self.psg_board[to_row][to_col] = piece

                                self.redraw_board(window)

                                board.push(user_move)
                                move_cnt += 1

                                # Update clock, reset elapse to zero
                                human_timer.update_base()

                                # Update game, move from human
                                time_left = human_timer.base
                                user_comment = value['comment_k']
                                self.update_game(move_cnt, user_move, time_left, user_comment)

                                window.FindElement('_movelist_').Update(disabled=False)
                                window.FindElement('_movelist_').Update('')
                                window.FindElement('_movelist_').Update(
                                    self.game.variations[0], append=True, disabled=True)

                                # Clear comment and engine search box
                                window.FindElement('comment_k').Update('')
                                window.Element('search_info_all_k').Update('')

                                # Change the color of the "fr" and "to" board squares
                                self.change_square_color(window, fr_row, fr_col)
                                self.change_square_color(window, to_row, to_col)

                                is_human_stm = not is_human_stm
                                # Human has done its move

                                k1 = 'w_elapse_k'
                                k2 = 'w_base_time_k'
                                if not self.is_user_white:
                                    k1 = 'b_elapse_k'
                                    k2 = 'b_base_time_k'

                                # Update elapse box
                                elapse_str = self.get_time_mm_ss_ms(
                                    human_timer.elapse)
                                window.Element(k1).Update(elapse_str)

                                # Update remaining time box
                                elapse_str = self.get_time_h_mm_ss(
                                    human_timer.base)
                                window.Element(k2).Update(elapse_str)

                                window.Element('advise_info_k').Update('')

                            # Else if move is illegal
                            else:
                                move_state = 0
                                color = self.sq_dark_color \
                                    if (move_from[0] + move_from[1]) % 2 else self.sq_light_color

                                # Restore the color of the fr square
                                button_square.Update(button_color=('white', color))
                                continue

                if is_new_game or is_exit_game or is_exit_app or \
                    is_user_resigns or is_user_wins or is_user_draws:
                    break

            # Else if side to move is not human
            elif not is_human_stm and is_engine_ready:
                is_promote = False
                best_move = None
                is_book_from_gui = True

                # Mode: Play, stm: Computer, If using gui book
                if self.is_use_gui_book and move_cnt <= self.max_book_ply:
                    # Verify presence of a book file
                    if os.path.isfile(self.gui_book_file):
                        gui_book = GuiBook(self.gui_book_file, board, self.is_random_book)
                        best_move = gui_book.get_book_move()
                        logging.info('Book move is {}.'.format(best_move))
                    else:
                        logging.warning('GUI book is missing.')

                # Mode: Play, stm: Computer, If there is no book move,
                # let the engine search the best move
                if best_move is None:
                    search = RunEngine(self.queue, self.engine_config_file,
                        self.opp_path_and_file, self.opp_id_name,
                        self.max_depth, engine_timer.base,
                                       engine_timer.inc,
                                       tc_type=engine_timer.tc_type,
                                       period_moves=board.fullmove_number)
                    search.get_board(board)
                    search.daemon = True
                    search.start()
                    window.FindElement('_gamestatus_').Update(
                            'Mode     Play, Engine is thinking ...')

                    while True:
                        button, value = window.Read(timeout=100)

                        # Update elapse box in m:s format
                        elapse_str = self.get_time_mm_ss_ms(engine_timer.elapse)
                        k = 'b_elapse_k'
                        if not self.is_user_white:
                            k = 'w_elapse_k'
                        window.Element(k).Update(elapse_str)
                        engine_timer.elapse += 100

                        # Hide/Unhide engine searching info while engine is thinking
                        if button == 'Show::right_search_info_k':
                            is_hide_search_info = False

                        if button == 'Hide::right_search_info_k':
                            is_hide_search_info = True
                            window.Element('search_info_all_k').Update('')

                        # Show book 1 while engine is searching
                        if button == 'Show::right_book1_k':
                            is_hide_book1 = False
                            ref_book1 = GuiBook(self.computer_book_file,
                                                board, self.is_random_book)
                            all_moves, is_found = ref_book1.get_all_moves()
                            if is_found:
                                window.Element('polyglot_book1_k').Update(all_moves)
                            else:
                                window.Element('polyglot_book1_k').Update('no book moves')

                        # Hide book 1 while engine is searching
                        if button == 'Hide::right_book1_k':
                            is_hide_book1 = True
                            window.Element('polyglot_book1_k').Update('')

                        # Show book 2 while engine is searching
                        if button == 'Show::right_book2_k':
                            is_hide_book2 = False
                            ref_book2 = GuiBook(self.human_book_file, board,
                                                self.is_random_book)
                            all_moves, is_found = ref_book2.get_all_moves()
                            if is_found:
                                window.Element('polyglot_book2_k').Update(all_moves)
                            else:
                                window.Element('polyglot_book2_k').Update('no book moves')

                        # Hide book 2 while engine is searching
                        if button == 'Hide::right_book2_k':
                            is_hide_book2 = True
                            window.Element('polyglot_book2_k').Update('')

                        # Exit app while engine is thinking                    
                        if button is None:
                            search.stop()
                            is_search_stop_for_exit = True

                        # Forced engine to move now and create a new game
                        if button == 'New::new_game_k':
                            search.stop()
                            is_search_stop_for_new_game = True

                        # Forced engine to move now
                        if button == 'Move Now':
                            search.stop()

                        # Mode: Play, Computer is thinking
                        if button == 'Neutral':
                            search.stop()
                            is_search_stop_for_neutral = True

                        if button == 'Resign::resign_game_k':
                            search.stop()
                            is_search_stop_for_resign = True

                        if button == 'User Wins::user_wins_k':
                            search.stop()
                            is_search_stop_for_user_wins = True

                        if button == 'User Draws::user_draws_k':
                            search.stop()
                            is_search_stop_for_user_draws = True

                        # Get the engine search info and display it in GUI text boxes
                        try:
                            msg = self.queue.get_nowait()
                        except Exception:
                            continue

                        msg_str = str(msg)
                        best_move = self.update_text_box(window, msg, is_hide_search_info)
                        if 'bestmove' in msg_str:
                            logging.info('engine msg: {}'.format(msg_str))
                            break

                    search.join()
                    search.quit_engine()
                    is_book_from_gui = False

                # If engine failed to send a legal move
                if best_move is None:
                    break

                # Update board with computer move
                move_str = str(best_move)
                fr_col = ord(move_str[0]) - ord('a')
                fr_row = 8 - int(move_str[1])
                to_col = ord(move_str[2]) - ord('a')
                to_row = 8 - int(move_str[3])

                piece = self.psg_board[fr_row][fr_col]
                self.psg_board[fr_row][fr_col] = BLANK

                # Update rook location if this is a castle move
                if board.is_castling(best_move):
                    self.update_rook(window, move_str)

                # Update board if e.p capture
                elif board.is_en_passant(best_move):
                    self.update_ep(best_move, board.turn)

                # Update board if move is a promotion
                elif best_move.promotion is not None:
                    is_promote = True
                    _, psg_promo = self.get_promo_piece(best_move, board.turn, False)

                # Update board to_square if move is a promotion
                if is_promote:
                    self.psg_board[to_row][to_col] = psg_promo
                # Update the to_square if not a promote move
                else:
                    # Place piece in the move to_square
                    self.psg_board[to_row][to_col] = piece

                self.redraw_board(window)

                board.push(best_move)
                move_cnt += 1

                # Update timer
                engine_timer.update_base()

                # Update game, move from engine
                time_left = engine_timer.base
                if is_book_from_gui:
                    engine_comment = 'book'
                else:
                    engine_comment = ''
                self.update_game(move_cnt, best_move, time_left, engine_comment)

                window.FindElement('_movelist_').Update(disabled=False)
                window.FindElement('_movelist_').Update('')
                window.FindElement('_movelist_').Update(
                    self.game.variations[0], append=True, disabled=True)

                # Change the color of the "fr" and "to" board squares
                self.change_square_color(window, fr_row, fr_col)
                self.change_square_color(window, to_row, to_col)

                is_human_stm = not is_human_stm
                # Engine has done its move

                k1 = 'b_elapse_k'
                k2 = 'b_base_time_k'
                if not self.is_user_white:
                    k1 = 'w_elapse_k'
                    k2 = 'w_base_time_k'

                # Update elapse box
                elapse_str = self.get_time_mm_ss_ms(engine_timer.elapse)
                window.Element(k1).Update(elapse_str)

                # Update remaining time box
                elapse_str = self.get_time_h_mm_ss(engine_timer.base)
                window.Element(k2).Update(elapse_str)

                window.FindElement('_gamestatus_').Update('Mode     Play')

        # Auto-save game
        logging.info('Saving game automatically')
        if is_user_resigns:
            self.game.headers['Result'] = '0-1' if self.is_user_white else '1-0'
            self.game.headers['Termination'] = '{} resigns'.format(
                    'white' if self.is_user_white else 'black')
        elif is_user_wins:
            self.game.headers['Result'] = '1-0' if self.is_user_white else '0-1'
            self.game.headers['Termination'] = 'Adjudication'
        elif is_user_draws:
            self.game.headers['Result'] = '1/2-1/2'
            self.game.headers['Termination'] = 'Adjudication'
        else:
            self.game.headers['Result'] = board.result(claim_draw = True)

        base_h = int(self.human_base_time_ms / 1000)
        inc_h = int(self.human_inc_time_ms / 1000)
        base_e = int(self.engine_base_time_ms / 1000)
        inc_e = int(self.engine_inc_time_ms / 1000)

        if self.is_user_white:
            if self.human_tc_type == 'fischer':
                self.game.headers['WhiteTimeControl'] = str(base_h) + '+' + \
                                                        str(inc_h)
            elif self.human_tc_type == 'delay':
                self.game.headers['WhiteTimeControl'] = str(base_h) + '-' + \
                                                        str(inc_h)
            if self.engine_tc_type == 'fischer':
                self.game.headers['BlackTimeControl'] = str(base_e) + '+' + \
                                                        str(inc_e)
            elif self.engine_tc_type == 'timepermove':
                self.game.headers['BlackTimeControl'] = str(1) + '/' + str(base_e)
        else:
            if self.human_tc_type == 'fischer':
                self.game.headers['BlackTimeControl'] = str(base_h) + '+' + \
                                                        str(inc_h)
            elif self.human_tc_type == 'delay':
                self.game.headers['BlackTimeControl'] = str(base_h) + '-' + \
                                                        str(inc_h)
            if self.engine_tc_type == 'fischer':
                self.game.headers['WhiteTimeControl'] = str(base_e) + '+' + \
                                                        str(inc_e)
            elif self.engine_tc_type == 'timepermove':
                self.game.headers['WhiteTimeControl'] = str(1) + '/' + str(base_e)
        self.save_game()

        if board.is_game_over(claim_draw=True):
            sg.Popup('Game is over.', title=BOX_TITLE,
                     icon=ico_path[platform]['pecg'])

        if is_exit_app:
            window.Close()
            sys.exit(0)

        self.clear_elements(window)

        return False if is_exit_game else is_new_game

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

            # Mode: Neutral
            if button is None:
                logging.info('Quit app from main loop, X is pressed.')
                break

            self.play_game_main_loop(window, engine_id_name)
                                               
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
