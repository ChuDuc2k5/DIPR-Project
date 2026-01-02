import pygame
import os
import random
import multiprocessing
import sys

# Import từ các file khác
from spritesheet import load_sprite_sheet
from ai_controller import ai_process
from fighter import Fighter

# =====================
# GLOBAL CONSTANTS
# =====================
WIDTH, HEIGHT = 1500, 700
FPS = 60


# =====================
# MAIN GAME FUNCTION
# =====================
def main():
    # 1. SETUP PYGAME
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("FPS Boxing - AI Integration")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 48)
    small_font = pygame.font.SysFont("Arial", 24)

    # 2. SETUP AI PROCESS
    ai_queue = multiprocessing.Queue(maxsize=1)
    frame_queue = multiprocessing.Queue(maxsize=1)
    stop_event = multiprocessing.Event()

    ai_proc = multiprocessing.Process(
        target=ai_process, args=(ai_queue, frame_queue, stop_event)
    )
    ai_proc.start()

    # ASSETS
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSETS = os.path.join(BASE_DIR, "assets")

    # --- Backgrounds ---
    def load_bg(filename):
        path = os.path.join(ASSETS, "bg", filename)
        try:
            img = pygame.image.load(path).convert()
            return pygame.transform.scale(img, (WIDTH, HEIGHT))
        except Exception:
            surf = pygame.Surface((WIDTH, HEIGHT))
            surf.fill((50, 50, 50))
            return surf

    menu_bg = load_bg("Menu.png")
    win_bg = load_bg("Win.png")
    lose_bg = load_bg("Lose.png")
    play_bg = load_bg("Bg.png")

    # --- Animations ---
    PLAYER_ANIM = {
        "idle": ("Idle.png", 3, 0.18),
        "punch_l": ("LP.png", 6, 0.18),
        "punch_r": ("RP.png", 6, 0.18),
        "punch_ls": ("LSP.png", 6, 0.15),
        "punch_rs": ("RSP.png", 6, 0.15),
        "defend": ("def.png", 9, 0.15),
    }

    ENEMY_ANIM = {
        "idle": ("Idle.png", 4, 0.07),
        "punch_l": ("LP.png", 5, 0.05),
        "punch_r": ("RP.png", 5, 0.05),
        "punch_s": ("SP.png", 5, 0.05),
        "defend": ("def.png", 2, 0.02),
        "GHR": ("GHR.png", 3, 0.18),
        "GHL": ("GHL.png", 3, 0.18),
        "GHS": ("GHS.png", 2, 0.20),
        "GHRdef": ("GHRdef.png", 3, 0.14),
        "GHLdef": ("GHLdef.png", 3, 0.14),
    }

    def load_anim_data(folder, anim_config):
        animations = {}
        if not os.path.exists(folder):
            return animations

        for state_key, (filename, frame_count, speed) in anim_config.items():
            path = os.path.join(folder, filename)
            try:
                animations[state_key] = {
                    "frames": load_sprite_sheet(path, frame_count, 3.5),
                    "speed": speed,
                }
            except Exception:
                pass
        return animations

    p_anims = load_anim_data(os.path.join(ASSETS, "player"), PLAYER_ANIM)
    e_anims = load_anim_data(os.path.join(ASSETS, "enemy"), ENEMY_ANIM)

    if not p_anims:
        p_anims = {"idle": {"frames": [pygame.Surface((50, 100))], "speed": 0.1}}
    if not e_anims:
        e_anims = {"idle": {"frames": [pygame.Surface((50, 100))], "speed": 0.1}}

    player = Fighter(p_anims, (WIDTH // 2, HEIGHT - 100))
    enemy = Fighter(e_anims, (WIDTH // 2, HEIGHT))

    # VARIABLE
    MENU, PLAY, TUTORIAL, WIN, LOSE = "menu", "play", "tutorial", "win", "lose"
    state = MENU
    menu_index = 0
    cam_surface = None
    ai_defend_active = False

    def draw_health_bar(curr_health, x, y, is_player):
        BAR_WIDTH, BAR_HEIGHT = 500, 30
        ratio = max(curr_health / 100, 0)
        pygame.draw.rect(screen, (200, 0, 0), (x, y, BAR_WIDTH, BAR_HEIGHT))
        if is_player:
            pygame.draw.rect(screen, (0, 255, 0), (x, y, BAR_WIDTH * ratio, BAR_HEIGHT))
        else:
            pygame.draw.rect(
                screen,
                (0, 255, 0),
                (x + (BAR_WIDTH * (1 - ratio)), y, BAR_WIDTH * ratio, BAR_HEIGHT),
            )
        pygame.draw.rect(screen, (255, 255, 255), (x, y, BAR_WIDTH, BAR_HEIGHT), 3)

    def resolve_combat():
        if player.is_attacking and int(player.index) == 4 and not player.has_hit:
            if not enemy.state.startswith("GH"):
                atk_type = player.attack_type
                dmg = 10
                if enemy.state == "defend":
                    enemy.start_hit_effect()
                    enemy.take_damage(2)
                else:
                    enemy.take_damage(dmg)
                    hit_state = "GHS"
                    if atk_type == "l":
                        hit_state = "GHL"
                    elif atk_type == "r":
                        hit_state = "GHR"
                    elif atk_type == "s":
                        hit_state = "GHS"
                    enemy.set_state(hit_state)
                player.has_hit = True

        if enemy.is_attacking and int(enemy.index) == 3 and not enemy.has_hit:
            player.start_hit_effect()
            if player.state == "defend":
                player.take_damage(2)
            else:
                player.take_damage(10)
                player.set_state("idle")
            enemy.has_hit = True

    def update_enemy_ai():
        if enemy.state.startswith("GH") or enemy.is_attacking:
            return
        enemy.ai_timer += 1
        if enemy.ai_timer > random.randint(60, 100):
            decision = random.random()
            if decision < 0.2:
                enemy.set_state("punch_l")
            elif decision < 0.4:
                enemy.set_state("punch_r")
            elif decision < 0.5:
                enemy.set_state("punch_s")
            else:
                enemy.set_state("defend")
            enemy.ai_timer = 0

    def reset_game():
        player.health = 100
        enemy.health = 100
        player.alive = True
        enemy.alive = True
        player.set_state("idle")
        enemy.set_state("idle")

    # LOOP
    running = True
    try:
        while running:
            clock.tick(FPS)

            ai_cmd = None
            while not ai_queue.empty():
                ai_cmd = ai_queue.get()

            if ai_cmd == "DEFEND_ON":
                ai_defend_active = True
            elif ai_cmd == "DEFEND_OFF":
                ai_defend_active = False

            # Lấy Camera Frame
            if not frame_queue.empty():
                try:
                    frame_data = frame_queue.get()
                    frame_data = frame_data.swapaxes(0, 1)
                    cam_surface = pygame.surfarray.make_surface(frame_data)
                except:
                    pass

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                if state == MENU and event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_UP:
                        menu_index = (menu_index - 1) % 3
                    elif event.key == pygame.K_DOWN:
                        menu_index = (menu_index + 1) % 3
                    elif event.key == pygame.K_RETURN:
                        if menu_index == 0:
                            reset_game()
                            state = PLAY
                        elif menu_index == 1:
                            state = TUTORIAL
                        elif menu_index == 2:
                            running = False

                if state in [TUTORIAL, WIN, LOSE] and event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        state = MENU

                if state == PLAY and event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        state = MENU

            if state == MENU:
                screen.blit(menu_bg, (0, 0))
                # === MENU INFO TEXT (TOP-LEFT) ===
                menu_info = [
                    "Group 11",
                    "Lê Nguyên - 23110043",
                    "Ngô Viet Hoang - 23110020",
                    "Chu Ngoc Viet Đuc - 23110016",
                ]

                for i, line in enumerate(menu_info):
                    txt = small_font.render(line, True, (255, 255, 255))
                    screen.blit(txt, (10, 10 + i * 22))

                options = ["PLAY", "TUTORIAL", "EXIT"]
                for i, text in enumerate(options):
                    col = (255, 0, 0) if i == menu_index else (200, 200, 200)
                    lbl = font.render(text, True, col)
                    screen.blit(lbl, (WIDTH // 2 - 60, 320 + i * 70))

            elif state == TUTORIAL:
                screen.fill((10, 10, 10))
                lines = [
                    "FPS BOXING - AI CONTROL",
                    "",
                    "Use Webcam to Punch/Guard",
                    "ESC to Return",
                ]
                for i, line in enumerate(lines):
                    txt = font.render(line, True, (200, 200, 200))
                    screen.blit(txt, (180, 150 + i * 45))

            elif state == PLAY:
                screen.blit(play_bg, (0, 0))
                if player.health <= 0:
                    state = LOSE
                elif enemy.health <= 0:
                    state = WIN

                if state == PLAY:
                    update_enemy_ai()

                    if not player.is_attacking:
                        action_taken = False

                        if ai_cmd == "PUNCH_L":
                            player.set_state("punch_l")
                            action_taken = True
                        elif ai_cmd == "PUNCH_R":
                            player.set_state("punch_r")
                            action_taken = True
                        elif ai_cmd == "PUNCH_S":
                            player.set_state("punch_rs")
                            action_taken = True

                        if not action_taken:
                            keys = pygame.key.get_pressed()
                            if keys[pygame.K_a]:
                                player.set_state("punch_l")
                                action_taken = True
                            elif keys[pygame.K_d]:
                                player.set_state("punch_r")
                                action_taken = True
                            elif keys[pygame.K_w] or keys[pygame.K_e]:
                                player.set_state("punch_rs")
                                action_taken = True
                            elif keys[pygame.K_q]:
                                player.set_state("punch_ls")
                                action_taken = True

                        if not action_taken:
                            keys = pygame.key.get_pressed()
                            if ai_defend_active or keys[pygame.K_s]:
                                player.set_state("defend")
                            else:
                                player.set_state("idle")

                    player.update()
                    enemy.update()
                    resolve_combat()

                enemy.draw(screen)
                player.draw(screen)
                draw_health_bar(player.health, 50, 50, True)
                draw_health_bar(enemy.health, WIDTH - 550, 50, False)

                if cam_surface:
                    cam_x, cam_y = WIDTH - 330, 90
                    pygame.draw.rect(
                        screen, (255, 255, 255), (cam_x - 2, cam_y - 2, 324, 244), 2
                    )
                    screen.blit(cam_surface, (cam_x, cam_y))
                    st_txt = small_font.render("AI Active", True, (0, 255, 0))
                    screen.blit(st_txt, (cam_x, cam_y + 245))

            elif state == WIN:
                screen.blit(win_bg, (0, 0))
                msg = font.render("VICTORY! Press ESC", True, (0, 255, 0))
                screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2))

            elif state == LOSE:
                screen.blit(lose_bg, (0, 0))
                msg = font.render("DEFEAT... Press ESC", True, (255, 0, 0))
                screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, HEIGHT // 2))

            pygame.display.flip()

    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        ai_proc.join()
        pygame.quit()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
