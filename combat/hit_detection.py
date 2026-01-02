# combat/hit_detection.py

import pygame


def check_hit(attacker, defender):
    if attacker.state != "PUNCH":
        return

    if attacker.has_hit:
        return

    hitbox = attacker.rect.copy()

    if attacker.direction == 1:
        hitbox.width += 40
    else:
        hitbox.x -= 40
        hitbox.width += 40

    if hitbox.colliderect(defender.rect):
        damage = 10

        # 🧠 COUNTER HIT
        if defender.state == "PUNCH":
            damage *= 1.5

        defender.take_hit(damage)
        attacker.has_hit = True
