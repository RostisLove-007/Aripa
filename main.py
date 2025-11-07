"""
Origami Grid Editor — редактор сетки с режимами рисования и удаления.
Исправлено: удаление одиночных узлов после удаления сегментов.
"""

import wx


def line_intersection(line1, line2):
    """
    Вычисляет точку пересечения двух отрезков.
    """
    x1, y1 = line1[0]
    x2, y2 = line1[1]
    x3, y3 = line2[0]
    x4, y4 = line2[1]

    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return None

    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom

    if 0 <= t <= 1 and 0 <= u <= 1:
        return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


class GridCanvas(wx.Frame):
    MODE_INPUT = "input"
    MODE_DELETE = "delete"

    def __init__(self, parent, title):
        super(GridCanvas, self).__init__(parent, title=title, size=(900, 650))

        self.div_num = 4
        self.grid_size = 0
        self.margin = 50

        self.endpoint_points = []      # Только концы существующих линий
        self.intersection_points = set()  # Только текущие пересечения
        self.hover_point = None
        self.selected_point = None
        self.lines = []

        self.mode = self.MODE_INPUT
        self.hovered_line = None
        self.hovered_segment = None

        # --- Интерфейс ---
        self.panel = wx.Panel(self)
        self.canvas = wx.Panel(self.panel, style=wx.FULL_REPAINT_ON_RESIZE)
        self.canvas.SetBackgroundColour(wx.WHITE)

        self.control_panel = wx.Panel(self.panel)
        self.control_panel.SetBackgroundColour(wx.Colour(240, 240, 240))

        self.radio_input = wx.RadioButton(self.control_panel, label="InputLine", style=wx.RB_GROUP)
        self.radio_delete = wx.RadioButton(self.control_panel, label="DeleteLine")
        self.radio_input.SetValue(True)

        self.radio_input.Bind(wx.EVT_RADIOBUTTON, lambda e: self.set_mode(self.MODE_INPUT))
        self.radio_delete.Bind(wx.EVT_RADIOBUTTON, lambda e: self.set_mode(self.MODE_DELETE))

        self.div_label = wx.StaticText(self.control_panel, label="Div Num")
        self.div_text = wx.TextCtrl(self.control_panel, value="4", size=(50, -1))
        self.set_button = wx.Button(self.control_panel, label="Set")
        self.set_button.Bind(wx.EVT_BUTTON, self.on_set_div)

        ctrl_sizer = wx.BoxSizer(wx.VERTICAL)
        ctrl_sizer.Add(self.radio_input, 0, wx.ALL, 5)
        ctrl_sizer.Add(self.radio_delete, 0, wx.ALL, 5)
        ctrl_sizer.Add(wx.StaticLine(self.control_panel), 0, wx.EXPAND | wx.ALL, 5)
        ctrl_sizer.Add(self.div_label, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        ctrl_sizer.Add(self.div_text, 0, wx.ALL | wx.EXPAND, 5)
        ctrl_sizer.Add(self.set_button, 0, wx.ALL | wx.EXPAND, 5)
        ctrl_sizer.AddStretchSpacer()
        self.control_panel.SetSizer(ctrl_sizer)

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add(self.control_panel, 0, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(self.canvas, 1, wx.EXPAND)
        self.panel.SetSizer(main_sizer)

        self.canvas.Bind(wx.EVT_PAINT, self.on_paint)
        self.canvas.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.canvas.Bind(wx.EVT_LEFT_DOWN, self.on_left_click)
        self.canvas.Bind(wx.EVT_SIZE, self.on_resize)

        self.update_grid_size()
        self.Show()

    def set_mode(self, mode):
        self.mode = mode
        self.hovered_line = None
        self.hovered_segment = None
        self.canvas.Refresh()

    def on_resize(self, event):
        self.update_grid_size()
        self.canvas.Refresh()

    def update_grid_size(self):
        size = self.canvas.GetSize()
        usable = min(size.width, size.height) - 2 * self.margin
        self.grid_size = usable // self.div_num if self.div_num > 0 else 50
        self.canvas.Refresh()

    def on_set_div(self, event):
        try:
            new_div = int(self.div_text.GetValue())
            if 1 <= new_div <= 50:
                self.div_num = new_div
                self.update_grid_size()
            else:
                wx.MessageBox("Введите число от 1 до 50", "Ошибка", wx.OK | wx.ICON_ERROR)
        except ValueError:
            wx.MessageBox("Введите целое число", "Ошибка", wx.OK | wx.ICON_ERROR)

    def get_grid_bounds(self):
        w, h = self.canvas.GetSize()
        size = min(w, h) - 2 * self.margin
        left = (w - size) // 2
        top = (h - size) // 2
        return left, top, left + size, top + size

    def get_relative_coords(self, point):
        if not point:
            return None
        left, top, right, bottom = self.get_grid_bounds()
        x_abs, y_abs = point
        size = right - left
        if size == 0:
            return None
        x_rel = (x_abs - left) / size
        y_rel = (bottom - y_abs) / size
        return round(x_rel, 3), round(y_rel, 3)

    def get_nearest_point(self, pos):
        x, y = pos
        left, top, right, bottom = self.get_grid_bounds()
        if not (left <= x <= right and top <= y <= bottom):
            return None

        gx = left + round((x - left) / self.grid_size) * self.grid_size
        gy = top + round((y - top) / self.grid_size) * self.grid_size
        gx = max(left, min(gx, right))
        gy = max(top, min(gy, bottom))

        candidates = [(gx, gy)]
        candidates.extend(self.endpoint_points)
        candidates.extend(self.intersection_points)

        unique = [p for p in set(candidates) if left <= p[0] <= right and top <= p[1] <= bottom]
        if not unique:
            return (gx, gy)
        return min(unique, key=lambda p: (p[0] - x)**2 + (p[1] - y)**2)

    def update_intersections(self):
        """Пересчитывает пересечения — только между существующими линиями."""
        self.intersection_points = set()
        for i in range(len(self.lines)):
            for j in range(i + 1, len(self.lines)):
                inter = line_intersection(self.lines[i], self.lines[j])
                if inter:
                    left, top, right, bottom = self.get_grid_bounds()
                    if left <= inter[0] <= right and top <= inter[1] <= bottom:
                        self.intersection_points.add(inter)

    def update_endpoint_points(self):
        """Пересобирает endpoint_points — только концы активных линий."""
        used = set()
        for line in self.lines:
            used.add(line[0])
            used.add(line[1])
        self.endpoint_points = list(used)

    def get_closest_line_and_segment(self, pos):
        x, y = pos
        min_dist = float('inf')
        result = None

        for idx, line in enumerate(self.lines):
            p1, p2 = line
            points_on_line = [p1, p2]
            for inter in self.intersection_points:
                if self.is_point_on_segment(inter, line, tol=1e-5):
                    points_on_line.append(inter)

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
        """
        Удаляет сегмент (seg_start → seg_end).
        Если узел становится изолированным — он исчезает.
        """
        line = self.lines[line_idx]
        p1, p2 = line

        # Все точки на линии
        points_on_line = [p1, p2]
        for inter in self.intersection_points:
            if self.is_point_on_segment(inter, line, tol=1e-5):
                points_on_line.append(inter)
        points_on_line = sorted(set(points_on_line), key=lambda pt: (pt[0], pt[1]))

        # Индексы начала и конца удаляемого сегмента
        start_idx = next((i for i, pt in enumerate(points_on_line) if self.points_equal(pt, seg_start)), -1)
        end_idx = next((i for i, pt in enumerate(points_on_line) if self.points_equal(pt, seg_end)), -1)

        if start_idx == -1 or end_idx == -1:
            return

        # Новые линии (без удалённого сегмента)
        new_lines = []
        if start_idx > 0:
            new_lines.append((points_on_line[0], points_on_line[start_idx]))
        if end_idx < len(points_on_line) - 1:
            new_lines.append((points_on_line[end_idx], points_on_line[-1]))

        # Замена
        if new_lines:
            self.lines[line_idx] = new_lines[0]
            if len(new_lines) > 1:
                self.lines.insert(line_idx + 1, new_lines[1])
        else:
            del self.lines[line_idx]

        # КРИТИЧНО: пересчёт точек и пересечений
        self.update_endpoint_points()
        self.update_intersections()

    def on_mouse_move(self, event):
        pos = event.GetPosition()
        self.hover_point = self.get_nearest_point(pos)

        if self.mode == self.MODE_DELETE:
            self.hovered_line = None
            self.hovered_segment = None
            result = self.get_closest_line_and_segment(pos)
            if result:
                idx, s1, s2 = result
                self.hovered_line = idx
                self.hovered_segment = (s1, s2)
        else:
            self.hovered_line = None
            self.hovered_segment = None

        self.canvas.Refresh()

    def on_left_click(self, event):
        pos = event.GetPosition()
        point = self.get_nearest_point(pos)
        if point is None:
            return

        left, top, right, bottom = self.get_grid_bounds()
        if not (left <= point[0] <= right and top <= point[1] <= bottom):
            return

        if self.mode == self.MODE_INPUT:
            if self.selected_point is not None and self.points_equal(point, self.selected_point):
                self.selected_point = None
                self.canvas.Refresh()
                return

            if self.selected_point is None:
                self.selected_point = point
            else:
                p1 = self.selected_point
                p2 = point
                for p in [p1, p2]:
                    if p not in self.endpoint_points:
                        self.endpoint_points.append(p)
                self.lines.append((p1, p2))
                self.selected_point = None
                self.update_intersections()

        elif self.mode == self.MODE_DELETE and self.hovered_segment:
            idx = self.hovered_line
            s1, s2 = self.hovered_segment
            self.remove_line_segment(idx, s1, s2)
            self.hovered_line = None
            self.hovered_segment = None

        self.canvas.Refresh()

    def on_paint(self, event):
        dc = wx.PaintDC(self.canvas)
        self.draw_grid_area(dc)
        self.draw_grid_lines(dc)
        self.draw_lines(dc)
        self.draw_hovered_segment(dc)

        if self.mode == self.MODE_INPUT:
            self.draw_red_points(dc)
            self.draw_hover_point(dc)
            self.draw_preview_line(dc)
            self.draw_coordinates(dc)

    def draw_grid_area(self, dc):
        left, top, right, bottom = self.get_grid_bounds()
        dc.SetPen(wx.Pen(wx.BLACK, 2))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(left, top, right - left, bottom - top)

    def draw_grid_lines(self, dc):
        left, top, right, bottom = self.get_grid_bounds()
        dc.SetPen(wx.Pen(wx.Colour(220, 220, 220), 1))
        x = left
        while x <= right:
            dc.DrawLine(x, top, x, bottom)
            x += self.grid_size
        y = top
        while y <= bottom:
            dc.DrawLine(left, y, right, y)
            y += self.grid_size

    def draw_lines(self, dc):
        dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 2))
        for line in self.lines:
            dc.DrawLine(int(line[0][0]), int(line[0][1]), int(line[1][0]), int(line[1][1]))

    def draw_hovered_segment(self, dc):
        if self.mode == self.MODE_DELETE and self.hovered_segment:
            p1, p2 = self.hovered_segment
            dc.SetPen(wx.Pen(wx.Colour(0, 255, 0), 3))
            dc.DrawLine(int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]))

    def draw_red_points(self, dc):
        dc.SetBrush(wx.Brush(wx.Colour(255, 0, 0)))
        dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 1))
        for p in self.endpoint_points:
            dc.DrawCircle(int(p[0]), int(p[1]), 3)
        for p in self.intersection_points:
            dc.DrawCircle(int(p[0]), int(p[1]), 3)

    def draw_hover_point(self, dc):
        if self.hover_point:
            x, y = self.hover_point
            dc.SetBrush(wx.Brush(wx.Colour(0, 255, 0)))
            dc.SetPen(wx.Pen(wx.Colour(0, 255, 0), 2))
            dc.DrawCircle(int(x), int(y), 5)

    def draw_preview_line(self, dc):
        if self.selected_point and self.hover_point:
            dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 2, wx.PENSTYLE_DOT))
            sp = self.selected_point
            hp = self.hover_point
            dc.DrawLine(int(sp[0]), int(sp[1]), int(hp[0]), int(hp[1]))

    def draw_coordinates(self, dc):
        if not self.hover_point:
            return
        rel = self.get_relative_coords(self.hover_point)
        if not rel:
            return
        x_rel, y_rel = rel
        text = f"x: {x_rel:.3f}, y: {y_rel:.3f}"

        font = wx.Font(11, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        dc.SetFont(font)
        dc.SetTextForeground(wx.Colour(0, 0, 0))
        text_w, text_h = dc.GetTextExtent(text)

        left, top, right, bottom = self.get_grid_bounds()
        x_center = (left + right) // 2
        y_pos = bottom + 8

        padding = 8
        bg_x = x_center - text_w // 2 - padding
        bg_y = y_pos - 2
        bg_w = text_w + 2 * padding
        bg_h = text_h + 4

        dc.SetBrush(wx.Brush(wx.Colour(255, 255, 255, 220)))
        dc.SetPen(wx.Pen(wx.Colour(180, 180, 180), 1))
        dc.DrawRoundedRectangle(bg_x, bg_y, bg_w, bg_h, 4)
        dc.DrawText(text, x_center - text_w // 2, y_pos)


if __name__ == '__main__':
    app = wx.App(False)
    frame = GridCanvas(None, "Origami Grid Editor")
    app.MainLoop()