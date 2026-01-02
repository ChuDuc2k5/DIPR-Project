import pygame


class Fighter:
    def __init__(self, animations, pos):
        self.animations = animations
        self.state = "idle"
        self.frames = animations[self.state]["frames"]
        self.speed = animations[self.state]["speed"]
        self.index = 0
        self.center = pos
        self.is_attacking = False
        self.attack_type = None
        self.finished = False
        self.ai_timer = 0
        self.max_health = 100
        self.health = 100
        self.alive = True
        self.has_hit = False
        self.shake_timer = 0
        self.flash_timer = 0

    def start_hit_effect(self):
        self.shake_timer = 10  # Rung trong 10 khung hình
        self.flash_timer = 5

    def take_damage(self, amount):
        self.health -= amount
        if self.health <= 0:
            self.health = 0
            self.alive = False

    def set_state(self, state):
        if self.state != state:
            self.state = state
            self.frames = self.animations[state]["frames"]
            self.speed = self.animations[state]["speed"]
            self.index = 0
            self.finished = False
            self.has_hit = False

            if state.startswith("punch"):
                self.is_attacking = True
                self.attack_type = state[-1]  # l / r / s
            else:
                self.is_attacking = False
                self.attack_type = None

    def update(self):
        self.index += self.speed
        if self.shake_timer > 0:
            self.shake_timer -= 1
        if self.flash_timer > 0:
            self.flash_timer -= 1
        # Khi index vượt quá số lượng khung hình của animation hiện tại
        if self.index >= len(self.frames):
            self.finished = True

            if self.is_attacking or self.state.startswith("GH"):
                # Nếu là đấm hoặc bị trúng đòn -> Reset về idle
                self.set_state("idle")
            else:
                # Nếu là idle, defend... -> Lặp lại animation (reset index về 0)
                self.index = 0

    # fighter.py

    def draw(self, screen):
        frame_index = min(int(self.index), len(self.frames) - 1)
        frame = self.frames[frame_index].copy()  # Copy để không đè màu vĩnh viễn

        # 1. Hiệu ứng chớp trắng
        if self.flash_timer > 0:
            # Phủ màu trắng lên sprite
            frame.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)

        rect = frame.get_rect()

        # 2. Hiệu ứng rung (lệch vị trí ngẫu nhiên)
        draw_pos = list(self.center)
        if self.shake_timer > 0:
            import random

            draw_pos[0] += random.randint(-4, 4)
            draw_pos[1] += random.randint(-4, 4)

        rect.midbottom = draw_pos
        screen.blit(frame, rect)
