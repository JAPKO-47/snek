from __future__ import annotations
import pygame
import random
import json
import math
import os
import heapq
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict

CONFIG = {
    'CELL_SIZE': 20,
    'GRID_W': 32,
    'GRID_H': 24,
    'FPS': 60,
    'TICKS_PER_MOVE': 8,
    'START_LENGTH': 4,
    'HIGH_SCORE_FILE': 'snake_highscores.json',
}

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (120, 120, 120)
GREEN = (40, 200, 40)
DARK_GREEN = (10, 140, 10)
RED = (220, 40, 40)
BLUE = (40, 120, 220)
YELLOW = (245, 220, 60)
ORANGE = (255, 140, 40)
PURPLE = (160, 80, 200)

POWER_TYPES = ['speed', 'slow', 'invincible', 'shrink', 'multiplier']

Point = Tuple[int, int]

def clamp(v, a, b):
    return max(a, min(b, v))

def load_highscores(path: str) -> Dict:
    if not os.path.exists(path):
        return {'highscore': 0}
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return {'highscore': 0}

def save_highscores(path: str, data: Dict):
    try:
        with open(path, 'w') as f:
            json.dump(data, f)
    except Exception:
        pass

def heuristic(a: Point, b: Point) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def astar(start: Point, goal: Point, grid_w: int, grid_h: int, blocked: set, wrap: bool=False) -> Optional[List[Point]]:
    open_set = []
    heapq.heappush(open_set, (0 + heuristic(start, goal), 0, start, None))
    came_from = {}
    gscore = {start: 0}
    while open_set:
        _, g, current, parent = heapq.heappop(open_set)
        if current == goal:
            path = [current]
            while parent:
                path.append(parent)
                parent = came_from.get(parent)
            return path[::-1]
        if current in came_from:
            continue
        came_from[current] = parent
        x, y = current
        neighbors = [((x+1)%grid_w, y), ((x-1)%grid_w, y), (x,(y+1)%grid_h), (x,(y-1)%grid_h)] if wrap else [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]
        for nx, ny in neighbors:
            if not wrap and (nx < 0 or nx >= grid_w or ny < 0 or ny >= grid_h):
                continue
            if (nx, ny) in blocked and (nx, ny) != goal:
                continue
            tentative = g + 1
            if tentative < gscore.get((nx, ny), 1e9):
                gscore[(nx, ny)] = tentative
                f = tentative + heuristic((nx, ny), goal)
                heapq.heappush(open_set, (f, tentative, (nx, ny), current))
    return None

@dataclass
class Food:
    pos: Point
    value: int = 1

@dataclass
class PowerUp:
    pos: Point
    kind: str
    duration_ticks: int

@dataclass
class Obstacle:
    pos: Point

@dataclass
class Snake:
    body: List[Point]
    direction: Point
    color: Tuple[int, int, int]
    alive: bool = True
    grow_pending: int = 0
    invincible_ticks: int = 0
    move_tick_counter: int = 0
    speed_modifier: float = 1.0
    def head(self) -> Point:
        return self.body[0]
    def step(self, next_pos: Point, grow: bool=False):
        self.body.insert(0, next_pos)
        if not grow and self.grow_pending <= 0:
            self.body.pop()
        else:
            if self.grow_pending > 0:
                self.grow_pending -= 1
    def change_dir(self, new_dir: Point):
        if (new_dir[0] * -1, new_dir[1] * -1) == self.direction and len(self.body) > 1:
            return
        self.direction = new_dir
    def collides(self, pt: Point) -> bool:
        return pt in self.body

class SnakeGame:
    def __init__(self):
        pygame.init()
        self.cell = CONFIG['CELL_SIZE']
        self.grid_w = CONFIG['GRID_W']
        self.grid_h = CONFIG['GRID_H']
        self.width = self.grid_w * self.cell
        self.height = self.grid_h * self.cell
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption('Advanced Snake')
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('consolas', 18)
        self.large_font = pygame.font.SysFont('consolas', 28)
        self.highscores = load_highscores(CONFIG['HIGH_SCORE_FILE'])
        self.reset()
    def reset(self):
        self.ticks = 0
        self.move_delay = CONFIG['TICKS_PER_MOVE']
        self.score = 0
        self.level = 1
        self.wrap = False
        self.obstacles: List[Obstacle] = []
        self.food: Optional[Food] = None
        self.powerups: List[PowerUp] = []
        self.power_ticks_remaining: Dict[str,int] = {}
        mid = (self.grid_w // 4, self.grid_h // 2)
        body = [(mid[0]-i, mid[1]) for i in range(CONFIG['START_LENGTH'])]
        self.player = Snake(body=body, direction=(1,0), color=GREEN)
        aimid = (3*self.grid_w // 4, self.grid_h // 2)
        aibody = [(aimid[0]+i, aimid[1]) for i in range(CONFIG['START_LENGTH'])]
        self.ai_snake = Snake(body=aibody, direction=(-1,0), color=BLUE)
        self.ai_enabled = True
        self.spawn_food()
        self.spawn_obstacles(initial=True)
        self.paused = False
        self.game_over = False
    def spawn_food(self):
        empty = self.empty_cells()
        if not empty:
            return
        pos = random.choice(empty)
        self.food = Food(pos=pos, value=1)
    def spawn_powerup(self):
        empty = self.empty_cells()
        if not empty:
            return
        kind = random.choice(POWER_TYPES)
        duration = {'speed': 200, 'slow': 300, 'invincible': 180, 'shrink': 1, 'multiplier': 400}[kind]
        pos = random.choice(empty)
        self.powerups.append(PowerUp(pos=pos, kind=kind, duration_ticks=duration))
    def spawn_obstacles(self, initial=False):
        count = clamp(self.level - 1 + (5 if initial else 0), 0, 50)
        for _ in range(count):
            empty = self.empty_cells()
            if not empty:
                break
            self.obstacles.append(Obstacle(pos=random.choice(empty)))
    def empty_cells(self) -> List[Point]:
        blocked = set(self.player.body) | set(self.ai_snake.body) | {o.pos for o in self.obstacles}
        if self.food:
            blocked.add(self.food.pos)
        blocked |= {p.pos for p in self.powerups}
        cells = [(x,y) for x in range(self.grid_w) for y in range(self.grid_h) if (x,y) not in blocked]
        return cells
    def tick(self):
        if self.paused or self.game_over:
            return
        self.ticks += 1
        player_delay = max(1, int(self.move_delay * self.player.speed_modifier))
        ai_delay = max(1, int(self.move_delay * self.ai_snake.speed_modifier))
        self.player.move_tick_counter += 1
        if self.player.move_tick_counter >= player_delay:
            self.player.move_tick_counter = 0
            self.player_move()
        if self.ai_enabled:
            self.ai_snake.move_tick_counter += 1
            if self.ai_snake.move_tick_counter >= ai_delay:
                self.ai_snake.move_tick_counter = 0
                self.ai_move()
        if self.player.invincible_ticks > 0:
            self.player.invincible_ticks -= 1
        if self.ai_snake.invincible_ticks > 0:
            self.ai_snake.invincible_ticks -= 1
        for p in list(self.powerups):
            p.duration_ticks -= 1
            if p.duration_ticks <= 0:
                self.powerups.remove(p)
    def player_move(self):
        nx, ny = self.next_pos(self.player.head(), self.player.direction)
        if not self.wrap and (nx < 0 or nx >= self.grid_w or ny < 0 or ny >= self.grid_h):
            if self.player.invincible_ticks > 0:
                nx, ny = clamp(nx, 0, self.grid_w-1), clamp(ny, 0, self.grid_h-1)
            else:
                self.player.alive = False
                self.end_game()
                return
        new_head = (nx % self.grid_w, ny % self.grid_h)
        if new_head in {o.pos for o in self.obstacles} and self.player.invincible_ticks <= 0:
            self.player.alive = False
            self.end_game()
            return
        if self.player.collides(new_head) and self.player.invincible_ticks <= 0:
            self.player.alive = False
            self.end_game()
            return
        if self.ai_snake.collides(new_head) and self.player.invincible_ticks <= 0:
            self.player.alive = False
            self.end_game()
            return
        got_food = self.food and new_head == self.food.pos
        got_power = any(p.pos == new_head for p in self.powerups)
        if got_food:
            self.score += self.food.value * (2 if 'multiplier' in self.power_ticks_remaining else 1)
            self.player.grow_pending += 1
            if self.score % 5 == 0:
                self.level += 1
                self.spawn_obstacles()
                if random.random() < 0.5:
                    self.spawn_powerup()
            self.spawn_food()
        if got_power:
            p = next(p for p in self.powerups if p.pos == new_head)
            self.apply_power(self.player, p.kind)
            try:
                self.powerups.remove(p)
            except ValueError:
                pass
        self.player.step(new_head)
    def ai_move(self):
        if not self.food:
            return
        blocked = {o.pos for o in self.obstacles} | set(self.player.body) | set(self.ai_snake.body[1:])
        path = astar(self.ai_snake.head(), self.food.pos, self.grid_w, self.grid_h, blocked, wrap=self.wrap)
        if path and len(path) > 1:
            nxt = path[1]
            dx = nxt[0] - self.ai_snake.head()[0]
            dy = nxt[1] - self.ai_snake.head()[1]
            if self.wrap:
                if dx > 1: dx -= self.grid_w
                if dx < -1: dx += self.grid_w
                if dy > 1: dy -= self.grid_h
                if dy < -1: dy += self.grid_h
            new_dir = (clamp(dx, -1, 1), clamp(dy, -1, 1))
            if new_dir == (0,0):
                new_dir = self.ai_snake.direction
            self.ai_snake.change_dir(new_dir)
        else:
            cand = [(1,0),(-1,0),(0,1),(0,-1)]
            random.shuffle(cand)
            for c in cand:
                nx, ny = self.next_pos(self.ai_snake.head(), c)
                if not self.wrap and (nx < 0 or nx >= self.grid_w or ny < 0 or ny >= self.grid_h):
                    continue
                nxt = (nx % self.grid_w, ny % self.grid_h)
                if nxt in {o.pos for o in self.obstacles}: continue
                if nxt in self.ai_snake.body: continue
                self.ai_snake.change_dir(c)
                break
        nx, ny = self.next_pos(self.ai_snake.head(), self.ai_snake.direction)
        if not self.wrap and (nx < 0 or nx >= self.grid_w or ny < 0 or ny >= self.grid_h):
            self.ai_snake.alive = False
            return
        new_head = (nx % self.grid_w, ny % self.grid_h)
        if new_head in {o.pos for o in self.obstacles} and self.ai_snake.invincible_ticks <= 0:
            self.ai_snake.alive = False
            return
        if self.ai_snake.collides(new_head) and self.ai_snake.invincible_ticks <= 0:
            self.ai_snake.alive = False
            return
        if self.player.collides(new_head) and self.ai_snake.invincible_ticks <= 0:
            self.ai_snake.alive = False
            return
        got_food = self.food and new_head == self.food.pos
        if got_food:
            self.ai_snake.grow_pending += 1
            self.spawn_food()
        self.ai_snake.step(new_head)
    def next_pos(self, pos: Point, dir: Point) -> Point:
        return (pos[0] + dir[0], pos[1] + dir[1])
    def apply_power(self, snake: Snake, kind: str):
        if kind == 'speed':
            snake.speed_modifier = 0.6
            snake.invincible_ticks = 0
            self.power_ticks_remaining['speed'] = 300
        elif kind == 'slow':
            snake.speed_modifier = 1.8
            self.power_ticks_remaining['slow'] = 300
        elif kind == 'invincible':
            snake.invincible_ticks = 300
            self.power_ticks_remaining['invincible'] = 300
        elif kind == 'shrink':
            if len(snake.body) > 3:
                snake.body = snake.body[:-max(1, len(snake.body)//4)]
        elif kind == 'multiplier':
            self.power_ticks_remaining['multiplier'] = 400
    def end_game(self):
        self.game_over = True
        hs = self.highscores.get('highscore', 0)
        if self.score > hs:
            self.highscores['highscore'] = self.score
            save_highscores(CONFIG['HIGH_SCORE_FILE'], self.highscores)
    def draw_cell(self, pos: Point, color: Tuple[int,int,int], inset: int=1):
        x, y = pos
        rect = pygame.Rect(x*self.cell + inset, y*self.cell + inset, self.cell - inset*2, self.cell - inset*2)
        pygame.draw.rect(self.screen, color, rect, border_radius=self.cell//6)
    def render(self):
        self.screen.fill(BLACK)
        for x in range(0, self.width, self.cell):
            pygame.draw.line(self.screen, (20,20,20), (x,0), (x,self.height))
        for y in range(0, self.height, self.cell):
            pygame.draw.line(self.screen, (20,20,20), (0,y), (self.width,y))
        for o in self.obstacles:
            self.draw_cell(o.pos, GRAY)
        if self.food:
            self.draw_cell(self.food.pos, RED, inset=3)
        for p in self.powerups:
            color = YELLOW if p.kind == 'multiplier' else ORANGE if p.kind == 'speed' else PURPLE if p.kind=='invincible' else BLUE if p.kind=='slow' else GREEN
            self.draw_cell(p.pos, color, inset=4)
        for i, b in enumerate(self.ai_snake.body):
            col = tuple(min(255, c + (i*3)) for c in self.ai_snake.color)
            self.draw_cell(b, col, inset=1)
        for i, b in enumerate(self.player.body):
            if i == 0:
                self.draw_cell(b, DARK_GREEN, inset=0)
            else:
                self.draw_cell(b, self.player.color, inset=1)
        hs = self.highscores.get('highscore', 0)
        hud = f'Score: {self.score}  High: {hs}  Level: {self.level}  FPS:{round(self.clock.get_fps())}'
        txt = self.font.render(hud, True, WHITE)
        self.screen.blit(txt, (6,6))
        if self.paused:
            self.draw_centered_text('PAUSED', 48)
        if self.game_over:
            self.draw_center
