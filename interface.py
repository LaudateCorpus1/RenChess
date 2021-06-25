import copy
from sys import platform
import PySimpleGUI as sg
from globals import *

class RenChessInterface:
    def __init__(self, chess_app):
        self.chess_app = chess_app
        self.menu_elem = None
        self.gui_theme = 'Reddit'
        self.window = None

        # Default board color is brown
        self.sq_light_color = '#F0D9B5'
        self.sq_dark_color = '#B58863'

        # Move highlight, for brown board
        self.move_sq_light_color = '#E8E18E'
        self.move_sq_dark_color = '#B8AF4E'

    def display_play_menu(self):
        menu_def_play = [
                ['&Mode', ['Neutral']],
                ['&Game', ['&New::new_game_k',
                        'Save to My Games::save_game_k',
                        'Save to White Repertoire',
                        'Save to Black Repertoire',
                        'Resign::resign_game_k',
                        'User Wins::user_wins_k',
                        'User Draws::user_draws_k']],
                ['FEN', ['Paste']],
                ['&Engine', ['Go', 'Move Now']],
                ['&Help', ['About']],
        ]
        self.menu_elem.Update(menu_def_play)
    
    def render_square(self, image, key, location):
        """ Returns an RButton (Read Button) with image image """
        if (location[0] + location[1]) % 2:
            color = self.sq_dark_color  # Dark square
        else:
            color = self.sq_light_color
        return sg.RButton('', image_filename=image, size=(1, 1),
                          border_width=0, button_color=('white', color),
                          pad=(0, 0), key=key)

    def change_square_color(self, row, col):
        """ 
        Change the color of a square based on square row and col.
        """
        btn_sq = self.window.FindElement(key=(row, col))
        is_dark_square = True if (row + col) % 2 else False
        bd_sq_color = self.move_sq_dark_color if is_dark_square else \
                      self.move_sq_light_color
        btn_sq.Update(button_color=('white', bd_sq_color))

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

    def create_board(self, is_user_white=True):
        """
        Returns board layout based on color of user. If user is white,
        the white pieces will be at the bottom, otherwise at the top.

        :param is_user_white: user has handling the white pieces
        :return: board layout
        """
        file_char_name = 'abcdefgh'
        self.chess_app.psg_board = copy.deepcopy(initial_board)

        board_layout = []

        if is_user_white:
            # Save the board with black at the top        
            start = 0
            end = 8
            step = 1
        else:
            start = 7
            end = -1
            step = -1
            file_char_name = file_char_name[::-1]

        # Loop through the board and create buttons with images
        for i in range(start, end, step):
            # Row numbers at left of board is blank
            row = [sg.Text(str(8 - i))]
            for j in range(start, end, step):
                piece_image = images[self.chess_app.psg_board[i][j]]
                row.append(self.render_square(piece_image, key=(i, j), location=(i, j)))
            board_layout.append(row)
        row = [sg.Text(' ', size=(3, 1))]
        for c in file_char_name:
            row.append(sg.Text(c, size=(5, 1), font=('Consolas', 12)))
        board_layout.append(row)

        return board_layout

    def build_main_panel_layout(self):
        sg.ChangeLookAndFeel(self.gui_theme)
        sg.SetOptions(margins=(0, 3), border_width=1)

        main_layout = [
            [sg.Button('Puzzles', key='main_puzzles'), 
            sg.Button('Review', key='main_review')]
        ]
        main_page = sg.Column(main_layout, key='main_page', visible=True)        

        # Define board
        board_layout = self.create_board(True)
        board_column = sg.Column(board_layout, key='board_column', visible=True)

        game_column = sg.Column(self.build_game_panel_layout(), key='game_column', visible=True)
        puzzle_column = sg.Column(self.build_puzzle_panel_layout(), key='puzzle_column', visible=False)

        play_layout = [[board_column, game_column, puzzle_column]]
        play_page = sg.Column(play_layout, key='play_page', visible=False)

        layout = [[main_page, play_page]]

        return layout

    def build_game_panel_layout(self):
        """
        Creates interface for board control panels.
        :return: GUI layout
        """ 
        board_controls = [
            [sg.Text('Mode     Neutral', size=(36, 1), font=('Consolas', 10), key='_gamestatus_')],
            [sg.Text('White', size=(7, 1), font=('Consolas', 10)),
             sg.Text('Human', font=('Consolas', 10), key='_White_',
                     size=(24, 1), relief='sunken'),
             sg.Text('', font=('Consolas', 10), key='w_base_time_k',
                     size=(11, 1), relief='sunken'),
             sg.Text('', font=('Consolas', 10), key='w_elapse_k', size=(7, 1),
                     relief='sunken')
             ],
            [sg.Text('Black', size=(7, 1), font=('Consolas', 10)),
             sg.Text('Computer', font=('Consolas', 10), key='_Black_',
                     size=(24, 1), relief='sunken'),
             sg.Text('', font=('Consolas', 10), key='b_base_time_k',
                     size=(11, 1), relief='sunken'),
             sg.Text('', font=('Consolas', 10), key='b_elapse_k', size=(7, 1),
                     relief='sunken')
             ],
            [sg.Text('Adviser', size=(7, 1), font=('Consolas', 10), key='adviser_k',
                     right_click_menu=['Right',
                         ['Start::right_adviser_k', 'Stop::right_adviser_k']]),
             sg.Text('', font=('Consolas', 10), key='advise_info_k', relief='sunken',
                     size=(46,1))],

            [sg.Text('Move list', size=(16, 1), font=('Consolas', 10))],
            [sg.Multiline('', do_not_clear=True, autoscroll=True, size=(52, 8),
                    font=('Consolas', 10), key='_movelist_', disabled=True)],

            [sg.Text('Comment', size=(7, 1), font=('Consolas', 10))],
            [sg.Multiline('', do_not_clear=True, autoscroll=True, size=(52, 3),
                    font=('Consolas', 10), key='comment_k')],

            [sg.Text('BOOK 1, Comp games', size=(26, 1),
                     font=('Consolas', 10),
                     right_click_menu=['Right',
                         ['Show::right_book1_k', 'Hide::right_book1_k']]),
             sg.Text('BOOK 2, Human games',
                     font=('Consolas', 10),
                     right_click_menu=['Right',
                         ['Show::right_book2_k', 'Hide::right_book2_k']])],
            [sg.Multiline('', do_not_clear=True, autoscroll=False, size=(23, 4),
                    font=('Consolas', 10), key='polyglot_book1_k', disabled=True),
             sg.Multiline('', do_not_clear=True, autoscroll=False, size=(25, 4),
                    font=('Consolas', 10), key='polyglot_book2_k', disabled=True)],

            [sg.Text('Opponent Search Info', font=('Consolas', 10), size=(30, 1),
                     right_click_menu=['Right',
                         ['Show::right_search_info_k', 'Hide::right_search_info_k']])],
            [sg.Text('', key='search_info_all_k', size=(55, 1),
                     font=('Consolas', 10), relief='sunken')],
        ]
        
        return board_controls

    def build_puzzle_panel_layout(self):
        """
        Creates interface for playing puzzles.
        
        :return: GUI layout
        """       

        layout = [
            [sg.Text('', size=(50, 1), font=('Consolas', 16), key='puzzle_title')],
            [sg.Text('', size=(50, 1), font=('Consolas', 12), key='puzzle_instruction')],
            [sg.Text('', size=(50, 1), font=('Consolas', 16), key='puzzle_comment')],
            [sg.Button('Next Puzzle', disabled=True, key='puzzle_next')],
            [sg.Table(values=[["", "", ""]], headings=["", "White", "Black"], col_widths=[3, 10, 10], auto_size_columns=False,
                    num_rows=5, row_height=20, key='puzzle_moves')],
            [sg.Button('Back to Main', disabled=False, key='back_to_main')]
        ]

        return layout

    def show_puzzle_number_dialog(self):
        puzzle_count = -1
        win_title = 'Number of Puzzles'
        layout = [
            [sg.T('Number of Puzzles', size=(16, 1)),
                sg.Input(10, key='puzzle_number', size=(8, 1))],            
            [sg.OK(), sg.Cancel()]
        ]

        self.window.Disable()
        w = sg.Window(win_title, layout, icon=ico_path[platform]['pecg'])
        while True:
            e, v = w.Read(timeout=10)
            if e is None:
                break
            if e == 'Cancel':
                break
            if e == 'OK':
                puzzle_count = int(v['puzzle_number'])
                break
        w.Close()
        self.window.Enable()
        return puzzle_count

    def create_default_window(self):
        layout = self.build_main_panel_layout()

        # Use white layout as default window
        self.window = sg.Window('{} {}'.format(APP_NAME, APP_VERSION),
                           layout, size=(900, 600),
                           default_button_element_size=(12, 1),
                           auto_size_buttons=False,
                           icon=ico_path[platform]['pecg'])
        return self.window

    def create_new_window(self, flip=False):
        """ Close the window param just before turning the new window """

        loc = self.window.CurrentLocation()
        self.window.Disable()
        if flip:
            self.chess_app.is_user_white = not self.chess_app.is_user_white

        layout = self.build_game_panel_layout(self.chess_app.is_user_white)

        w = sg.Window('{} {}'.format(APP_NAME, APP_VERSION),
            layout,
            default_button_element_size=(12, 1),
            auto_size_buttons=False,
            location=(loc[0], loc[1]),
            icon=ico_path[platform]['pecg'])

        # Initialize White and black boxes
        while True:
            button, value = w.Read(timeout=50)
            self.update_labels_and_game_tags(w, human=self.chess_app.username)
            break

        self.window.Close()
        self.window = w
        return w

    def update_labels_and_game_tags(self, window, human='Human'):
        """ Update player names """
        engine_id = self.chess_app.opp_id_name
        game = self.chess_app.game
        if self.chess_app.is_user_white:
            window.FindElement('_White_').Update(human)
            window.FindElement('_Black_').Update(engine_id)
            game.headers['White'] = human
            game.headers['Black'] = engine_id
        else:
            window.FindElement('_White_').Update(engine_id)
            window.FindElement('_Black_').Update(human)
            game.headers['White'] = engine_id
            game.headers['Black'] = human

    def redraw_board(self):
        """
        Redraw board at start and afte a move.

        :param window:
        :return:
        """
        for i in range(8):
            for j in range(8):
                color = self.sq_dark_color if (i + j) % 2 else \
                        self.sq_light_color
                piece_image = images[self.chess_app.psg_board[i][j]]
                elem = self.window.FindElement(key=(i, j))
                elem.Update(button_color=('white', color),
                            image_filename=piece_image, )

    def show_puzzle_page(self):
        self.window['main_page'].Update(visible=False)                
        self.window['game_column'].Update(visible=False)
        self.window['puzzle_column'].Update(visible=True)
        self.window['play_page'].Update(visible=True)

    def show_main_page(self):                  
        self.window['play_page'].Update(visible=False)
        self.window['main_page'].Update(visible=True)      