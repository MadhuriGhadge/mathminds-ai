import random

# Initialize the game board dimensions
rows = 6
cols = 7
gameBoard = [[0 for _ in range(cols)] for _ in range(rows)]

def printGameBoard():
    """Prints the Connect Four game board with improved accuracy."""
    print("\n   A   B   C   D   E   F   G")  # Column labels
    
    for x in range(rows):  # Loop through each row
        print("  +" + "---+" * cols)  # Top boundary of each row
        print(f"{x} |", end="")  # Row number
        for y in range(cols):  # Loop through each column
            if gameBoard[x][y] == 1:
                print(" 🔵 |", end="")  # Player's chip
            elif gameBoard[x][y] == 2:
                print(" 🔴 |", end="")  # CPU's chip
            else:
                print("   |", end="")  # Empty space
        print()  # Move to the next line
    
    print("  +" + "---+" * cols)  # Bottom boundary of the board



def modifyTurn(spacePicked, turn):
    """Modifies the board by placing a player's chip at the picked space."""
    gameBoard[spacePicked[0]][spacePicked[1]] = turn

def checkForWinner(chip):
    """Checks for a winner by verifying horizontal, vertical, and diagonal connections."""
    # Check horizontal spaces
    for x in range(rows):
        for y in range(cols - 3):
            if (gameBoard[x][y] == chip and gameBoard[x][y + 1] == chip and
                gameBoard[x][y + 2] == chip and gameBoard[x][y + 3] == chip):
                return True

    # Check vertical spaces
    for y in range(cols):
        for x in range(rows - 3):
            if (gameBoard[x][y] == chip and gameBoard[x + 1][y] == chip and
                gameBoard[x + 2][y] == chip and gameBoard[x + 3][y] == chip):
                return True

    # Check diagonal (down-right)
    for x in range(rows - 3):
        for y in range(cols - 3):
            if (gameBoard[x][y] == chip and gameBoard[x + 1][y + 1] == chip and
                gameBoard[x + 2][y + 2] == chip and gameBoard[x + 3][y + 3] == chip):
                return True

    # Check diagonal (up-right)
    for x in range(3, rows):
        for y in range(cols - 3):
            if (gameBoard[x][y] == chip and gameBoard[x - 1][y + 1] == chip and
                gameBoard[x - 2][y + 2] == chip and gameBoard[x - 3][y + 3] == chip):
                return True

    return False

def get_column_input():
    """Prompts the player for column input and validates it."""
    while True:
        print("Available Columns: ", end="")
        for col in range(cols):
            if gameBoard[0][col] == 0:
                print(chr(col + ord('A')), end=" ")
        print()
        
        col_input = input("Choose a column (A-G): ").strip().upper()
        if col_input in "ABCDEFG":
            col = ord(col_input) - ord('A')
            if gameBoard[0][col] == 0:
                return col
            print("That column is full. Try a different one.")
        else:
            print("Invalid input. Please enter a letter between A and G.")


def make_move(col, player):
    """Finds the next available row in the column and returns the move."""
    for row in reversed(range(rows)):
        if gameBoard[row][col] == 0:  # Check for an empty slot
            return row, col  # Return the available position
    return None  # If no available row is found (column is full)


def cpu_move():
    """Smarter CPU move: blocks player win or chooses a random column."""
    # Check for winning move for CPU
    for col in range(cols):
        if gameBoard[0][col] == 0:
            row, _ = make_move(col, 2)
            modifyTurn((row, col), 2)
            if checkForWinner(2):
                return row, col
            modifyTurn((row, col), 0)  # Undo move if not winning

    # Check if Player is about to win and block
    for col in range(cols):
        if gameBoard[0][col] == 0:
            row, _ = make_move(col, 1)
            modifyTurn((row, col), 1)
            if checkForWinner(1):
                modifyTurn((row, col), 2)  # Block player
                return row, col
            modifyTurn((row, col), 0)  # Undo move if no immediate win

    # Otherwise, make a random move
    while True:
        col = random.randint(0, cols - 1)
        if gameBoard[0][col] == 0:
            return make_move(col, 2)


def play_game():
    """Main game loop: Player (🔵) vs CPU (🔴)."""
    print("Welcome to Connect Four! You are 🔵 and the CPU is 🔴.")
    printGameBoard()

    while True:
        # Player's turn
        print("\nYour turn, Player 🔵:")
        col = get_column_input()
        row, col = make_move(col, 1)
        modifyTurn((row, col), 1)
        printGameBoard()

        if checkForWinner(1):
            print("Congratulations! You win! 🎉")
            break

        # Check for draw
        if all(gameBoard[0][col] != 0 for col in range(cols)):
            print("It's a draw!")
            break

        # CPU's turn
        print("\nCPU's turn, 🔴:")
        row, col = cpu_move()
        modifyTurn((row, col), 2)
        printGameBoard()

        if checkForWinner(2):
            print("CPU wins! Better luck next time. 😢")
            break

        # Check for draw
        if all(gameBoard[0][col] != 0 for col in range(cols)):
            print("It's a draw!")
            break

# Run the game
if __name__ == "__main__":
    play_game()
