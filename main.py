import pygame
import sys
import random
import math
import cv2
import mediapipe as mp

# ---------------------------------------
# INITIAL SETUP
# ---------------------------------------
pygame.init()
pygame.mixer.init()

WIDTH, HEIGHT = 900, 700
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Hand Breakout Deluxe")

clock = pygame.time.Clock()

# ---------------------------------------
# COLORS
# ---------------------------------------
BACKGROUND = (12, 18, 28)
WHITE = (255, 255, 255)
TEXT = (220, 220, 220)

BRICK_COLORS = [
    (240, 90, 90),
    (250, 160, 80),
    (250, 220, 80),
    (150, 220, 90),
    (80, 180, 220),
    (180, 120, 220)
]

PARTICLE_COLORS = [
    (255, 200, 100),
    (255, 100, 100),
    (100, 200, 255)
]

# ---------------------------------------
# SOUND EFFECTS
# ---------------------------------------
brick_sound = pygame.mixer.Sound("brick.wav")
paddle_sound = pygame.mixer.Sound("paddle.wav")
lose_sound = pygame.mixer.Sound("lose.wav")
powerup_sound = pygame.mixer.Sound("powerup.wav")

# ---------------------------------------
# MEDIAPIPE HAND TRACKING
# ---------------------------------------
vision = mp.tasks.vision

# Create hand landmarker
base_options = mp.tasks.BaseOptions(model_asset_path='hand_landmarker.task')
options = vision.HandLandmarkerOptions(base_options=base_options, running_mode=vision.RunningMode.VIDEO, num_hands=1)
hand_landmarker = vision.HandLandmarker.create_from_options(options)

cap = cv2.VideoCapture(0)

# ---------------------------------------
# GAME OBJECT CLASSES
# ---------------------------------------

class Paddle:
    def __init__(self):
        self.width = 150
        self.height = 15
        self.x = WIDTH // 2 - self.width // 2
        self.y = HEIGHT - 50
        self.speed = 25

    def draw(self):
        pygame.draw.rect(screen, (70, 130, 255), (self.x, self.y, self.width, self.height), border_radius=6)
        pygame.draw.rect(screen, (120, 170, 255), (self.x+4, self.y+2, self.width-8, 4), border_radius=4)

    def move_to(self, target_x):
        if target_x < self.x:
            self.x -= self.speed
        elif target_x > self.x:
            self.x += self.speed
        self.x = max(0, min(self.x, WIDTH - self.width))


class Ball:
    def __init__(self, x=None, y=None):
        self.radius = 10
        self.x = x if x else WIDTH // 2
        self.y = y if y else HEIGHT // 2
        angle = random.uniform(-math.pi/4, math.pi/4)
        speed = 6
        self.dx = speed * math.cos(angle)
        self.dy = -abs(speed * math.sin(angle))
        self.active = True

    def move(self):
        self.x += self.dx
        self.y += self.dy

        # Wall collisions
        if self.x <= self.radius or self.x >= WIDTH - self.radius:
            self.dx *= -1

        if self.y <= self.radius:
            self.dy *= -1

        if self.y >= HEIGHT + 50:
            self.active = False

    def draw(self):
        pygame.draw.circle(screen, (255, 105, 97), (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(screen, WHITE, (int(self.x - 3), int(self.y - 3)), 4)


class Brick:
    def __init__(self, x, y, color_index):
        self.x = x
        self.y = y
        self.width = 90
        self.height = 30
        self.color = BRICK_COLORS[color_index]
        self.active = True

    def draw(self):
        if not self.active:
            return
        pygame.draw.rect(screen, self.color, (self.x, self.y, self.width, self.height), border_radius=4)
        pygame.draw.rect(screen, (min(self.color[0]+40,255), min(self.color[1]+40,255), min(self.color[2]+40,255)),
                         (self.x+3, self.y+3, self.width-6, 6), border_radius=3)


class Particle:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.dx = random.uniform(-2,2)
        self.dy = random.uniform(-2,2)
        self.size = random.randint(3,6)
        self.life = 30
        self.color = random.choice(PARTICLE_COLORS)

    def update(self):
        self.x += self.dx
        self.y += self.dy
        self.size = max(0, self.size-0.1)
        self.life -= 1

    def draw(self):
        if self.life > 0:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), int(self.size))


class PowerUp:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.size = 22
        self.type = random.choice(["big", "slow", "multi"])
        self.speed = 3
        self.active = True

    def update(self):
        self.y += self.speed
        if self.y > HEIGHT:
            self.active = False

    def draw(self):
        colors = {
            "big": (150,255,150),
            "slow": (255,200,150),
            "multi": (150,150,255)
        }
        pygame.draw.rect(screen, colors[self.type], (self.x, self.y, self.size, self.size), border_radius=6)


# ---------------------------------------
# GAME CLASS
# ---------------------------------------
class Game:
    def __init__(self):
        self.paddle = Paddle()
        self.balls = [Ball()]
        self.bricks = []
        self.particles = []
        self.powerups = []

        self.score = 0
        self.lives = 3
        self.level = 1

        self.shake = 0
        self.filtered_x = WIDTH // 2
        self.hand_frame_counter = 0

        self.font = pygame.font.SysFont("Arial", 28)
        self.big_font = pygame.font.SysFont("Arial", 60)

        self.create_bricks()

    def create_bricks(self):
        self.bricks = []
        start_x = 80
        start_y = 80
        for row in range(6):
            for col in range(8):
                x = start_x + col * 100
                y = start_y + row * 40
                self.bricks.append(Brick(x, y, row % len(BRICK_COLORS)))

    # --------------------------
    # HAND TRACKING
    # --------------------------
    def detect_hand_only(self):
        ret, frame = cap.read()
        if not ret:
            return False
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        timestamp_ms = int(cv2.getTickCount() / cv2.getTickFrequency() * 1000)
        result = hand_landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms)
        return bool(result.hand_landmarks and len(result.hand_landmarks) > 0)

    def update_hand(self):
        self.hand_frame_counter += 1
        ret, frame = cap.read()
        if not ret:
            return
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        timestamp_ms = int(cv2.getTickCount() / cv2.getTickFrequency() * 1000)
        result = hand_landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms)

        if result.hand_landmarks and len(result.hand_landmarks) > 0:
            # Get the tip of the index finger (landmark 8)
            tip = result.hand_landmarks[0][8]  # INDEX_FINGER_TIP
            hand_x = int(tip.x * WIDTH)
            alpha = 0.8
            self.filtered_x = int(alpha*hand_x + (1-alpha)*self.filtered_x)
            self.paddle.move_to(self.filtered_x)

        # Store frame for camera preview
        self.hand_frame = frame.copy()

    # --------------------------
    # UPDATE GAME LOGIC
    # --------------------------
    def update(self):
        self.update_hand()

        # Update balls
        for ball in self.balls[:]:
            ball.move()
            if not ball.active:
                self.balls.remove(ball)
                continue
            # Paddle collision
            if (self.paddle.y - ball.radius <= ball.y <= self.paddle.y + 10 and
                self.paddle.x <= ball.x <= self.paddle.x + self.paddle.width):
                ball.dy *= -1
                paddle_sound.play()

        # If no balls left
        if not self.balls:
            self.lives -= 1
            lose_sound.play()
            if self.lives > 0:
                self.balls.append(Ball())
            else:
                return "game_over"

        # Brick collisions
        remaining = 0
        for brick in self.bricks:
            if not brick.active:
                continue
            remaining += 1
            for ball in self.balls:
                if (brick.x <= ball.x <= brick.x + brick.width and
                    brick.y <= ball.y <= brick.y + brick.height):
                    brick.active = False
                    ball.dy *= -1
                    self.score += 10
                    brick_sound.play()
                    self.shake = 6
                    for _ in range(15):
                        self.particles.append(Particle(brick.x+45, brick.y+15))
                    if random.random() < 0.08:
                        self.powerups.append(PowerUp(brick.x+20, brick.y+10))

        # New level
        if remaining == 0:
            self.level += 1
            self.create_bricks()
            self.balls = [Ball()]

        # Update particles
        for p in self.particles[:]:
            p.update()
            if p.life <= 0:
                self.particles.remove(p)

        # Update powerups
        for p in self.powerups[:]:
            p.update()
            if not p.active:
                self.powerups.remove(p)
                continue
            if (self.paddle.y <= p.y <= self.paddle.y+20 and
                self.paddle.x <= p.x <= self.paddle.x + self.paddle.width):
                self.apply_powerup(p.type)
                powerup_sound.play()
                self.powerups.remove(p)

        return "playing"

    def apply_powerup(self, type):
        if type == "big":
            self.paddle.width = min(self.paddle.width + 40, 250)
        elif type == "slow":
            for b in self.balls:
                b.dx *= 0.7
                b.dy *= 0.7
        elif type == "multi":
            self.balls.append(Ball(self.balls[0].x, self.balls[0].y))
            self.balls.append(Ball(self.balls[0].x, self.balls[0].y))

    # --------------------------
    # DRAW
    # --------------------------
    def draw(self):
        ox = random.randint(-self.shake, self.shake) if self.shake > 0 else 0
        oy = random.randint(-self.shake, self.shake) if self.shake > 0 else 0
        self.shake = max(0, self.shake - 1)

        screen.fill(BACKGROUND)

        # Draw objects
        self.paddle.draw()
        for b in self.balls:
            b.draw()
        for brick in self.bricks:
            brick.draw()
        for p in self.particles:
            p.draw()
        for p in self.powerups:
            p.draw()

        # UI
        score = self.font.render(f"Score: {self.score}", True, TEXT)
        lives = self.font.render(f"Lives: {self.lives}", True, TEXT)
        level = self.font.render(f"Level: {self.level}", True, TEXT)
        screen.blit(score, (20, 20))
        screen.blit(lives, (20, 50))
        screen.blit(level, (WIDTH - 150, 20))

        # Draw camera preview with landmarks
        if hasattr(self, "hand_frame"):
            cam_size = 150
            frame_small = cv2.resize(self.hand_frame, (cam_size, cam_size))
            frame_small = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
            surf = pygame.surfarray.make_surface(frame_small.swapaxes(0, 1))
            screen.blit(surf, (WIDTH - cam_size - 10, 10))
            pygame.draw.rect(screen, WHITE, (WIDTH - cam_size - 10, 10, cam_size, cam_size), 2)


# ---------------------------------------
# SCREENS
# ---------------------------------------
def draw_menu():
    screen.fill(BACKGROUND)
    title = pygame.font.SysFont("Arial", 70).render("HAND BREAKOUT", True, WHITE)
    sub = pygame.font.SysFont("Arial", 32).render("Raise your hand to start", True, TEXT)
    screen.blit(title, (WIDTH//2 - title.get_width()//2, 250))
    screen.blit(sub, (WIDTH//2 - sub.get_width()//2, 360))


def draw_game_over(score):
    screen.fill((0, 0, 0))
    t = pygame.font.SysFont("Arial", 70).render("GAME OVER", True, (255, 80, 80))
    s = pygame.font.SysFont("Arial", 40).render(f"Score: {score}", True, WHITE)
    r = pygame.font.SysFont("Arial", 30).render("Press R to Restart or Q to Quit", True, WHITE)
    screen.blit(t, (WIDTH//2 - t.get_width()//2, 230))
    screen.blit(s, (WIDTH//2 - s.get_width()//2, 330))
    screen.blit(r, (WIDTH//2 - r.get_width()//2, 420))


# ---------------------------------------
# MAIN LOOP
# ---------------------------------------
def main():
    game = Game()
    state = "menu"

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                cap.release()
                cv2.destroyAllWindows()
                sys.exit()

        if state == "menu":
            draw_menu()
            if game.detect_hand_only():
                state = "playing"

        elif state == "playing":
            status = game.update()
            game.draw()
            if status == "game_over":
                state = "game_over"

        elif state == "game_over":
            draw_game_over(game.score)
            keys = pygame.key.get_pressed()
            if keys[pygame.K_r]:
                game = Game()
                state = "menu"
            if keys[pygame.K_q]:
                pygame.quit()
                sys.exit()

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    main()
