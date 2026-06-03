"""
Simulation View

QWidget that renders the live simulation onto an offscreen PyGame Surface
and blits it through a QImage. Visual style follows the dark engineering
palette defined in ui/theme.py — uniform with the rest of the app.

The viewport is *the* dominant area of the workflow, so we lean on:
  - a deep matte background that pushes obstacles forward;
  - subtle per-metre grid that fades into the background;
  - high-contrast robot/goal/sensor accents;
  - a calm HUD pinned to the top-left, plus a status pill bottom-right.
"""

from typing import Any, Callable, Optional, Tuple

import numpy as np
import pygame
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QImage, QPainter
from PyQt5.QtWidgets import QWidget

from .theme import VIEWPORT


class SimulationView(QWidget):
    """Renders the simulation. Pure view: never advances the engine."""

    DEFAULT_SIZE = QSize(820, 720)

    def __init__(
        self,
        get_engine: Callable[[], Optional[object]],
        on_key_press: Optional[Callable[[str], None]] = None,
        on_key_release: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._get_engine = get_engine
        self._on_key_press = on_key_press
        self._on_key_release = on_key_release

        self.setMinimumSize(QSize(540, 420))
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAutoFillBackground(False)

        pygame.init()
        self._surface = pygame.Surface(
            (self.DEFAULT_SIZE.width(), self.DEFAULT_SIZE.height())
        )
        # Pre-load fonts once — pygame's SysFont call is non-trivial.
        self._font_hud = pygame.font.SysFont("Consolas,Cascadia Code,Menlo", 12)
        self._font_caption = pygame.font.SysFont("Segoe UI,Inter", 11, bold=False)
        self._font_pill = pygame.font.SysFont("Segoe UI,Inter", 11, bold=True)

        # --- Editor mode plumbing ---------------------------------------
        # When set, the view renders from the editor's MapModel instead of
        # the live SimulationEngine, and forwards mouse events to it.
        self._editor_controller: Any = None  # late binding to avoid cycle
        self._edit_mode: bool = False
        # Cached world-to-screen transform from the last render so mouse
        # handlers can run screen_to_world without re-deriving the layout.
        self._last_scale: float = 1.0
        self._last_offset_x: float = 0.0
        self._last_offset_y: float = 0.0
        self._last_world_size: Tuple[float, float] = (0.0, 0.0)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    def resizeEvent(self, event):  # noqa: N802 (Qt naming)
        size = event.size()
        if size.width() > 0 and size.height() > 0:
            self._surface = pygame.Surface((size.width(), size.height()))
        super().resizeEvent(event)

    # ------------------------------------------------------------------
    # Editor binding
    # ------------------------------------------------------------------
    def set_editor_controller(self, controller: Any) -> None:
        """Attach (or detach with None) the scene-editor controller."""
        self._editor_controller = controller

    def set_edit_mode(self, enabled: bool) -> None:
        """Switch render path: live engine vs. editor model."""
        self._edit_mode = bool(enabled)
        # The crosshair pointer makes the editor feel like, well, an editor.
        if self._edit_mode:
            self.setCursor(Qt.CrossCursor)
        else:
            self.unsetCursor()

    # ------------------------------------------------------------------
    # Render entry point.
    # ------------------------------------------------------------------
    def render_frame(self) -> None:
        self._surface.fill(VIEWPORT.BG)

        # Editor mode short-circuits everything that depends on the engine.
        if self._edit_mode and self._editor_controller is not None:
            self._render_editor()
            self.update()
            return

        engine = self._get_engine()
        if engine is None:
            self._draw_placeholder("Load a scene to begin")
            self.update()
            return

        env = engine.environment
        robot = engine.robot

        offset_x, offset_y, scale = self._compute_layout(env.width, env.height)
        W, H = self._surface.get_size()
        self._cache_layout(offset_x, offset_y, scale, env.width, env.height)

        def to_screen(wx: float, wy: float) -> Tuple[int, int]:
            return (
                int(offset_x + wx * scale),
                int(H - offset_y - wy * scale),
            )

        self._draw_grid(env, scale, offset_x, offset_y, H)
        self._draw_world_frame(env, to_screen)
        self._draw_obstacles(env, to_screen)
        self._draw_path(engine, to_screen)
        self._draw_trail(robot, to_screen)
        self._draw_goal(env, to_screen, scale)
        self._draw_rays(robot, env, to_screen)
        self._draw_robot(robot, to_screen, scale)
        frame_left = int(offset_x)
        frame_top = int(offset_y)
        frame_right = int(offset_x + env.width * scale)
        frame_bottom = int(H - offset_y)
        self._draw_hud(engine, frame_left, frame_top)
        self._draw_status_pill(engine, frame_right, frame_bottom)

        self.update()

    # ------------------------------------------------------------------
    # Editor render path
    # ------------------------------------------------------------------
    def _render_editor(self) -> None:
        ctrl = self._editor_controller
        model = ctrl.model

        offset_x, offset_y, scale = self._compute_layout(model.width, model.height)
        W, H = self._surface.get_size()
        self._cache_layout(offset_x, offset_y, scale, model.width, model.height)

        def to_screen(wx: float, wy: float) -> Tuple[int, int]:
            return (
                int(offset_x + wx * scale),
                int(H - offset_y - wy * scale),
            )

        # World grid + frame.
        self._draw_grid_simple(model.width, model.height, scale, offset_x, offset_y, H)
        x0, y0 = to_screen(0, model.height)
        x1, y1 = to_screen(model.width, 0)
        pygame.draw.rect(self._surface, VIEWPORT.BOUNDARY,
                         pygame.Rect(x0, y0, x1 - x0, y1 - y0), 2)

        # Obstacles with selection highlight.
        for i, obs in enumerate(model.obstacles):
            self._draw_editor_obstacle(obs, to_screen,
                                       selected=(i == ctrl.selected_obstacle_index))

        # Live preview rectangle while drawing.
        if ctrl.preview_obstacle is not None and ctrl.preview_obstacle.width > 0 \
                and ctrl.preview_obstacle.height > 0:
            self._draw_preview_obstacle(ctrl.preview_obstacle, to_screen)

        # Start + Goal markers.
        self._draw_editor_start(model.start, to_screen, scale)
        self._draw_editor_goal(model.goal, to_screen, scale)

        # HUD inside the frame.
        self._draw_editor_hud(model, ctrl, int(offset_x), int(offset_y))

    # ------------------------------------------------------------------
    # Layout caching + coordinate conversions
    # ------------------------------------------------------------------
    def _compute_layout(self, world_w: float, world_h: float) -> Tuple[float, float, float]:
        W, H = self._surface.get_size()
        pad = 24
        sx = (W - 2 * pad) / max(world_w, 1e-6)
        sy = (H - 2 * pad) / max(world_h, 1e-6)
        scale = min(sx, sy)
        offset_x = (W - world_w * scale) / 2
        offset_y = (H - world_h * scale) / 2
        return offset_x, offset_y, scale

    def _cache_layout(self, offset_x: float, offset_y: float, scale: float,
                      world_w: float, world_h: float) -> None:
        self._last_offset_x = offset_x
        self._last_offset_y = offset_y
        self._last_scale = scale
        self._last_world_size = (world_w, world_h)

    def screen_to_world(self, sx: int, sy: int) -> Tuple[float, float]:
        """Inverse of the to_screen transform used at the last render."""
        if self._last_scale <= 0:
            return 0.0, 0.0
        W, H = self._surface.get_size()
        # Map widget coords → surface coords (we paint surface scaled to widget rect).
        widget_w = max(1, self.width())
        widget_h = max(1, self.height())
        surf_x = sx * (W / widget_w)
        surf_y = sy * (H / widget_h)
        wx = (surf_x - self._last_offset_x) / self._last_scale
        wy = (H - surf_y - self._last_offset_y) / self._last_scale
        return wx, wy

    # ------------------------------------------------------------------
    def paintEvent(self, event):  # noqa: N802
        W, H = self._surface.get_size()
        raw = pygame.image.tostring(self._surface, "RGB")
        image = QImage(raw, W, H, W * 3, QImage.Format_RGB888)
        painter = QPainter(self)
        painter.drawImage(self.rect(), image)
        painter.end()

    # ------------------------------------------------------------------
    # Keyboard → manual controller
    # ------------------------------------------------------------------
    _KEY_MAP = {
        Qt.Key_Up: "up", Qt.Key_W: "up",
        Qt.Key_Down: "down", Qt.Key_S: "down",
        Qt.Key_Left: "left", Qt.Key_A: "left",
        Qt.Key_Right: "right", Qt.Key_D: "right",
    }

    def keyPressEvent(self, event):  # noqa: N802
        if event.isAutoRepeat():
            return
        name = self._KEY_MAP.get(event.key())
        if name and self._on_key_press is not None:
            self._on_key_press(name)
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event):  # noqa: N802
        if event.isAutoRepeat():
            return
        name = self._KEY_MAP.get(event.key())
        if name and self._on_key_release is not None:
            self._on_key_release(name)
        else:
            super().keyReleaseEvent(event)

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------
    def _draw_grid(self, env, scale, offset_x, offset_y, H) -> None:
        """1-metre minor grid, 5-metre major. Both very subtle."""
        for i in range(int(env.width) + 1):
            x = int(offset_x + i * scale)
            color = VIEWPORT.GRID_AXIS if i % 5 == 0 else VIEWPORT.GRID_FAINT
            pygame.draw.line(self._surface, color,
                             (x, int(offset_y)), (x, int(H - offset_y)), 1)
        for j in range(int(env.height) + 1):
            y = int(H - offset_y - j * scale)
            color = VIEWPORT.GRID_AXIS if j % 5 == 0 else VIEWPORT.GRID_FAINT
            pygame.draw.line(self._surface, color,
                             (int(offset_x), y),
                             (int(offset_x + env.width * scale), y), 1)

    def _draw_world_frame(self, env, to_screen) -> None:
        x0, y0 = to_screen(0, env.height)
        x1, y1 = to_screen(env.width, 0)
        rect = pygame.Rect(x0, y0, x1 - x0, y1 - y0)
        pygame.draw.rect(self._surface, VIEWPORT.BOUNDARY, rect, 2)

    def _draw_obstacles(self, env, to_screen) -> None:
        for obstacle in env.obstacles:
            if obstacle.width < 0.15 or obstacle.height < 0.15:
                continue
            x0, y0 = to_screen(
                obstacle.x - obstacle.width / 2,
                obstacle.y + obstacle.height / 2,
            )
            x1, y1 = to_screen(
                obstacle.x + obstacle.width / 2,
                obstacle.y - obstacle.height / 2,
            )
            rect = pygame.Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0))
            pygame.draw.rect(self._surface, VIEWPORT.OBSTACLE, rect)
            pygame.draw.rect(self._surface, VIEWPORT.OBSTACLE_BORDER, rect, 1)

    def _draw_goal(self, env, to_screen, scale) -> None:
        gx, gy = env.goal
        cx, cy = to_screen(gx, gy)
        radius = max(8, int(0.3 * scale))
        # Two-ring goal: filled core + faint outline halo.
        pygame.draw.circle(self._surface, VIEWPORT.GOAL, (cx, cy), radius)
        pygame.draw.circle(self._surface, VIEWPORT.GOAL_RING,
                           (cx, cy), radius + 4, 1)
        # Crosshair.
        pygame.draw.line(self._surface, VIEWPORT.GOAL_RING,
                         (cx - radius - 6, cy), (cx - radius - 2, cy), 1)
        pygame.draw.line(self._surface, VIEWPORT.GOAL_RING,
                         (cx + radius + 2, cy), (cx + radius + 6, cy), 1)

    def _draw_rays(self, robot, env, to_screen) -> None:
        sensor = robot.distance_sensor
        endpoints = sensor.get_ray_endpoints(robot.get_state())
        sx_world = robot.state['x']
        sy_world = robot.state['y']
        rx, ry = to_screen(sx_world, sy_world)
        w = float(getattr(env, "width", 0.0))
        h = float(getattr(env, "height", 0.0))

        for dist, (ex, ey) in zip(sensor.distances, endpoints):
            # Visual safety net: clip the segment to the world AABB even
            # if the sensor reading is briefly stale (e.g. between Reset
            # and the next sensor update).
            if w > 0 and h > 0:
                ex, ey = _clip_segment_to_aabb(
                    sx_world, sy_world, ex, ey, 0.0, 0.0, w, h
                )

            color = (VIEWPORT.RAY_HIT if dist < sensor.max_range - 1e-3
                     else VIEWPORT.RAY_FREE)
            ex_s, ey_s = to_screen(ex, ey)
            pygame.draw.line(self._surface, color, (rx, ry), (ex_s, ey_s), 1)
            if color == VIEWPORT.RAY_HIT:
                pygame.draw.circle(self._surface, VIEWPORT.RAY_HIT,
                                   (ex_s, ey_s), 2)

    def _draw_robot(self, robot, to_screen, scale) -> None:
        corners = robot.get_corners()
        pts = [to_screen(cx, cy) for cx, cy in corners]
        pygame.draw.polygon(self._surface, VIEWPORT.ROBOT_BODY, pts)
        pygame.draw.polygon(self._surface, VIEWPORT.ROBOT_OUTLINE, pts, 1)

        # Heading triangle.
        x = robot.state['x']
        y = robot.state['y']
        theta = robot.state['theta']
        nose_offset = robot.length / 2 + 0.06
        nose = (x + nose_offset * np.cos(theta),
                y + nose_offset * np.sin(theta))
        base_offset = robot.length / 2 - 0.04
        side = 0.07
        left = (
            x + base_offset * np.cos(theta) - side * np.sin(theta),
            y + base_offset * np.sin(theta) + side * np.cos(theta),
        )
        right = (
            x + base_offset * np.cos(theta) + side * np.sin(theta),
            y + base_offset * np.sin(theta) - side * np.cos(theta),
        )
        pygame.draw.polygon(self._surface, VIEWPORT.ROBOT_FRONT,
                            [to_screen(*nose), to_screen(*left), to_screen(*right)])

        # Centre dot.
        cx, cy = to_screen(x, y)
        pygame.draw.circle(self._surface, VIEWPORT.ROBOT_OUTLINE, (cx, cy), 2)

    def _draw_trail(self, robot, to_screen) -> None:
        trail = robot.get_trajectory()
        if len(trail) < 2:
            return
        step = max(1, len(trail) // 600)
        pts = [to_screen(x, y) for x, y in trail[::step]]
        if len(pts) >= 2:
            pygame.draw.lines(self._surface, VIEWPORT.TRAIL, False, pts, 2)

    def _draw_path(self, engine, to_screen) -> None:
        controller = engine.controller
        path = getattr(controller, "path", None)
        if not path:
            return
        pts = [to_screen(x, y) for x, y in path]
        if len(pts) >= 2:
            pygame.draw.lines(self._surface, VIEWPORT.PATH, False, pts, 2)
        for px, py in pts:
            pygame.draw.circle(self._surface, VIEWPORT.PATH, (px, py), 2)

    # ------------------------------------------------------------------
    # HUD
    # ------------------------------------------------------------------
    def _draw_hud(self, engine, frame_left: int, frame_top: int) -> None:
        """
        HUD pinned inside the world frame's top-left corner.

        Two columns: muted caption + monospaced value. The inner padding
        is generous enough to keep text clear of the frame border and the
        first metre of world content.
        """
        state = engine.robot.get_state()
        rows = [
            ("TIME",      f"{engine.time:6.2f} s"),
            ("POSITION",  f"({state['x']:5.2f}, {state['y']:5.2f}) m"),
            ("HEADING",   f"{np.degrees(state['theta']):+6.1f}°"),
            ("VELOCITY",  f"{state['v']:+.2f} m/s   ω {state['omega']:+.2f} rad/s"),
            ("MIN RAY",   f"{engine.robot.distance_sensor.get_minimum_distance():.2f} m"),
            ("CONTROL",   f"{engine.controller.get_name()}"),
        ]
        # Inner inset from the frame border.
        inset = 12
        x = frame_left + inset
        y = frame_top + inset
        col_w = 84
        for caption, value in rows:
            cap_surf = self._font_caption.render(caption, True, VIEWPORT.HUD_TEXT_MUTED)
            val_surf = self._font_hud.render(value, True, VIEWPORT.HUD_TEXT)
            self._surface.blit(cap_surf, (x, y))
            self._surface.blit(val_surf, (x + col_w, y - 1))
            y += 18

    def _draw_status_pill(self, engine, frame_right: int, frame_bottom: int) -> None:
        """
        Status pill pinned inside the world frame's bottom-right corner.

        Sits just inside the frame so it never overlaps the border or
        anything outside the viewport.
        """
        if engine.goal_reached:
            text, fg = "GOAL REACHED", VIEWPORT.GOAL
        elif engine.timed_out:
            text, fg = "TIMEOUT", (210, 153, 34)
        elif engine.robot.collision_sensor.is_colliding():
            text, fg = "COLLISION", VIEWPORT.RAY_HIT
        else:
            return

        surf = self._font_pill.render(text, True, fg)
        pad_x, pad_y = 12, 6
        inset = 12
        pill_w = surf.get_width() + 2 * pad_x
        pill_h = surf.get_height() + 2 * pad_y
        rect = pygame.Rect(
            frame_right - inset - pill_w,
            frame_bottom - inset - pill_h,
            pill_w,
            pill_h,
        )
        pygame.draw.rect(self._surface, VIEWPORT.HUD_PILL_BG, rect, border_radius=10)
        pygame.draw.rect(self._surface, VIEWPORT.HUD_PILL_BORDER, rect, 1, border_radius=10)
        self._surface.blit(surf, (rect.x + pad_x, rect.y + pad_y))

    # ------------------------------------------------------------------
    # Mouse routing — active only while edit mode is on.
    # ------------------------------------------------------------------
    @staticmethod
    def _qt_button_name(button) -> Optional[str]:
        if button == Qt.LeftButton:
            return "left"
        if button == Qt.RightButton:
            return "right"
        if button == Qt.MiddleButton:
            return "middle"
        return None

    def mousePressEvent(self, event):  # noqa: N802
        if self._edit_mode and self._editor_controller is not None:
            btn = self._qt_button_name(event.button())
            if btn is None:
                return
            wx, wy = self.screen_to_world(event.x(), event.y())
            self._editor_controller.on_mouse_press(wx, wy, btn)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._edit_mode and self._editor_controller is not None:
            wx, wy = self.screen_to_world(event.x(), event.y())
            self._editor_controller.on_mouse_move(wx, wy)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if self._edit_mode and self._editor_controller is not None:
            btn = self._qt_button_name(event.button())
            if btn is None:
                return
            wx, wy = self.screen_to_world(event.x(), event.y())
            self._editor_controller.on_mouse_release(wx, wy, btn)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Editor drawing primitives
    # ------------------------------------------------------------------
    def _draw_grid_simple(self, world_w: float, world_h: float, scale: float,
                          offset_x: float, offset_y: float, H: int) -> None:
        """Same look as _draw_grid but works without an Environment object."""
        for i in range(int(world_w) + 1):
            x = int(offset_x + i * scale)
            color = VIEWPORT.GRID_AXIS if i % 5 == 0 else VIEWPORT.GRID_FAINT
            pygame.draw.line(self._surface, color,
                             (x, int(offset_y)), (x, int(H - offset_y)), 1)
        for j in range(int(world_h) + 1):
            y = int(H - offset_y - j * scale)
            color = VIEWPORT.GRID_AXIS if j % 5 == 0 else VIEWPORT.GRID_FAINT
            pygame.draw.line(self._surface, color,
                             (int(offset_x), y),
                             (int(offset_x + world_w * scale), y), 1)

    def _draw_editor_obstacle(self, obs, to_screen, selected: bool = False) -> None:
        x0, y0 = to_screen(obs.x - obs.width / 2, obs.y + obs.height / 2)
        x1, y1 = to_screen(obs.x + obs.width / 2, obs.y - obs.height / 2)
        rect = pygame.Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0))
        pygame.draw.rect(self._surface, VIEWPORT.OBSTACLE, rect)
        outline = (108, 158, 255) if selected else VIEWPORT.OBSTACLE_BORDER
        pygame.draw.rect(self._surface, outline, rect, 2 if selected else 1)
        if selected:
            handles = [(rect.x, rect.y), (rect.right - 1, rect.y),
                       (rect.x, rect.bottom - 1), (rect.right - 1, rect.bottom - 1)]
            for hx, hy in handles:
                pygame.draw.rect(self._surface, (255, 211, 92),
                                 pygame.Rect(hx - 3, hy - 3, 6, 6))

    def _draw_preview_obstacle(self, obs, to_screen) -> None:
        x0, y0 = to_screen(obs.x - obs.width / 2, obs.y + obs.height / 2)
        x1, y1 = to_screen(obs.x + obs.width / 2, obs.y - obs.height / 2)
        rect = pygame.Rect(x0, y0, max(1, x1 - x0), max(1, y1 - y0))
        pygame.draw.rect(self._surface, (255, 211, 92), rect, 2)

    def _draw_editor_start(self, start, to_screen, scale) -> None:
        cx, cy = to_screen(start.x, start.y)
        radius = max(6, int(0.18 * scale))
        pygame.draw.circle(self._surface, VIEWPORT.ROBOT_BODY, (cx, cy), radius)
        pygame.draw.circle(self._surface, VIEWPORT.ROBOT_OUTLINE, (cx, cy), radius, 1)
        ax = start.x + 0.45 * np.cos(start.theta)
        ay = start.y + 0.45 * np.sin(start.theta)
        end = to_screen(ax, ay)
        pygame.draw.line(self._surface, VIEWPORT.ROBOT_OUTLINE, (cx, cy), end, 2)
        head_size = 0.12
        left = (ax - head_size * np.cos(start.theta - 0.5),
                ay - head_size * np.sin(start.theta - 0.5))
        right = (ax - head_size * np.cos(start.theta + 0.5),
                 ay - head_size * np.sin(start.theta + 0.5))
        pygame.draw.polygon(self._surface, VIEWPORT.ROBOT_FRONT,
                            [end, to_screen(*left), to_screen(*right)])
        label = self._font_pill.render("S", True, VIEWPORT.ROBOT_OUTLINE)
        self._surface.blit(label, (cx - label.get_width() // 2 - 1,
                                   cy - label.get_height() // 2))

    def _draw_editor_goal(self, goal, to_screen, scale) -> None:
        cx, cy = to_screen(goal.x, goal.y)
        radius = max(6, int(0.3 * scale))
        pygame.draw.circle(self._surface, VIEWPORT.GOAL, (cx, cy), radius)
        pygame.draw.circle(self._surface, VIEWPORT.GOAL_RING, (cx, cy),
                           radius + 3, 1)
        label = self._font_pill.render("G", True, (8, 19, 12))
        self._surface.blit(label, (cx - label.get_width() // 2,
                                   cy - label.get_height() // 2))

    def _draw_editor_hud(self, model, ctrl, frame_left: int, frame_top: int) -> None:
        rows = [
            ("MODE",       "EDIT"),
            ("TOOL",       ctrl.tool_name().replace("_", " ")),
            ("SIZE",       f"{model.width:.1f} x {model.height:.1f} m"),
            ("OBSTACLES",  f"{len(model.obstacles)}"),
            ("SNAP",       f"{ctrl.grid_step:.2f} m" if ctrl.snap_to_grid else "off"),
            ("SELECTED",   "—" if ctrl.selected_obstacle_index is None
                                 else f"#{ctrl.selected_obstacle_index + 1}"),
        ]
        inset = 12
        x = frame_left + inset
        y = frame_top + inset
        col_w = 90
        for caption, value in rows:
            cap_surf = self._font_caption.render(caption, True, VIEWPORT.HUD_TEXT_MUTED)
            val_surf = self._font_hud.render(value, True, VIEWPORT.HUD_TEXT)
            self._surface.blit(cap_surf, (x, y))
            self._surface.blit(val_surf, (x + col_w, y - 1))
            y += 18

    def _draw_placeholder(self, text: str) -> None:
        font = pygame.font.SysFont("Segoe UI,Inter", 14)
        surf = font.render(text, True, VIEWPORT.HUD_TEXT_MUTED)
        rect = surf.get_rect(center=self._surface.get_rect().center)
        self._surface.blit(surf, rect)


def _clip_segment_to_aabb(
    sx: float, sy: float, ex: float, ey: float,
    min_x: float, min_y: float, max_x: float, max_y: float,
) -> tuple:
    """
    Clip segment (sx,sy)→(ex,ey) so it stops at the AABB boundary.

    Assumes (sx, sy) is inside (or on) the box; returns the endpoint
    moved inward so the segment fits. If the start is outside (shouldn't
    happen for a robot inside the world), returns the original end.
    """
    dx = ex - sx
    dy = ey - sy
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return ex, ey

    t_exit = 1.0
    if dx > 1e-9:
        t_exit = min(t_exit, (max_x - sx) / dx)
    elif dx < -1e-9:
        t_exit = min(t_exit, (min_x - sx) / dx)
    if dy > 1e-9:
        t_exit = min(t_exit, (max_y - sy) / dy)
    elif dy < -1e-9:
        t_exit = min(t_exit, (min_y - sy) / dy)

    t_exit = max(0.0, min(1.0, t_exit))
    return sx + t_exit * dx, sy + t_exit * dy
