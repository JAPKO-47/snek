import curses
from random import randint

s = curses.initscr()
curses.curs_set(0)
sh, sw = s.getmaxyx()
w = curses.newwin(sh, sw, 0, 0)
w.timeout(100)
key = curses.KEY_RIGHT
snake = [[sh//2, sw//4]]
food = [sh//2, sw//2]
w.addch(food[0], food[1], 'F')

while True:
    next_key = w.getch()
    key = key if next_key == -1 else next_key

    head = snake[0]
    if key == curses.KEY_DOWN:
        new_head = [head[0] + 1, head[1]]
    elif key == curses.KEY_UP:
        new_head = [head[0] - 1, head[1]]
    elif key == curses.KEY_LEFT:
        new_head = [head[0], head[1] - 1]
    elif key == curses.KEY_RIGHT:
        new_head = [head[0], head[1] + 1]

    snake.insert(0, new_head)
    if new_head == food:
        food = [randint(1, sh-1), randint(1, sw-1)]
        w.addch(food[0], food[1], 'F')
    else:
        tail = snake.pop()
        w.addch(tail[0], tail[1], ' ')

    if (new_head in snake[1:] or 
        new_head[0] in [0, sh] or 
        new_head[1] in [0, sw]):
        curses.endwin()
        quit()

    w.addch(new_head[0], new_head[1], 'O')
