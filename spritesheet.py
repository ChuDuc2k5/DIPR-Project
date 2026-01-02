import pygame


def load_sprite_sheet(path, frame_count, scale=1):
    sheet = pygame.image.load(path).convert_alpha()
    fw = sheet.get_width() // frame_count
    fh = sheet.get_height()

    frames = []
    for i in range(frame_count):
        frame = sheet.subsurface(pygame.Rect(i * fw, 0, fw, fh))
        frame = pygame.transform.scale(frame, (int(fw * scale), int(fh * scale)))
        frames.append(frame)

    return frames
