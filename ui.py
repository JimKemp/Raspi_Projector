"""
All pygame rendering for Jimflix. The UI class owns the screen surface, fonts,
and a cover-image cache. Each draw_* method renders one screen state. Cover
loading is defensive: a missing or corrupt image falls back to a titled
placeholder tile instead of crashing.
"""

import os

import pygame

import config


def _wrap_text(font, text, max_width):
    """Greedy word-wrap into a list of lines that each fit max_width pixels."""
    if not text:
        return []
    lines = []
    for paragraph in text.splitlines():
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            trial = word if not current else current + " " + word
            if font.size(trial)[0] <= max_width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
    return lines


def _truncate(font, text, max_width):
    """Truncate a single line with an ellipsis if it exceeds max_width."""
    if font.size(text)[0] <= max_width:
        return text
    ell = "…"
    while text and font.size(text + ell)[0] > max_width:
        text = text[:-1]
    return text + ell


class UI:
    def __init__(self):
        flags = pygame.FULLSCREEN if config.FULLSCREEN else 0
        self.screen = pygame.display.set_mode(config.SCREEN_SIZE, flags)
        pygame.display.set_caption("Jimflix")
        pygame.mouse.set_visible(False)
        self.w, self.h = config.SCREEN_SIZE

        self.font_splash = pygame.font.Font(config.FONT_NAME, config.FONT_SIZE_SPLASH)
        self.font_header = pygame.font.Font(config.FONT_NAME, config.FONT_SIZE_HEADER)
        self.font_item = pygame.font.Font(config.FONT_NAME, config.FONT_SIZE_ITEM)
        self.font_body = pygame.font.Font(config.FONT_NAME, config.FONT_SIZE_BODY)
        self.font_small = pygame.font.Font(config.FONT_NAME, config.FONT_SIZE_SMALL)

        self._cover_cache = {}   # (path, w, h) -> Surface

    def flip(self):
        pygame.display.flip()

    # --- cover handling ----------------------------------------------------

    def _placeholder(self, title, size):
        surf = pygame.Surface(size)
        surf.fill(config.PLACEHOLDER_COLOR)
        pygame.draw.rect(surf, config.DIM_TEXT_COLOR, surf.get_rect(), 2)
        # Wrap the title into the tile so an art-less item is still identifiable.
        lines = _wrap_text(self.font_small, title, size[0] - 16)[:6]
        y = (size[1] - len(lines) * (self.font_small.get_height() + 2)) // 2
        for line in lines:
            txt = self.font_small.render(line, True, config.TEXT_COLOR)
            surf.blit(txt, ((size[0] - txt.get_width()) // 2, y))
            y += self.font_small.get_height() + 2
        return surf

    def get_cover(self, item, size):
        key = (item.cover_path, size[0], size[1])
        if key in self._cover_cache:
            return self._cover_cache[key]

        surf = None
        if item.cover_path and os.path.isfile(item.cover_path):
            try:
                img = pygame.image.load(item.cover_path).convert()
                surf = pygame.transform.smoothscale(img, size)
            except Exception:
                surf = None   # corrupt/unsupported image -> placeholder
        if surf is None:
            surf = self._placeholder(item.title, size)

        self._cover_cache[key] = surf
        return surf

    # --- screens -----------------------------------------------------------

    def draw_splash(self):
        self.screen.fill(config.SPLASH_BG_COLOR)
        txt = self.font_splash.render(config.SPLASH_TEXT, True, config.HIGHLIGHT_COLOR)
        self.screen.blit(
            txt, ((self.w - txt.get_width()) // 2, (self.h - txt.get_height()) // 2)
        )
        self.flip()

    def draw_message(self, message, submessage=""):
        self.screen.fill(config.BG_COLOR)
        txt = self.font_header.render(message, True, config.TEXT_COLOR)
        self.screen.blit(txt, ((self.w - txt.get_width()) // 2, self.h // 2 - 60))
        if submessage:
            sub = self.font_body.render(submessage, True, config.DIM_TEXT_COLOR)
            self.screen.blit(sub, ((self.w - sub.get_width()) // 2, self.h // 2 + 10))
        self.flip()

    def draw_categories(self, categories, selected):
        self.screen.fill(config.BG_COLOR)
        header = self.font_header.render("Jimflix", True, config.HIGHLIGHT_COLOR)
        self.screen.blit(header, (config.GRID_LEFT, 40))

        y = 140
        row_h = self.font_item.get_height() + 28
        for i, cat in enumerate(categories):
            is_sel = i == selected
            if is_sel:
                rect = pygame.Rect(config.GRID_LEFT - 16, y - 6,
                                   self.w - 2 * (config.GRID_LEFT - 16), row_h - 12)
                pygame.draw.rect(self.screen, config.PANEL_COLOR, rect, border_radius=8)
                pygame.draw.rect(self.screen, config.HIGHLIGHT_COLOR, rect, 2, border_radius=8)
            color = config.HIGHLIGHT_COLOR if is_sel else config.TEXT_COLOR
            label = f"{cat.name}"
            count = f"{len(cat)} title{'s' if len(cat) != 1 else ''}"
            txt = self.font_item.render(label, True, color)
            cnt = self.font_small.render(count, True, config.DIM_TEXT_COLOR)
            self.screen.blit(txt, (config.GRID_LEFT, y))
            self.screen.blit(cnt, (self.w - config.GRID_LEFT - cnt.get_width(), y + 4))
            y += row_h

        self._footer("↑↓ navigate    OK select")
        self.flip()

    def draw_grid(self, category, selected, scroll_row):
        self.screen.fill(config.BG_COLOR)
        header = self.font_header.render(category.name, True, config.HIGHLIGHT_COLOR)
        self.screen.blit(header, (config.GRID_LEFT, 28))

        cols = config.GRID_COLUMNS
        cw, ch = config.COVER_W, config.COVER_H
        hsp, vsp = config.GRID_H_SPACING, config.GRID_V_SPACING
        cell_h = ch + self.font_small.get_height() + 8
        top = config.GRID_TOP

        visible_rows = max(1, (self.h - top - 40) // (cell_h + vsp))

        for idx, item in enumerate(category.items):
            row = idx // cols
            col = idx % cols
            if row < scroll_row or row >= scroll_row + visible_rows:
                continue
            x = config.GRID_LEFT + col * (cw + hsp)
            y = top + (row - scroll_row) * (cell_h + vsp)

            cover = self.get_cover(item, (cw, ch))
            self.screen.blit(cover, (x, y))

            if idx == selected:
                pygame.draw.rect(self.screen, config.HIGHLIGHT_COLOR,
                                 pygame.Rect(x - 4, y - 4, cw + 8, ch + 8), 4,
                                 border_radius=6)

            title = _truncate(self.font_small, item.title, cw)
            color = config.HIGHLIGHT_COLOR if idx == selected else config.DIM_TEXT_COLOR
            label = self.font_small.render(title, True, color)
            self.screen.blit(label, (x + (cw - label.get_width()) // 2, y + ch + 4))

        self._footer("↑↓←→ navigate    OK details    Back to categories")
        self.flip()

    def draw_detail(self, item, episode_selected=0):
        self.screen.fill(config.BG_COLOR)

        # Cover on the left.
        cw, ch = 300, 430
        cover = self.get_cover(item, (cw, ch))
        self.screen.blit(cover, (config.GRID_LEFT, 80))

        # Text column on the right.
        tx = config.GRID_LEFT + cw + 50
        tw = self.w - tx - config.GRID_LEFT
        y = 80

        title = _truncate(self.font_header, item.title, tw)
        self.screen.blit(self.font_header.render(title, True, config.TEXT_COLOR), (tx, y))
        y += self.font_header.get_height() + 8

        meta = item.meta_line()
        if meta:
            self.screen.blit(self.font_body.render(meta, True, config.HIGHLIGHT_COLOR), (tx, y))
            y += self.font_body.get_height() + 6
        if item.series:
            self.screen.blit(
                self.font_small.render(f"Series: {item.series}", True, config.DIM_TEXT_COLOR),
                (tx, y))
            y += self.font_small.get_height() + 10
        else:
            y += 10

        # Description (wrapped, truncated to fit remaining space above footer).
        desc = item.description or "No description available."
        avail_h = self.h - y - 150
        max_lines = max(1, avail_h // (self.font_body.get_height() + 4))
        lines = _wrap_text(self.font_body, desc, tw)
        for line in lines[:max_lines]:
            self.screen.blit(self.font_body.render(line, True, config.TEXT_COLOR), (tx, y))
            y += self.font_body.get_height() + 4
        if len(lines) > max_lines:
            self.screen.blit(self.font_body.render("…", True, config.DIM_TEXT_COLOR), (tx, y))

        # Episode list if more than one video file in the folder.
        if len(item.videos) > 1:
            ey = self.h - 200
            self.screen.blit(
                self.font_small.render("Files:", True, config.DIM_TEXT_COLOR),
                (tx, ey))
            ey += self.font_small.get_height() + 4
            for i, v in enumerate(item.videos[:4]):
                name = _truncate(self.font_small, os.path.basename(v), tw - 30)
                color = config.HIGHLIGHT_COLOR if i == episode_selected else config.TEXT_COLOR
                prefix = "▶ " if i == episode_selected else "   "
                self.screen.blit(
                    self.font_small.render(prefix + name, True, color), (tx, ey))
                ey += self.font_small.get_height() + 2

        if not item.has_video:
            warn = self.font_body.render("Video file unavailable", True, (220, 90, 90))
            self.screen.blit(warn, (tx, self.h - 150))

        hint = "OK / Play to watch    Back to list"
        if len(item.videos) > 1:
            hint = "↑↓ pick file    OK / Play to watch    Back to list"
        self._footer(hint)
        self.flip()

    # --- helpers -----------------------------------------------------------

    def _footer(self, text):
        bar = self.font_small.render(text, True, config.DIM_TEXT_COLOR)
        self.screen.blit(bar, (config.GRID_LEFT, self.h - 44))
