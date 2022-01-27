import os
import sys

import pygame

WHITE = 1
BLACK = 2
WIDTH = HEIGHT = 512
NUMBER = 8
TILE_SIZE = WIDTH // NUMBER
PIECE_IMAGES = {}
MAX_FPS = 15
pygame.init()
pygame.mixer.music.load("data/sound.mp3")
pygame.mixer.music.play(-1)
screen = pygame.display.set_mode((WIDTH, HEIGHT))
colors = [pygame.Color('light gray'), pygame.Color('dark green')]
clock = pygame.time.Clock()


def load_image(name, color_key=None):
    fullname = os.path.join('data', name)
    try:
        image = pygame.image.load(fullname)
    except pygame.error as message:
        print('Не удаётся загрузить:', name)
        raise SystemExit(message)
    image = image.convert_alpha()
    if color_key is not None:
        if color_key == -1:
            color_key = image.get_at((0, 0))
        image.set_colorkey(color_key)
    return image


def load_piece_images():
    pieces = ['wP', 'wR', 'wN', 'wB', 'wQ', 'wK', 'bP', 'bR', 'bN', 'bB', 'bQ', 'bK']
    for piece in pieces:
        PIECE_IMAGES[piece] = pygame.transform.scale(load_image(piece + '.png', -1), (TILE_SIZE, TILE_SIZE))


class Board:

    def __init__(self, screen):
        self.screen = screen
        self.white_to_move = True
        self.field = [
            ['bR', 'bN', 'bB', 'bQ', 'bK', 'bB', 'bN', 'bR'],
            ['bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP', 'bP'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['--', '--', '--', '--', '--', '--', '--', '--'],
            ['wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP', 'wP'],
            ['wR', 'wN', 'wB', 'wQ', 'wK', 'wB', 'wN', 'wR'],
        ]
        self.move_log = []
        self.move_functions = {'P': self.get_pawn_moves, 'R': self.get_rook_moves, 'N': self.get_knight_moves,
                               'B': self.get_bishop_moves, 'Q': self.get_queen_moves, 'K': self.get_king_moves}

        self.white_king_location = (7, 4)
        self.black_king_location = (0, 4)

        self.checkmate = False
        self.stale_mate = False

        self.enpassant_possible = ()

        self.current_castling_rights = CastleRights(True, True, True, True)
        self.castle_rights_log = [CastleRights(self.current_castling_rights.wks, self.current_castling_rights.bks,
                                               self.current_castling_rights.wqs, self.current_castling_rights.bqs)]

    '''darkslategray1 cyan3'''

    def draw_board(self, screen):
        for row in range(NUMBER):
            for col in range(NUMBER):
                color = colors[((row + col) % 2)]
                pygame.draw.rect(screen, color, pygame.Rect(col * TILE_SIZE, row * TILE_SIZE, TILE_SIZE, TILE_SIZE))

    def draw_pieces(self, screen):
        for row in range(NUMBER):
            for col in range(NUMBER):
                piece = self.field[row][col]
                if piece != '--':
                    screen.blit(PIECE_IMAGES[piece], pygame.Rect(col * TILE_SIZE, row * TILE_SIZE, TILE_SIZE, TILE_SIZE
                                                                 ))

    def highlight_squares(self, screen, selected_square, valid_moves):
        if selected_square != ():
            row, col = selected_square
            if self.field[row][col][0] == ('w' if self.white_to_move else 'b'):
                s = pygame.Surface((TILE_SIZE, TILE_SIZE))
                s.set_alpha(100)
                s.fill(pygame.Color('blue'))
                screen.blit(s, (col * TILE_SIZE, row * TILE_SIZE))
                for move in valid_moves:
                    if move.start_row == row and move.start_col == col:
                        s.fill(pygame.Color('yellow'))
                        screen.blit(s, (move.end_col * TILE_SIZE, move.end_row * TILE_SIZE))

    def move_animation(self, move, screen, clock):
        delta_row = move.end_row - move.start_row
        delta_col = move.end_col - move.start_col
        frames_per_square = 10
        frames_count = (abs(delta_row) + abs(delta_col)) * frames_per_square
        for frame in range(frames_count + 1):
            row, col = (move.start_row + delta_row * frame / frames_count,
                        move.start_col + delta_col * frame / frames_count)
            self.draw_board(screen)
            self.draw_pieces(screen)

            color = colors[(move.end_row + move.end_col) % 2]
            end_square = pygame.Rect(move.end_col * TILE_SIZE, move.end_row * TILE_SIZE, TILE_SIZE, TILE_SIZE)
            pygame.draw.rect(screen, color, end_square)
            if move.piece_captured != '--':
                screen.blit(PIECE_IMAGES[move.piece_captured], end_square)
            screen.blit(PIECE_IMAGES[move.piece_moved],
                        pygame.Rect(col * TILE_SIZE, row * TILE_SIZE, TILE_SIZE, TILE_SIZE))
            pygame.display.flip()
            clock.tick(60)

    def move(self, move):
        self.field[move.start_row][move.start_col] = '--'
        self.field[move.end_row][move.end_col] = move.piece_moved
        self.move_log.append(move)
        self.white_to_move = not self.white_to_move
        if move.piece_moved == 'wK':
            self.white_king_location = (move.end_row, move.end_col)
        elif move.piece_moved == 'bK':
            self.black_king_location = (move.end_row, move.end_col)

        if move.is_pawn_promoted:
            self.field[move.end_row][move.end_col] = move.piece_moved[0] + 'Q'

        if move.is_enpassant_move:
            self.field[move.start_row][move.end_col] = '--'

        if move.piece_moved[1] == 'P' and abs(move.end_row - move.start_row) == 2:
            self.enpassant_possible = ((move.start_row + move.end_row) // 2, move.start_col)
        else:
            self.enpassant_possible = ()

        if move.is_castle_move:
            if move.end_col - move.start_col == 2:
                self.field[move.end_row][move.end_col - 1] = self.field[move.end_row][move.end_col + 1]
                self.field[move.end_row][move.end_col + 1] = '--'
            else:
                self.field[move.end_row][move.end_col + 1] = self.field[move.end_row][move.end_col - 2]
                self.field[move.end_row][move.end_col - 2] = '--'

        self.update_castle_rights(move)
        self.castle_rights_log.append(CastleRights(self.current_castling_rights.wks, self.current_castling_rights.bks,
                                                   self.current_castling_rights.wqs, self.current_castling_rights.bqs))

    def cancel_move(self):
        if len(self.move_log) != 0:
            move = self.move_log.pop()
            self.field[move.start_row][move.start_col] = move.piece_moved
            self.field[move.end_row][move.end_col] = move.piece_captured
            self.white_to_move = not self.white_to_move
            if move.piece_moved == 'wK':
                self.white_king_location = (move.start_row, move.start_col)
            elif move.piece_moved == 'bK':
                self.black_king_location = (move.start_row, move.start_col)
            if move.is_enpassant_move:
                self.field[move.end_row][move.end_col] = '--'
                self.field[move.start_row][move.end_col] = move.piece_captured
                self.enpassant_possible = (move.end_row, move.end_col)
            if move.piece_moved[1] == 'P' and abs(move.start_row - move.end_row) == 2:
                self.enpassant_possible = ()

            self.castle_rights_log.pop()
            new_rights = self.castle_rights_log[-1]
            self.current_castling_rights = CastleRights(new_rights.wks, new_rights.bks, new_rights.wqs, new_rights.bks)
            if move.is_castle_move:
                if move.end_col - move.start_col == 2:
                    self.field[move.end_row][move.end_col + 1] = self.field[move.end_row][move.end_col - 1]
                    self.field[move.end_row][move.end_col - 1] = '--'
                else:
                    self.field[move.end_row][move.end_col - 2] = self.field[move.end_row][move.end_col + 1]
                    self.field[move.end_row][move.end_col + 1] = '--'

    def update_castle_rights(self, move):
        if move.piece_moved == 'wK':
            self.current_castling_rights.wks = False
            self.current_castling_rights.wqs = False
        elif move.piece_moved == 'bK':
            self.current_castling_rights.bks = False
            self.current_castling_rights.bqs = False
        elif move.piece_moved == 'wR':
            if move.start_row == 7:
                if move.start_col == 0:
                    self.current_castling_rights.wqs = False
                elif move.start_col == 7:
                    self.current_castling_rights.wks = False
        elif move.piece_moved == 'bR':
            if move.start_row == 0:
                if move.start_col == 0:
                    self.current_castling_rights.bqs = False
                elif move.start_col == 7:
                    self.current_castling_rights.bks = False

    def get_valid_moves(self):
        temp_enpassant_possible = self.enpassant_possible
        temp_castle_rights = CastleRights(self.current_castling_rights.wks, self.current_castling_rights.bks,
                                          self.current_castling_rights.wqs, self.current_castling_rights.bqs)
        moves = self.get_all_possible_moves()
        if self.white_to_move:
            self.get_castle_moves(self.white_king_location[0], self.white_king_location[1], moves)
        else:
            self.get_castle_moves(self.black_king_location[0], self.black_king_location[1], moves)

        for i in range(len(moves) - 1, -1, -1):
            self.move(moves[i])

            self.white_to_move = not self.white_to_move
            if self.in_check():
                moves.remove(moves[i])
            self.white_to_move = not self.white_to_move
            self.cancel_move()
        if len(moves) == 0:
            if self.in_check():
                self.checkmate = True
            else:
                self.stale_mate = True
        else:
            self.checkmate = False
            self.stale_mate = False

        self.enpassant_possible = temp_enpassant_possible
        self.current_castling_rights = temp_castle_rights
        return moves

    def in_check(self):
        if self.white_to_move:
            return self.square_under_attack(self.white_king_location[0], self.white_king_location[1])
        else:
            return self.square_under_attack(self.black_king_location[0], self.black_king_location[1])

    def square_under_attack(self, row, col):
        self.white_to_move = not self.white_to_move
        opp_moves = self.get_all_possible_moves()
        self.white_to_move = not self.white_to_move
        for move in opp_moves:
            if move.end_row == row and move.end_col == col:
                return True
        return False

    def get_all_possible_moves(self):
        moves = []
        for row in range(len(self.field)):
            for col in range(len(self.field[row])):
                turn = self.field[row][col][0]
                if (turn == 'w' and self.white_to_move) or (turn == 'b' and not self.white_to_move):
                    piece = self.field[row][col][1]
                    self.move_functions[piece](row, col, moves)
        return moves

    def get_pawn_moves(self, row, col, moves):
        if self.white_to_move:
            if self.field[row - 1][col] == '--':
                moves.append(Move((row, col), (row - 1, col), self.field))
                if row == 6 and self.field[row - 2][col] == '--':
                    moves.append(Move((row, col), (row - 2, col), self.field))
            if col - 1 >= 0:
                if self.field[row - 1][col - 1][0] == 'b':
                    moves.append(Move((row, col), (row - 1, col - 1), self.field))
                elif (row - 1, col - 1) == self.enpassant_possible:
                    moves.append(Move((row, col), (row - 1, col - 1), self.field, is_enpassant_move=True))
            if col + 1 <= 7:
                if self.field[row - 1][col + 1][0] == 'b':
                    moves.append(Move((row, col), (row - 1, col + 1), self.field))
                elif (row - 1, col + 1) == self.enpassant_possible:
                    moves.append(Move((row, col), (row - 1, col + 1), self.field, is_enpassant_move=True))
        else:
            if self.field[row + 1][col] == '--':
                moves.append(Move((row, col), (row + 1, col), self.field))
                if row == 1 and self.field[row + 2][col] == '--':
                    moves.append(Move((row, col), (row + 2, col), self.field))
            if col - 1 >= 0:
                if self.field[row + 1][col - 1][0] == 'w':
                    moves.append(Move((row, col), (row + 1, col - 1), self.field))
                elif (row + 1, col - 1) == self.enpassant_possible:
                    moves.append(Move((row, col), (row + 1, col - 1), self.field, is_enpassant_move=True))
            if col + 1 <= 7:
                if self.field[row + 1][col + 1][0] == 'w':
                    moves.append(Move((row, col), (row + 1, col + 1), self.field))
                elif (row + 1, col + 1) == self.enpassant_possible:
                    moves.append(Move((row, col), (row + 1, col + 1), self.field, is_enpassant_move=True))

    def get_rook_moves(self, row, col, moves):
        directions = ((-1, 0), (0, -1), (1, 0), (0, 1))
        enemy_color = 'b' if self.white_to_move else 'w'
        for d in directions:
            for i in range(1, 8):
                end_row = row + (d[0] * i)
                end_col = col + (d[1] * i)
                if 0 <= end_row <= 7 and 0 <= end_col <= 7:
                    end_piece = self.field[end_row][end_col]
                    if end_piece == '--':
                        moves.append(Move((row, col), (end_row, end_col), self.field))
                    elif end_piece[0] == enemy_color:
                        moves.append(Move((row, col), (end_row, end_col), self.field))
                        break
                    else:
                        break
                else:
                    break

    def get_knight_moves(self, row, col, moves):
        directions = ((-2, -1), (-2, 1), (2, -1), (2, 1), (1, 2), (1, -2), (-1, 2), (-1, -2))
        ally_color = 'w' if self.white_to_move else 'b'
        for d in directions:
            end_row = row + d[0]
            end_col = col + d[1]
            if 0 <= end_row <= 7 and 0 <= end_col <= 7:
                end_piece = self.field[end_row][end_col]
                if end_piece[0] != ally_color:
                    moves.append(Move((row, col), (end_row, end_col), self.field))

    def get_queen_moves(self, row, col, moves):
        self.get_rook_moves(row, col, moves)
        self.get_bishop_moves(row, col, moves)

    def get_bishop_moves(self, row, col, moves):
        directions = ((-1, -1), (1, -1), (1, 1), (-1, 1))
        enemy_color = 'b' if self.white_to_move else 'w'
        for d in directions:
            for i in range(1, 8):
                end_row = row + (d[0] * i)
                end_col = col + (d[1] * i)
                if 0 <= end_row <= 7 and 0 <= end_col <= 7:
                    end_piece = self.field[end_row][end_col]
                    if end_piece == '--':
                        moves.append(Move((row, col), (end_row, end_col), self.field))
                    elif end_piece[0] == enemy_color:
                        moves.append(Move((row, col), (end_row, end_col), self.field))
                        break
                    else:
                        break
                else:
                    break

    def get_king_moves(self, row, col, moves):
        directions = ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
        ally_color = 'w' if self.white_to_move else 'b'
        for i in range(8):
            end_row = row + directions[i][0]
            end_col = col + directions[i][1]
            if 0 <= end_row <= 7 and 0 <= end_col <= 7:
                end_piece = self.field[end_row][end_col]
                if end_piece[0] != ally_color:
                    moves.append(Move((row, col), (end_row, end_col), self.field))

    def get_castle_moves(self, row, col, moves):
        if self.in_check():
            return
        if (self.white_to_move and self.current_castling_rights.wks) or \
                (not self.white_to_move and self.current_castling_rights.bks):
            self.get_kingside_castle_moves(row, col, moves)
        if (self.white_to_move and self.current_castling_rights.wqs) or \
                (not self.white_to_move and self.current_castling_rights.bqs):
            self.get_queenside_castle_moves(row, col, moves)

    def get_kingside_castle_moves(self, row, col, moves):
        if self.field[row][col + 1] == '--' and self.field[row][col + 2] == '--':
            if not self.square_under_attack(row, col + 1) and not self.square_under_attack(row, col + 2):
                moves.append(Move((row, col), (row, col + 2), self.field, is_castle_move=True))

    def get_queenside_castle_moves(self, row, col, moves):
        if self.field[row][col - 1] == '--' and self.field[row][col - 2] == '--':
            if not self.square_under_attack(row, col - 1) and not self.square_under_attack(row, col - 2):
                moves.append(Move((row, col), (row, col - 2), self.field, is_castle_move=True))


class CastleRights:

    def __init__(self, wks, bks, wqs, bqs):
        self.wks = wks
        self.bks = bks
        self.wqs = wqs
        self.bqs = bqs


class Move:
    ranks_to_rows = {'1': 7, '2': 6, '3': 5, '4': 4,
                     '5': 3, '6': 2, '7': 1, '8': 0}
    rows_to_ranks = {v: k for k, v in ranks_to_rows.items()}

    files_to_cols = {'a': 0, 'b': 1, 'c': 2, 'd': 3, 'e': 4,
                     'f': 5, 'g': 6, 'h': 7}
    cols_to_files = {v: k for k, v in files_to_cols.items()}

    def __init__(self, start_sq, end_sq, board, is_enpassant_move=False, is_castle_move=False):
        self.start_row = start_sq[0]
        self.start_col = start_sq[1]
        self.end_row = end_sq[0]
        self.end_col = end_sq[1]
        self.piece_moved = board[self.start_row][self.start_col]
        self.piece_captured = board[self.end_row][self.end_col]
        self.move_ID = self.start_row * 1000 + self.start_col * 100 + self.end_row * 10 + self.end_col
        self.is_pawn_promoted = (self.piece_moved == 'wP' and self.end_row == 0) or \
                                (self.piece_moved == 'bP' and self.end_row == 7)

        self.is_enpassant_move = is_enpassant_move
        if self.is_enpassant_move:
            self.piece_captured = 'wP' if self.piece_moved == 'bP' else 'bP'

        self.is_castle_move = is_castle_move

    def __eq__(self, other):
        if isinstance(other, Move):
            return self.move_ID == other.move_ID

    def get_chess_notation(self):
        return self.piece_moved[1] + self.get_rank_file(self.start_row, self.start_col) + \
               self.get_rank_file(self.end_row, self.end_col)

    def get_rank_file(self, row, col):
        return self.cols_to_files[col] + self.rows_to_ranks[row]


def draw_text(screen, text):
    font = pygame.font.SysFont('Helvitca', 32, True, False)
    text_object = font.render(text, 0, pygame.Color('black'))
    text_pos = pygame.Rect(0, 0, WIDTH, HEIGHT).move((WIDTH / 2 - text_object.get_width() / 2),
                                                     (HEIGHT / 2 - text_object.get_height() / 2))
    screen.blit(text_object, text_pos)


def terminate():
    pygame.quit()
    sys.exit


def start_screen():
    intro_text = ["Правила:", "",
                  "Для перемещения фигуры нажмите на неё,", "",
                  "А затем нажмите на поле,", "",
                  "на которое хотите походить", "",
                  "Для изменения цвета доски,", "",
                  "Нажмите 1, 2 или 3", "",
                  "Остальные правила такие же,", "",
                  "как в стандартных шахматах"]

    fon = pygame.transform.scale(load_image('i.jpg'), (WIDTH, HEIGHT))
    screen.blit(fon, (0, 0))
    font = pygame.font.Font(None, 30)
    text_coord = 50
    for line in intro_text:
        string_rendered = font.render(line, 1, pygame.Color('black'))
        intro_rect = string_rendered.get_rect()
        text_coord += 10
        intro_rect.top = text_coord
        intro_rect.x = 10
        text_coord += intro_rect.height
        screen.blit(string_rendered, intro_rect)

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                terminate()
            elif event.type == pygame.KEYDOWN or \
                    event.type == pygame.MOUSEBUTTONDOWN:
                return
        pygame.display.flip()
        clock.tick(MAX_FPS)


start_screen()


def main():
    global colors
    pygame.init()
    pygame.display.set_caption('Chess')
    clock = pygame.time.Clock()
    screen.fill(pygame.Color('white'))
    board = Board(screen)
    load_piece_images()
    valid_moves = board.get_valid_moves()
    move_made = False
    animate = False
    game_over = False

    running = True

    selected_square = ()
    player_clicks = []

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if not game_over:
                    position = pygame.mouse.get_pos()
                    col = position[0] // TILE_SIZE
                    row = position[1] // TILE_SIZE

                    if selected_square == (row, col):
                        selected_square = ()
                        player_clicks = []
                    else:
                        selected_square = (row, col)
                        player_clicks.append(selected_square)
                    if len(player_clicks) == 2:
                        move = Move(player_clicks[0], player_clicks[1], board.field)
                        print(move.get_chess_notation())
                        for i in range(len(valid_moves)):
                            if move == valid_moves[i]:
                                board.move(valid_moves[i])
                                move_made = True
                                animate = True
                                selected_square = ()
                                player_clicks = []
                        if not move_made:
                            player_clicks = [selected_square]
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_z:
                    board.cancel_move()
                    move_made = True
                    animate = False
                if event.key == pygame.K_r:
                    board = Board(screen)
                    valid_moves = board.get_valid_moves()
                    move_made = False
                    animate = False
                    game_over = False
                if event.key == pygame.K_1:
                    colors = [pygame.Color('light gray'), pygame.Color('dark green')]
                if event.key == pygame.K_2:
                    colors = [pygame.Color('darkslategray1'), pygame.Color('cyan3')]
                if event.key == pygame.K_3:
                    colors = [pygame.Color('darkorchid3'), pygame.Color('violetred4')]

        if move_made:
            if animate:
                board.move_animation(board.move_log[-1], screen, clock)
            valid_moves = board.get_valid_moves()
            move_made = False
            animate = False
        board.draw_board(screen)
        board.highlight_squares(screen, selected_square, valid_moves)
        board.draw_pieces(screen)
        if board.checkmate:
            game_over = True
            if not board.white_to_move:
                draw_text(screen, 'white wins')
            else:
                draw_text(screen, 'black wins')
        elif board.stale_mate:
            game_over = True
            draw_text(screen, 'Stalemate')
        clock.tick(MAX_FPS)
        pygame.display.flip()
    pygame.quit()


if __name__ == '__main__':
    main()
