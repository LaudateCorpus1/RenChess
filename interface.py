import copy
from sys import platform
import PySimpleGUI as sg
from globals import *

class RenChessInterface:
    def __init__(self, chess_app):
        self.chess_app = chess_app
        self.menu_elem = None
        self.gui_theme = 'Reddit'

    def render_square(self, image, key, location):
        """ Returns an RButton (Read Button) with image image """
        if (location[0] + location[1]) % 2:
            color = self.chess_app.sq_dark_color  # Dark square
        else:
            color = self.chess_app.sq_light_color
        return sg.RButton('', image_filename=image, size=(1, 1),
                          border_width=0, button_color=('white', color),
                          pad=(0, 0), key=key)

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

    def build_game_panel_layout(self, is_user_white=True):
        """
        Creates all elements for the GUI, including the board layout.

        :param is_user_white: if user is white, the white pieces are
        oriented such that the white pieces are at the bottom.
        :return: GUI layout
        """
        sg.ChangeLookAndFeel(self.gui_theme)
        sg.SetOptions(margins=(0, 3), border_width=1)

        # Define board
        board_layout = self.create_board(is_user_white)

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

        board_tab = [[sg.Column(board_layout)]]

        self.menu_elem = sg.Menu(menu_def_neutral, tearoff=False)

        # White board layout, mode: Neutral
        layout = [
                [self.menu_elem],
                [sg.Column(board_tab), sg.Column(board_controls)]
        ]

        return layout

    def create_default_window(self):
        layout = self.build_game_panel_layout(True)

        # Use white layout as default window
        w = sg.Window('{} {}'.format(APP_NAME, APP_VERSION),
                           layout, default_button_element_size=(12, 1),
                           auto_size_buttons=False,
                           icon=ico_path[platform]['pecg'])
        return w

    def create_new_window(self, window, flip=False):
        """ Close the window param just before turning the new window """

        loc = window.CurrentLocation()
        window.Disable()
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

        window.Close()
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