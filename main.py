import wx

class GridCanvas(wx.Frame):
    def __init__(self, parent, title):
        super(GridCanvas, self).__init__(parent, title=title, size=(400, 400))

        self.panel = wx.Panel(self)
        self.canvas = wx.Panel(self.panel, style=wx.FULL_REPAINT_ON_RESIZE)

        self.grid_size = 50
        self.points = []
        self.hover_point = None
        self.selected_point = None
        self.lines = []

        self.canvas.Bind(wx.EVT_PAINT, self.on_paint)
        self.canvas.Bind(wx.EVT_MOTION, self.on_mouse_move)
        self.canvas.Bind(wx.EVT_LEFT_DOWN, self.on_left_click)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.canvas, 1, wx.EXPAND)
        self.panel.SetSizer(sizer)

        self.Show()

    def on_paint(self, event):
        dc = wx.PaintDC(self.canvas)
        self.draw_grid(dc)
        self.draw_points(dc)
        self.draw_lines(dc)
        if self.selected_point and self.hover_point:
            dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 2))
            dc.DrawLine(self.selected_point[0], self.selected_point[1], self.hover_point[0], self.hover_point[1])

    def draw_grid(self, dc):
        width, height = self.canvas.GetSize()
        dc.SetPen(wx.Pen(wx.Colour(200, 200, 200), 1))
        for x in range(0, width, self.grid_size):
            dc.DrawLine(x, 0, x, height)
        for y in range(0, height, self.grid_size):
            dc.DrawLine(0, y, width, y)

    def draw_points(self, dc):
        width, height = self.canvas.GetSize()
        for x in range(0, width, self.grid_size):
            for y in range(0, height, self.grid_size):
                if (x, y) == self.hover_point:
                    dc.SetBrush(wx.Brush(wx.Colour(0, 255, 0)))
                    dc.SetPen(wx.Pen(wx.Colour(0, 255, 0), 2))
                    dc.DrawCircle(x, y, 3)
                elif (x, y) in self.points:
                    dc.SetBrush(wx.Brush(wx.Colour(255, 0, 0)))
                    dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 2))
                    dc.DrawCircle(x, y, 3)

    def draw_lines(self, dc):
        dc.SetPen(wx.Pen(wx.Colour(255, 0, 0), 2))
        for line in self.lines:
            dc.DrawLine(line[0][0], line[0][1], line[1][0], line[1][1])

    def on_mouse_move(self, event):
        x, y = event.GetPosition()
        x = round(x / self.grid_size) * self.grid_size
        y = round(y / self.grid_size) * self.grid_size
        self.hover_point = (x, y)
        self.canvas.Refresh()

    def on_left_click(self, event):
        x, y = event.GetPosition()
        x = round(x / self.grid_size) * self.grid_size
        y = round(y / self.grid_size) * self.grid_size
        point = (x, y)

        if self.selected_point is None:
            self.selected_point = point
            if point not in self.points:
                self.points.append(point)
        else:
            self.lines.append((self.selected_point, point))
            self.selected_point = None
        self.canvas.Refresh()


if __name__ == '__main__':
    app = wx.App(False)
    frame = GridCanvas(None, "Grid Canvas")
    app.MainLoop()
