"""
Origami Grid Editor — как ORIPA.
Aux ∩ Aux: кликабельно, невидимо.
Все невидимые узлы — кликабельны.
Координаты — математически точные.
+ Undo/Redo (Ctrl+Z / Ctrl+Y)
+ Исправлено: призрачные точки после Undo
+ Исправлено: подсветка узлов в режиме удаления
"""

import wx
import copy


def line_intersection_rel(line1_rel, line2_rel):
    """Пересечение двух отрезков в относительных координатах [0,1]x[0,1]"""
    (x1, y1), (x2, y2) = line1_rel
    (x3, y3), (x4, y4) = line2_rel

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return None

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

    if 0 <= t <= 1 and 0 <= u <= 1:
        ix = x1 + t * (x2 - x1)
        iy = y1 + t * (y2 - y1)
        return (round(ix, 12), round(iy, 12))
    return None


class GridCanvas(wx.Frame):
    MODE_INPUT = "input"
    MODE_DELETE = "delete"

    LINE_MOUNTAIN = "mountain"
    LINE_VALLEY = "valley"
    LINE_AUX = "aux"

    def __init__(self, parent, title):
        super(GridCanvas, self).__init__(parent, title=title, size=(900, 650))

        self.div_num = 4
        self.margin = 50

        # --- Относительные координаты ---
        self.rel_endpoint_points = []
        self.rel_intersections = set()
        self.rel_invisible = set()

        # --- Абсолютные точки ---
        self.hover_point = None
        self.selected_point = None

        self.lines = []  # [(p1_abs, p2_abs, type)]

        self.mode = self.MODE_INPUT
        self.line_type = self.LINE_MOUNTAIN
        self.hovered_line = None
        self.hovered_segment = None

        # --- История Undo/Redo ---
        self.history = []
        self.history_index = -1
        self.max_history = 50

        # ------------------- GUI -------------------
        self.panel = wx.Panel(self)
        self.canvas = wx.Panel(self.panel, style=wx.FULL_REPAINT_ON_RESIZE)
        self.canvas.SetBackgroundColour(wx.WHITE)

        self.control_panel = wx.Panel(self.panel)
        self.control_panel.SetBackgroundColour(wx.Colour(240, 240, 240))

        # --- Радиокнопки ---
        self.radio_input = wx.RadioButton(self.control_panel, label="InputLine", style=wx.RB_GROUP)
        self.radio_delete = wx.RadioButton(self.control_panel, label="DeleteLine")
        self.radio_input.SetValue(True)

        self.radio_mountain = wx.RadioButton(self.control_panel, label="Mountain", style=wx.RB_GROUP)
        self.radio_valley = wx.RadioButton(self.control_panel, label="Valley")
        self.radio_aux = wx.RadioButton(self.control_panel, label="Aux")
        self.radio_mountain.SetValue(True)

        self.radio_input.Bind(wx.EVT_RADIOBUTTON, lambda e: self.set_mode(self.MODE_INPUT))
        self.radio_delete.Bind(wx.EVT_RADIOBUTTON, lambda e: self.set_mode(self.MODE_DELETE))
        self.radio_mountain.Bind(wx.EVT_RADIOBUTTON, lambda e: self.set_line_type(self.LINE_MOUNTAIN))
        self.radio_valley.Bind(wx.EVT_RADIOBUTTON, lambda e: self.set_line_type(self.LINE_VALLEY))
        self.radio_aux.Bind(wx.EVT_RADIOBUTTON, lambda e: self.set_line_type(self.LINE_AUX))

        # --- Div Num ---
        self.div_label = wx.StaticText(self.control_panel, label="Div Num")
        self.div_text = wx.TextCtrl(self.control_panel, value="4", size=(50, -1))
        self.set_button = wx.Button(self.control_panel, label="Set")
        self.set_button.Bind(wx.EVT_BUTTON, self.on_set_div)

        # --- Undo / Redo ---
        self.undo_button = wx.Button(self.control_panel, label="Undo")
        self.redo_button = wx.Button(self.control_panel, label="Redo")
        self.undo_button.Bind(wx.EVT_BUTTON, self.on_undo)
        self.redo_button.Bind(wx.EVT_BUTTON, self.on_redo)

        # --- Сборка интерфейса ---
        ctrl_sizer = wx.BoxSizer(wx.VERTICAL)
        ctrl_sizer.Add(self.radio_input, 0, wx.ALL, 5)
        ctrl_sizer.Add(self.radio_delete, 0, wx.ALL, 5)
        ctrl_sizer.Add(wx.StaticLine(self.control_panel), 0, wx.EXPAND | wx.ALL, 5)
        ctrl_sizer.Add(self.radio_mountain, 0, wx.ALL, 5)
        ctrl_sizer.Add(self.radio_valley, 0, wx.ALL, 5)
        ctrl_sizer.Add(self.radio_aux, 0, wx.ALL, 5)
        ctrl_sizer.Add(wx.StaticLine(self.control_panel), 0, wx.EXPAND | wx.ALL, 5)
        ctrl_sizer.Add(self.div_label, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        ctrl_sizer.Add(self.div_text, 0, wx.ALL | wx.EXPAND, 5)
        ctrl_sizer.Add(self.set_button, 0, wx.ALL | wx.EXPAND, 5)
        ctrl_sizer.AddStretchSpacer()
        ctrl_sizer.Add(self.undo_button, 0, wx.ALL | wx.EXPAND, 5)
        ctrl_sizer.Add(self.redo_button, 0, wx.ALL | wx.EXPAND, 5)
        self.control_panel.SetSizer(ctrl_sizer)

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add(self.control_panel, 0, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(self.canvas, 1, wx.EXPAND)
        self.panel.SetSizer(main_sizer)

        # --- События ---
        self.canvas.Bind(wx.EVT_PAINT, self.on_paint)
        self.canvas.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.canvas.Bind(wx.EVT_LEFT_DOWN, self.on_left_click)
        self.canvas.Bind(wx.EVT_SIZE, self.on_resize)
        self.canvas.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        # --- Инициализация ---
        self.update_grid_size()
        self.save_state()
        self.update_undo_redo_buttons()
        self.Show()

    # ------------------------------------------------------------------ #
    # --------------------------  Undo/Redo  --------------------------- #
    # ------------------------------------------------------------------ #
    def save_state(self):
        """Сохраняет текущее состояние линий"""
        state = copy.deepcopy(self.lines)
        if self.history_index < len(self.history) - 1:
            self.history = self.history[:self.history_index + 1]
        self.history.append(state)
        self.history_index += 1
        if len(self.history) > self.max_history:
            self.history.pop(0)
            self.history_index -= 1
        self.update_undo_redo_buttons()

    def restore_state(self, state):
        """Восстанавливает состояние и пересчитывает ВСЁ"""
        self.lines = copy.deepcopy(state)
        self.selected_point = None
        self.hovered_line = None
        self.hovered_segment = None

        # Полное обновление
        self.update_all_intersections()
        self.update_endpoint_points()
        self.canvas.Refresh()

    def on_undo(self, event):
        if self.history_index > 0:
            self.history_index -= 1
            self.restore_state(self.history[self.history_index])
            self.update_undo_redo_buttons()

    def on_redo(self, event):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.restore_state(self.history[self.history_index])
            self.update_undo_redo_buttons()

    def update_undo_redo_buttons(self):
        self.undo_button.Enable(self.history_index > 0)
        self.redo_button.Enable(self.history_index < len(self.history) - 1)

    def on_key_down(self, event):
        key = event.GetKeyCode()
        if event.ControlDown():
            if key == ord('Z'):
                self.on_undo(None)
            elif key == ord('Y'):
                self.on_redo(None)
        event.Skip()

    # ------------------------------------------------------------------ #
    # --------------------------  UI helpers  -------------------------- #
    # ------------------------------------------------------------------ #
    def set_mode(self, mode):
        self.mode = mode
        self.hovered_line = None
        self.hovered_segment = None
        self.canvas.Refresh()

    def set_line_type(self, line_type):
        self.line_type = line_type
        self.canvas.Refresh()

    def on_resize(self, event):
        self.update_grid_size()
        self.canvas.Refresh()

    def update_grid_size(self):
        size = self.canvas.GetSize()
        usable = min(size.width, size.height) - 2 * self.margin
        self.grid_size = usable / self.div_num if self.div_num > 0 else 50.0
        self.update_all_intersections()
        self.canvas.Refresh()

    def on_set_div(self, event):
        try:
            new_div = int(self.div_text.GetValue())
            if 1 <= new_div <= 50:
                self.div_num = new_div
                self.update_grid_size()
                self.save_state()
            else:
                wx.MessageBox("Введите число от 1 до 50", "Ошибка", wx.OK | wx.ICON_ERROR)
        except ValueError:
            wx.MessageBox("Введите целое число", "Ошибка", wx.OK | wx.ICON_ERROR)

    # ------------------------------------------------------------------ #
    # ---------------------  Координатные функции  --------------------- #
    # ------------------------------------------------------------------ #
    def get_grid_bounds(self):
        w, h = self.canvas.GetSize()
        size = min(w, h) - 2 * self.margin
        left = (w - size) / 2
        top = (h - size) / 2
        return left, top, left + size, top + size

    def rel_to_abs(self, rel_point):
        if not rel_point:
            return None
        left, top, right, bottom = self.get_grid_bounds()
        size = right - left
        x_rel, y_rel = rel_point
        x_abs = left + x_rel * size
        y_abs = bottom - y_rel * size
        return (x_abs, y_abs)

    def abs_to_rel(self, abs_point):
        if not abs_point:
            return None
        left, top, right, bottom = self.get_grid_bounds()
        size = right - left
        if size == 0:
            return None
        x_abs, y_abs = abs_point
        x_rel = (x_abs - left) / size
        y_rel = (bottom - y_abs) / size
        return (x_rel, y_rel)

    # ------------------------------------------------------------------ #
    # --------------------------  Узлы  -------------------------------- #
    # ------------------------------------------------------------------ #
    def get_nearest_point(self, pos):
        x_abs, y_abs = pos
        rel_pos = self.abs_to_rel(pos)
        if not rel_pos:
            return None

        left, top, right, bottom = self.get_grid_bounds()
        if not (left <= x_abs <= right and top <= y_abs <= bottom):
            return None

        gx_rel = round(rel_pos[0] * self.div_num) / self.div_num
        gy_rel = round(rel_pos[1] * self.div_num) / self.div_num
        gx_rel = max(0.0, min(1.0, gx_rel))
        gy_rel = max(0.0, min(1.0, gy_rel))
        grid_point_rel = (gx_rel, gy_rel)

        candidates_rel = [grid_point_rel]
        candidates_rel.extend(self.rel_endpoint_points)
        candidates_rel.extend(self.rel_intersections)
        candidates_rel.extend(self.rel_invisible)
        candidates_rel = list(set(candidates_rel))

        candidates_abs = [self.rel_to_abs(p) for p in candidates_rel]
        if not candidates_abs:
            return self.rel_to_abs(grid_point_rel)

        nearest_abs = min(candidates_abs,
                          key=lambda p: (p[0] - x_abs) ** 2 + (p[1] - y_abs) ** 2)
        return nearest_abs

    def update_all_intersections(self):
        self.rel_intersections = set()
        self.rel_invisible = set()

        mv_lines = []
        for p1_abs, p2_abs, ltype in self.lines:
            if ltype != self.LINE_AUX:
                p1_rel = self.abs_to_rel(p1_abs)
                p2_rel = self.abs_to_rel(p2_abs)
                if p1_rel and p2_rel:
                    mv_lines.append((p1_rel, p2_rel, ltype))

        for i in range(len(mv_lines)):
            for j in range(i + 1, len(mv_lines)):
                inter = line_intersection_rel(mv_lines[i][:2], mv_lines[j][:2])
                if inter:
                    self.rel_intersections.add(inter)

        aux_lines = []
        for p1_abs, p2_abs, ltype in self.lines:
            if ltype == self.LINE_AUX:
                p1_rel = self.abs_to_rel(p1_abs)
                p2_rel = self.abs_to_rel(p2_abs)
                if p1_rel and p2_rel:
                    aux_lines.append((p1_rel, p2_rel))

        for k in range(1, self.div_num):
            y_rel = k / self.div_num
            x_rel = k / self.div_num
            grid_h = ((0.0, y_rel), (1.0, y_rel))
            grid_v = ((x_rel, 0.0), (x_rel, 1.0))
            for aux in aux_lines:
                inter = line_intersection_rel(aux, grid_h)
                if inter: self.rel_invisible.add(inter)
                inter = line_intersection_rel(aux, grid_v)
                if inter: self.rel_invisible.add(inter)

        bounds_rel = [((0, 0), (1, 0)), ((1, 0), (1, 1)), ((1, 1), (0, 1)), ((0, 1), (0, 0))]
        for b1, b2 in bounds_rel:
            for aux in aux_lines:
                inter = line_intersection_rel(aux, (b1, b2))
                if inter: self.rel_invisible.add(inter)

        for aux in aux_lines:
            for mv_p1, mv_p2, _ in mv_lines:
                inter = line_intersection_rel(aux, (mv_p1, mv_p2))
                if inter: self.rel_invisible.add(inter)

        for i in range(len(aux_lines)):
            for j in range(i + 1, len(aux_lines)):
                inter = line_intersection_rel(aux_lines[i], aux_lines[j])
                if inter: self.rel_invisible.add(inter)

    def update_endpoint_points(self):
        self.rel_endpoint_points = []
        for p1_abs, p2_abs, ltype in self.lines:
            if ltype != self.LINE_AUX:
                rel1 = self.abs_to_rel(p1_abs)
                rel2 = self.abs_to_rel(p2_abs)
                if rel1: self.rel_endpoint_points.append(rel1)
                if rel2: self.rel_endpoint_points.append(rel2)
        self.rel_endpoint_points = list(set(self.rel_endpoint_points))

    # ------------------------------------------------------------------ #
    # -----------------------  Удаление сегментов  --------------------- #
    # ------------------------------------------------------------------ #
    def get_closest_line_and_segment(self, pos):
        x, y = pos
        min_dist = float('inf')
        result = None

        for idx, (p1, p2, ltype) in enumerate(self.lines):
            points_on_line = [p1, p2]
            inter_set = self.rel_intersections if ltype != self.LINE_AUX else self.rel_invisible
            for inter_rel in inter_set:
                inter_abs = self.rel_to_abs(inter_rel)
                if self.is_point_on_segment(inter_abs, (p1, p2), tol=1e-3):
                    points_on_line.append(inter_abs)

            points_on_line = sorted(set(points_on_line), key=lambda pt: (pt[0], pt[1]))

            for i in range(len(points_on_line) - 1):
                a, b = points_on_line[i], points_on_line[i + 1]
                dist = self.distance_to_segment(pos, (a, b))
                if dist < 20 and dist < min_dist:
                    min_dist = dist
                    result = (idx, a, b)

            if not result:
                dist1 = self.distance_to_point(pos, p1)
                dist2 = self.distance_to_point(pos, p2)
                if min(dist1, dist2) < 25:
                    result = (idx, p1, p2)

        return result

    def distance_to_segment(self, point, segment):
        px, py = point
        x1, y1 = segment[0]
        x2, y2 = segment[1]
        dx, dy = x2 - x1, y2 - y1
        if dx == dy == 0:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0, min(1, t))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5

    def distance_to_point(self, p1, p2):
        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

    def is_point_on_segment(self, point, segment, tol=1e-6):
        a, b = segment
        cross = (point[1] - a[1]) * (b[0] - a[0]) - (point[0] - a[0]) * (b[1] - a[1])
        if abs(cross) > tol:
            return False
        dot = (point[0] - a[0]) * (b[0] - a[0]) + (point[1] - a[1]) * (b[1] - a[1])
        if dot < 0:
            return False
        squared_len = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
        if dot > squared_len:
            return False
        return True

    def points_equal(self, p1, p2, tol=1e-6):
        return abs(p1[0] - p2[0]) < tol and abs(p1[1] - p2[1]) < tol

    def remove_line_segment(self, line_idx, seg_start, seg_end):
        line = self.lines[line_idx]
        p1, p2, ltype = line

        points_on_line = [p1, p2]
        inter_set = self.rel_intersections if ltype != self.LINE_AUX else self.rel_invisible
        for inter_rel in inter_set:
            inter_abs = self.rel_to_abs(inter_rel)
            if self.is_point_on_segment(inter_abs, (p1, p2), tol=1e-3):
                points_on_line.append(inter_abs)
        points_on_line = sorted(set(points_on_line), key=lambda pt: (pt[0], pt[1]))

        start_idx = next((i for i, pt in enumerate(points_on_line)
                          if self.points_equal(pt, seg_start)), -1)
        end_idx = next((i for i, pt in enumerate(points_on_line)
                        if self.points_equal(pt, seg_end)), -1)

        if start_idx == -1 or end_idx == -1:
            return

        new_lines = []
        if start_idx > 0:
            new_lines.append((points_on_line[0], points_on_line[start_idx], ltype))
        if end_idx < len(points_on_line) - 1:
            new_lines.append((points_on_line[end_idx], points_on_line[-1], ltype))

        if new_lines:
            self.lines[line_idx] = new_lines[0]
            if len(new_lines) > 1:
                self.lines.insert(line_idx + 1, new_lines[1])
        else:
            del self.lines[line_idx]

        self.update_endpoint_points()
        self.update_all_intersections()
        self.save_state()

    # ------------------------------------------------------------------ #
    # ---------------------------  Мышь  ------------------------------- #
    # ------------------------------------------------------------------ #
    def on_mouse_move(self, event):
        pos = event.GetPosition()

        if self.mode == self.MODE_DELETE:
            self.hover_point = None  # Отключаем подсветку узла
            self.hovered_line = None
            self.hovered_segment = None
            result = self.get_closest_line_and_segment(pos)
            if result:
                idx, s1, s2 = result
                self.hovered_line = idx
                self.hovered_segment = (s1, s2)
        else:
            self.hover_point = self.get_nearest_point(pos)
            self.hovered_line = None
            self.hovered_segment = None

        self.canvas.Refresh()

    def on_left_click(self, event):
        pos = event.GetPosition()
        point_abs = self.get_nearest_point(pos)
        if point_abs is None:
            return

        point_rel = self.abs_to_rel(point_abs)
        if not point_rel:
            return

        left, top, right, bottom = self.get_grid_bounds()
        if not (left <= point_abs[0] <= right and top <= point_abs[1] <= bottom):
            return

        if self.mode == self.MODE_INPUT:
            if self.selected_point is not None:
                sel_rel = self.abs_to_rel(self.selected_point)
                if (abs(sel_rel[0] - point_rel[0]) < 1e-8 and
                        abs(sel_rel[1] - point_rel[1]) < 1e-8):
                    self.selected_point = None
                    self.canvas.Refresh()
                    return

            if self.selected_point is None:
                self.selected_point = point_abs
            else:
                p1_abs = self.selected_point
                p2_abs = point_abs
                self.lines.append((p1_abs, p2_abs, self.line_type))
                self.selected_point = None
                self.update_all_intersections()
                if self.line_type != self.LINE_AUX:
                    self.update_endpoint_points()
                self.save_state()

        elif self.mode == self.MODE_DELETE and self.hovered_segment:
            idx = self.hovered_line
            s1, s2 = self.hovered_segment
            self.remove_line_segment(idx, s1, s2)
            self.hovered_line = None
            self.hovered_segment = None

        self.canvas.Refresh()

    # ------------------------------------------------------------------ #
    # ----------------------  Точные координаты  ----------------------- #
    # ------------------------------------------------------------------ #
    def get_relative_coords(self, abs_point):
        if not abs_point:
            return None
        rel_point = self.abs_to_rel(abs_point)
        if not rel_point:
            return None

        all_rel = (self.rel_endpoint_points +
                   list(self.rel_intersections) +
                   list(self.rel_invisible))

        for cand in all_rel:
            if (abs(cand[0] - rel_point[0]) < 1e-10 and
                    abs(cand[1] - rel_point[1]) < 1e-10):
                return cand

        return (round(rel_point[0], 6), round(rel_point[1], 6))

    # ------------------------------------------------------------------ #
    # ---------------------------  Рисование  -------------------------- #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _i(x):
        return int(round(x))

    def on_paint(self, event):
        dc = wx.PaintDC(self.canvas)
        self.draw_grid_area(dc)
        self.draw_grid_lines(dc)
        self.draw_aux_lines(dc)
        self.draw_main_lines(dc)
        self.draw_hovered_segment(dc)
        self.draw_black_points(dc)
        self.draw_hover_point(dc)
        self.draw_preview_line(dc)
        self.draw_coordinates(dc)

    def draw_grid_area(self, dc):
        left, top, right, bottom = self.get_grid_bounds()
        dc.SetPen(wx.Pen(wx.BLACK, 2))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(self._i(left), self._i(top),
                         self._i(right - left), self._i(bottom - top))

    def draw_grid_lines(self, dc):
        left, top, right, bottom = self.get_grid_bounds()
        dc.SetPen(wx.Pen(wx.Colour(220, 220, 220), 1))
        x = left
        while x <= right:
            dc.DrawLine(self._i(x), self._i(top), self._i(x), self._i(bottom))
            x += self.grid_size
        y = top
        while y <= bottom:
            dc.DrawLine(self._i(left), self._i(y), self._i(right), self._i(y))
            y += self.grid_size

    def draw_aux_lines(self, dc):
        dc.SetPen(wx.Pen(wx.Colour(180, 180, 180), 1))
        for p1, p2, ltype in self.lines:
            if ltype == self.LINE_AUX:
                dc.DrawLine(self._i(p1[0]), self._i(p1[1]),
                            self._i(p2[0]), self._i(p2[1]))

    def draw_main_lines(self, dc):
        for p1, p2, ltype in self.lines:
            if ltype == self.LINE_MOUNTAIN:
                dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 2))
            elif ltype == self.LINE_VALLEY:
                dc.SetPen(wx.Pen(wx.Colour(0, 0, 255), 2))
            else:
                continue
            dc.DrawLine(self._i(p1[0]), self._i(p1[1]),
                        self._i(p2[0]), self._i(p2[1]))

    def draw_hovered_segment(self, dc):
        if self.mode == self.MODE_DELETE and self.hovered_segment:
            p1, p2 = self.hovered_segment
            dc.SetPen(wx.Pen(wx.Colour(0, 255, 0), 3))
            dc.DrawLine(self._i(p1[0]), self._i(p1[1]),
                        self._i(p2[0]), self._i(p2[1]))

    def draw_black_points(self, dc):
        dc.SetBrush(wx.Brush(wx.BLACK))
        dc.SetPen(wx.Pen(wx.BLACK, 1))
        for rel_p in self.rel_endpoint_points:
            p = self.rel_to_abs(rel_p)
            dc.DrawCircle(self._i(p[0]), self._i(p[1]), 3)
        for rel_p in self.rel_intersections:
            p = self.rel_to_abs(rel_p)
            dc.DrawCircle(self._i(p[0]), self._i(p[1]), 3)

    def draw_hover_point(self, dc):
        if self.hover_point:
            x, y = self.hover_point
            dc.SetBrush(wx.Brush(wx.Colour(0, 255, 0)))
            dc.SetPen(wx.Pen(wx.Colour(0, 255, 0), 2))
            dc.DrawCircle(self._i(x), self._i(y), 5)

    def draw_preview_line(self, dc):
        if self.selected_point and self.hover_point:
            color = (wx.Colour(255, 0, 0) if self.line_type == self.LINE_MOUNTAIN else
                     wx.Colour(0, 0, 255) if self.line_type == self.LINE_VALLEY else
                     wx.Colour(180, 180, 180))
            dc.SetPen(wx.Pen(color, 2, wx.PENSTYLE_DOT))
            sp = self.selected_point
            hp = self.hover_point
            dc.DrawLine(self._i(sp[0]), self._i(sp[1]),
                        self._i(hp[0]), self._i(hp[1]))

    def draw_coordinates(self, dc):
        if not self.hover_point:
            return
        rel = self.get_relative_coords(self.hover_point)
        if not rel:
            return
        x_rel, y_rel = rel
        text = f"x: {x_rel:.6f}, y: {y_rel:.6f}"

        font = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)
        dc.SetTextForeground(wx.Colour(0, 0, 0))
        text_w, text_h = dc.GetTextExtent(text)

        left, top, right, bottom = self.get_grid_bounds()
        x_center = (left + right) / 2
        y_pos = bottom + 8

        padding = 8
        bg_x = x_center - text_w / 2 - padding
        bg_y = y_pos - 2
        bg_w = text_w + 2 * padding
        bg_h = text_h + 4

        dc.SetBrush(wx.Brush(wx.Colour(255, 255, 255, 240)))
        dc.SetPen(wx.Pen(wx.Colour(100, 100, 100), 1))
        dc.DrawRoundedRectangle(self._i(bg_x), self._i(bg_y),
                                self._i(bg_w), self._i(bg_h), 5)

        dc.DrawText(text, self._i(x_center - text_w / 2), self._i(y_pos))


if __name__ == '__main__':
    app = wx.App(False)
    frame = GridCanvas(None, "Origami Grid Editor")
    app.MainLoop()