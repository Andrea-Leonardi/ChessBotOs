from stockfish import Stockfish

sf = Stockfish(path="C:\\Users\\Andrea\\OneDrive\\All\\Andrea\\cose da stampare\\ChessBot\\ChessBotOs\\stockfish-windows-x86-64-universal\\stockfish\\stockfish-windows-x86-64-universal.exe")

#set the skill level of the engine (0-20)
sf.set_elo_rating(1500)
# Print board
print(sf.get_board_visual())

while True:
    print('Enter move (e.g. e2e4)')
    myMove = input()

    # Update the board with user's move (assume legal)
    sf.make_moves_from_current_position([myMove])

    # Get Stockfish's move
    computerMove = sf.get_best_move()
    print("Stockfish plays: ", computerMove)

    # Update the board with computer's move
    sf.make_moves_from_current_position([computerMove])

    print(sf.get_board_visual())