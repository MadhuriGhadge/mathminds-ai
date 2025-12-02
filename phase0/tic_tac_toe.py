# TIC TAC TOE GAME  

# Print the game board  
def print_board(board):  
    for row in board:  
        print(" | ".join(row))  
        print("-" * 9)  
# Purpose: Displays the 3x3 game board.
# " | ".join(row): Formats each row with | separating the cells.
# "-" * 9: Prints a horizontal line between rows for better visibility.

# Check for a winner  
def check_winner(board, player):  
    # Check rows, columns, and diagonals  
    for i in range(3):  
        if all([board[i][j] == player for j in range(3)]):  # Check rows  
            return True  
        if all([board[j][i] == player for j in range(3)]):  # Check columns  
            return True  
    if all([board[i][i] == player for i in range(3)]):  # Main diagonal  
        return True  
    if all([board[i][2 - i] == player for i in range(3)]):  # Anti-diagonal  
        return True  
    return False  
'''
Checks if the current player (X or O) has won the game.

Check all rows: Each cell in a row contains the player's symbol.
Check all columns: Each cell in a column contains the player's symbol.
Check the main diagonal: board[0][0], board[1][1], board[2][2].
Check the anti-diagonal: board[0][2], board[1][1], board[2][0].
'''

# Check if the board is full  
def is_draw(board):  
    return all([cell != " " for row in board for cell in row])  

'''Determines if the board is full and no moves are left.
Logic:
Flatten the board into a list of cells.
Ensure no cell is empty (" ").
'''

# Main function  
def tic_tac_toe():  
    print("Welcome to Tic Tac Toe!")  
    print("Player 1 is X, Player 2 is O")  

    # Initialize the game board  
    board = [[" " for _ in range(3)] for _ in range(3)]  
    

    current_player = "X"  

    '''
    Prints the game instructions.
    Creates an empty 3x3 board (" ") for the game.
    Sets the first player as "X".
    '''
    
    
    while True:  
        print_board(board)  
        print(f"Player {current_player}'s turn")  

        # Get the player's move  
        try:  
            row, col = map(int, input("Enter row and column (0-2, separated by space): ").split())  
        except ValueError:  
            print("Invalid input! Please enter two numbers separated by space.")  
            continue  

            '''
                        Game Board Display: The current state of the board is printed.
            Input Handling:
            The user enters the row and column indices separated by a space.
            Error Handling: Ensures the input is valid (two numbers).
            '''


        # Check for valid move  
        if row not in range(3) or col not in range(3) or board[row][col] != " ":  
            print("Invalid move! Try again.")  
            continue  

        #Ensures:Row and column are within valid indices (0-2).The selected cell is not already occupied.

        # Make the move  
        board[row][col] = current_player  #Updates the board with the current player's symbol.

        # Check for a winner  
        if check_winner(board, current_player):  
            print_board(board)  
            print(f"Player {current_player} wins!")  
            break  
        #If a winner is found or the board is full, the game ends.

        # Check for a draw  
        if is_draw(board):  
            print_board(board)  
            print("It's a draw!")  
            break  

        # Switch player  #Alternates between "X" and "O".
        current_player = "O" if current_player == "X" else "X"  

# Run the game  
if __name__ == "__main__":  
    tic_tac_toe()