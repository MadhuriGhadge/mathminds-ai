import tkinter as tk
from time import strftime

def update_time():
    current_time = strftime('%H:%M:%S %p') 
    clock_label.config(text=current_time)
    clock_label.after(1000, update_time) 


root = tk.Tk()
root.title("Digital Clock")


clock_label = tk.Label(root, font=('calibri', 40, 'bold'), background='black', foreground='white')
clock_label.pack(anchor='center')

'''
tk.Label(): A widget to display text or images.
font=('calibri', 40, 'bold'): Sets the font style to Calibri, size to 40, and makes it bold.
background='black': Sets the background color to black.
foreground='white': Sets the text color to white.
clock_label.pack(anchor='center'): Positions the label in the center of the window.
'''


update_time()
root.mainloop()

'''
The GUI window is created with a label for displaying the time.
The update_time function retrieves the current time and updates the label every second.
The after method ensures the time keeps updating without blocking the main thread.
When you run this script, you’ll see a window displaying a digital clock that updates in real tim
'''