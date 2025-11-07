import wx

def line_intersection(line1, line2):
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
        ix = x1 + t * (x2 - x1)
        iy = y1 + t * (y2 - y1)
        return (ix, iy)
    return None


class GridCanvas(wx.Frame):
    def __init__(self, parent, title):
        super(GridCanvas, self).__init__(parent, title=title, size=(800, 600))

        # --- Основные данные ---
        self.div_num = 4
        self.grid_size = 0
        self.canvas_size = 500
        self.margin = 50

        self.endpoint_points = []
        self.intersection_points = set()
        self.hover_point = None
        self.selected_point = None
        self.lines = []

        # --- Интерфейс ---
        self.panel = wx.Panel(self)
        self.canvas = wx.Panel(self.panel, style=wx.FULL_REPAINT_ON_RESIZE)
        self.canvas.SetBackgroundColour(wx.WHITE)

        # Левая панель
        self.control_panel = wx.Panel(self.panel)
        self.control_panel.SetBackgroundColour(wx.Colour(240, 240, 240))

        self.div_label = wx.StaticText(self.control_panel, label="Div Num")
        self.div_text = wx.TextCtrl(self.control_panel, value="4", size=(50, -1))
        self.set_button = wx.Button(self.control_panel, label="Set")
        self.set_button.Bind(wx.EVT_BUTTON, self.on_set_div)

        ctrl_sizer = wx.BoxSizer(wx.VERTICAL)
        ctrl_sizer.Add(self.div_label, 0, wx.ALL | wx.ALIGN_CENTER, 5)
        ctrl_sizer.Add(self.div_text, 0, wx.ALL | wx.EXPAND, 5)
        ctrl_sizer.Add(self.set_button, 0, wx.ALL | wx.EXPAND, 5)
        ctrl_sizer.AddStretchSpacer()
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

        self.update_grid_size()
        self.Show()

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

    def get_grid_points(self):
        left, top, right, bottom = self.get_grid_bounds()
        points = []
        x = left
        while x <= right:
            y = top
            while y <= bottom:
                points.append((x, y))
                y += self.grid_size
            x += self.grid_size
        return points

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
        self.intersection_points = set()
        for i in range(len(self.lines)):
            for j in range(i + 1, len(self.lines)):
                inter = line_intersection(self.lines[i], self.lines[j])
                if inter:
                    left, top, right, bottom = self.get_grid_bounds()
                    if left <= inter[0] <= right and top <= inter[1] <= bottom:
                        self.intersection_points.add(inter)

    def on_paint(self, event):
        dc = wx.PaintDC(self.canvas)
        self.draw_grid_area(dc)
        self.draw_grid_lines(dc)
        self.draw_red_points(dc)
        self.draw_hover_point(dc)
        self.draw_lines(dc)
        self.draw_preview_line(dc)

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

    def draw_lines(self, dc):
        dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 2))
        for line in self.lines:
            dc.DrawLine(int(line[0][0]), int(line[0][1]),
                        int(line[1][0]), int(line[1][1]))

    def draw_preview_line(self, dc):
        if self.selected_point and self.hover_point:
            dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 2, wx.PENSTYLE_DOT))
            sp = self.selected_point
            hp = self.hover_point
            dc.DrawLine(int(sp[0]), int(sp[1]), int(hp[0]), int(hp[1]))

    def on_mouse_move(self, event):
        pos = event.GetPosition()
        self.hover_point = self.get_nearest_point(pos)
        self.canvas.Refresh()

    def on_left_click(self, event):
        pos = event.GetPosition()
        point = self.get_nearest_point(pos)
        if point is None:
            return

        left, top, right, bottom = self.get_grid_bounds()
        if not (left <= point[0] <= right and top <= point[1] <= bottom):
            return

        # === НОВАЯ ЛОГИКА: отмена выбора ===
        if self.selected_point is not None and point == self.selected_point:
            # Клик по уже выбранной точке → отменяем выбор
            self.selected_point = None
            self.canvas.Refresh()
            return

        if self.selected_point is None:
            # Выбираем первую точку
            self.selected_point = point
            # НЕ добавляем в endpoint_points сразу — только при создании линии
        else:
            # Завершаем линию
            p1 = self.selected_point
            p2 = point

            # Добавляем обе точки как конечные (если ещё не добавлены)
            for p in [p1, p2]:
                if p not in self.endpoint_points and p not in self.intersection_points:
                    self.endpoint_points.append(p)

            self.lines.append((p1, p2))
            self.selected_point = None
            self.update_intersections()

        self.canvas.Refresh()


if __name__ == '__main__':
    app = wx.App(False)
    frame = GridCanvas(None, "Origami Grid Editor")
    app.MainLoop()