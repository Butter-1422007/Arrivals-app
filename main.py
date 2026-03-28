from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.slider import Slider
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, RoundedRectangle, Ellipse, Line
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.metrics import dp
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
import threading
import platform
import math

try:
    from plyer import gps
    GPS_AVAILABLE = True
except Exception:
    GPS_AVAILABLE = False


# ── Colour Palette ───────────────────────────────────────────
BG          = (0.04, 0.04, 0.09, 1)
CARD        = (0.09, 0.09, 0.16, 1)
CARD2       = (0.12, 0.12, 0.20, 1)
BLUE        = (0.18, 0.52, 0.98, 1)
TEAL        = (0.08, 0.82, 0.68, 1)
WARN        = (0.98, 0.74, 0.08, 1)
WHITE       = (0.96, 0.96, 1.00, 1)
GREY        = (0.42, 0.44, 0.56, 1)
GREEN       = (0.12, 0.88, 0.52, 1)
RED         = (0.98, 0.32, 0.38, 1)
DIVIDER     = (0.18, 0.18, 0.28, 1)


def dist_color(meters, buffer):
    """Return colour based on how close you are."""
    ratio = meters / max(buffer, 1)
    if ratio <= 1.0:
        return GREEN
    elif ratio <= 2.0:
        return WARN
    return TEAL


class RCard(BoxLayout):
    def __init__(self, radius=20, bg=CARD, **kw):
        super().__init__(**kw)
        with self.canvas.before:
            Color(*bg)
            self._r = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[radius])
        self.bind(pos=self._u, size=self._u)

    def _u(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size


class PillButton(Button):
    def __init__(self, bg=BLUE, **kw):
        super().__init__(**kw)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.color = WHITE
        self.bold = True
        self._bg = bg
        with self.canvas.before:
            self._ci = Color(*bg)
            self._r = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[14])
        self.bind(pos=self._u, size=self._u)

    def _u(self, *_):
        self._r.pos = self.pos
        self._r.size = self.size

    def set_bg(self, color):
        self._ci.rgba = color

    def on_press(self):
        Animation(opacity=0.75, duration=0.07).start(self)

    def on_release(self):
        Animation(opacity=1.0, duration=0.1).start(self)


class Divider(Widget):
    def __init__(self, **kw):
        super().__init__(size_hint=(1, None), height=dp(1), **kw)
        with self.canvas:
            Color(*DIVIDER)
            self._l = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._u, size=self._u)

    def _u(self, *_):
        self._l.pos = self.pos
        self._l.size = self.size


class RadialProgress(Widget):
    """Circular progress ring showing proximity to destination."""
    def __init__(self, **kw):
        super().__init__(size_hint=(None, None),
                         size=(dp(110), dp(110)), **kw)
        self._progress = 0.0
        self._color = TEAL
        self._dist_text = "--"
        self._unit_text = ""
        self._draw()
        self.bind(pos=self._redraw, size=self._redraw)

    def _draw(self):
        self.canvas.clear()
        cx = self.pos[0] + self.size[0] / 2
        cy = self.pos[1] + self.size[1] / 2
        r = min(self.size) / 2 - dp(8)

        with self.canvas:
            # Track ring
            Color(0.15, 0.15, 0.25, 1)
            Line(circle=(cx, cy, r), width=dp(5))

            # Progress arc
            Color(*self._color)
            angle = 360 * self._progress
            if angle > 0:
                Line(circle=(cx, cy, r, 90, 90 - angle),
                     width=dp(5), cap='round')

            # Center distance text
            Color(*WHITE)

        # Labels drawn via kivy Label trick using canvas.after
        self._cx = cx
        self._cy = cy

    def _redraw(self, *_):
        self._draw()

    def update(self, progress, color, dist_text, unit_text):
        self._progress = max(0.0, min(1.0, progress))
        self._color = color
        self._dist_text = dist_text
        self._unit_text = unit_text
        self._draw()


class ArrivalsApp(App):

    def build(self):
        self.title = "Arrivals"
        self.destination_coords = None
        self.alarm_active = False
        self.buffer_meters = 500
        self.current_coords = None
        self._last_distance = None

        # Root
        root = BoxLayout(orientation='vertical',
                         padding=0, spacing=0)
        with root.canvas.before:
            Color(*BG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._upd_bg, size=self._upd_bg)

        # Scrollable content
        scroll = BoxLayout(orientation='vertical',
                           padding=(dp(18), dp(14)),
                           spacing=dp(14))

        # ── HEADER ────────────────────────────────────────────
        hdr = BoxLayout(orientation='vertical',
                        size_hint=(1, None), height=dp(68),
                        spacing=dp(2))

        logo_row = BoxLayout(orientation='horizontal',
                             size_hint=(1, None), height=dp(46))

        logo = Label(
            text="ARRIVALS",
            font_size=dp(32),
            bold=True,
            color=WHITE,
            halign='left', valign='middle',
            size_hint=(0.6, 1)
        )
        logo.bind(size=logo.setter('text_size'))

        self._status_pill = RCard(
            radius=20, bg=CARD2,
            size_hint=(None, None),
            size=(dp(100), dp(30)),
            padding=(dp(10), 0),
            pos_hint={'center_y': 0.5}
        )
        self._status_dot = Label(
            text="● IDLE",
            font_size=dp(11),
            bold=True,
            color=GREY,
            halign='center', valign='middle'
        )
        self._status_dot.bind(
            size=self._status_dot.setter('text_size'))
        self._status_pill.add_widget(self._status_dot)

        logo_row.add_widget(logo)
        logo_row.add_widget(Widget())
        logo_row.add_widget(self._status_pill)

        tagline = Label(
            text="Sleep on the bus. Wake up at your stop.",
            font_size=dp(12),
            color=GREY,
            halign='left', valign='middle',
            size_hint=(1, None), height=dp(18)
        )
        tagline.bind(size=tagline.setter('text_size'))

        hdr.add_widget(logo_row)
        hdr.add_widget(tagline)
        scroll.add_widget(hdr)

        # ── GPS CARD ──────────────────────────────────────────
        gps_card = RCard(
            orientation='horizontal',
            size_hint=(1, None), height=dp(44),
            padding=(dp(14), 0), spacing=dp(10)
        )

        self._gps_dot = Label(
            text="◉",
            font_size=dp(16),
            color=WARN,
            size_hint=(None, 1), width=dp(22),
            halign='center', valign='middle'
        )
        self._gps_lbl = Label(
            text="Acquiring GPS signal...",
            font_size=dp(12),
            color=WARN,
            halign='left', valign='middle'
        )
        self._gps_lbl.bind(size=self._gps_lbl.setter('text_size'))

        self._gps_acc = Label(
            text="",
            font_size=dp(11),
            color=GREY,
            halign='right', valign='middle',
            size_hint=(None, 1), width=dp(70)
        )

        gps_card.add_widget(self._gps_dot)
        gps_card.add_widget(self._gps_lbl)
        gps_card.add_widget(self._gps_acc)
        scroll.add_widget(gps_card)

        # ── DISTANCE RING + INFO ──────────────────────────────
        ring_card = RCard(
            orientation='horizontal',
            size_hint=(1, None), height=dp(130),
            padding=(dp(16), dp(10)), spacing=dp(16)
        )

        # Radial ring
        ring_wrap = BoxLayout(
            size_hint=(None, 1), width=dp(110),
            orientation='vertical'
        )
        self._ring = RadialProgress()
        ring_wrap.add_widget(self._ring)

        # Distance text beside ring
        info_col = BoxLayout(orientation='vertical',
                             spacing=dp(4))

        self._dist_big = Label(
            text="--",
            font_size=dp(38),
            bold=True,
            color=WHITE,
            halign='left', valign='bottom',
            size_hint=(1, None), height=dp(48)
        )
        self._dist_big.bind(
            size=self._dist_big.setter('text_size'))

        self._dist_unit = Label(
            text="meters away",
            font_size=dp(12),
            color=GREY,
            halign='left', valign='top',
            size_hint=(1, None), height=dp(18)
        )
        self._dist_unit.bind(
            size=self._dist_unit.setter('text_size'))

        self._eta_lbl = Label(
            text="Set a destination to begin",
            font_size=dp(11),
            color=GREY,
            halign='left', valign='middle',
            size_hint=(1, None), height=dp(16)
        )
        self._eta_lbl.bind(size=self._eta_lbl.setter('text_size'))

        self._dest_name = Label(
            text="No destination",
            font_size=dp(12),
            color=TEAL,
            halign='left', valign='middle',
            size_hint=(1, None), height=dp(18)
        )
        self._dest_name.bind(
            size=self._dest_name.setter('text_size'))

        info_col.add_widget(self._dist_big)
        info_col.add_widget(self._dist_unit)
        info_col.add_widget(self._eta_lbl)
        info_col.add_widget(self._dest_name)

        ring_card.add_widget(ring_wrap)
        ring_card.add_widget(info_col)
        scroll.add_widget(ring_card)

        # ── DESTINATION CARD ──────────────────────────────────
        dest_card = RCard(
            orientation='vertical',
            size_hint=(1, None), height=dp(160),
            padding=dp(16), spacing=dp(10)
        )

        dest_top = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None), height=dp(18)
        )
        dest_top.add_widget(Label(
            text="DESTINATION",
            font_size=dp(10),
            bold=True,
            color=GREY,
            halign='left', valign='middle'
        ))
        self._coord_lbl = Label(
            text="",
            font_size=dp(10),
            color=GREY,
            halign='right', valign='middle'
        )
        dest_top.add_widget(self._coord_lbl)
        dest_card.add_widget(dest_top)

        self.dest_input = TextInput(
            hint_text="Search any place — e.g. Marina Beach, Chennai",
            multiline=False,
            font_size=dp(14),
            foreground_color=WHITE,
            hint_text_color=(*GREY[:3], 0.5),
            background_color=(0.14, 0.14, 0.24, 1),
            cursor_color=BLUE,
            padding=(dp(14), dp(11)),
            size_hint=(1, None), height=dp(48)
        )
        dest_card.add_widget(self.dest_input)

        self.search_btn = PillButton(
            text="Search Destination",
            bg=BLUE,
            font_size=dp(14),
            size_hint=(1, None), height=dp(46)
        )
        self.search_btn.bind(on_press=self.search_destination)
        dest_card.add_widget(self.search_btn)

        self._dest_status = Label(
            text="Type a place name and tap Search",
            font_size=dp(12),
            color=GREY,
            halign='left', valign='middle',
            size_hint=(1, None), height=dp(18)
        )
        self._dest_status.bind(
            size=self._dest_status.setter('text_size'))
        dest_card.add_widget(self._dest_status)
        scroll.add_widget(dest_card)

        # ── BUFFER CARD ───────────────────────────────────────
        buf_card = RCard(
            orientation='vertical',
            size_hint=(1, None), height=dp(96),
            padding=(dp(16), dp(12)), spacing=dp(8)
        )

        buf_top = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None), height=dp(20)
        )
        buf_top.add_widget(Label(
            text="WAKE-UP DISTANCE",
            font_size=dp(10),
            bold=True,
            color=GREY,
            halign='left', valign='middle'
        ))
        self._buf_val = Label(
            text="500 m",
            font_size=dp(14),
            bold=True,
            color=TEAL,
            halign='right', valign='middle'
        )
        buf_top.add_widget(self._buf_val)
        buf_card.add_widget(buf_top)

        self.buf_slider = Slider(
            min=200, max=2000, value=500, step=50,
            size_hint=(1, None), height=dp(44)
        )
        self.buf_slider.bind(value=self._on_slider)
        buf_card.add_widget(self.buf_slider)
        scroll.add_widget(buf_card)

        # ── ALARM BUTTON ──────────────────────────────────────
        self.alarm_btn = PillButton(
            text="START ALARM",
            bg=GREEN,
            font_size=dp(17),
            size_hint=(1, None), height=dp(60)
        )
        self.alarm_btn.bind(on_press=self.toggle_alarm)
        scroll.add_widget(self.alarm_btn)

        # ── WAKE UP BANNER ────────────────────────────────────
        self._banner = RCard(
            orientation='vertical',
            bg=(0.07, 0.25, 0.13, 1),
            size_hint=(1, None), height=dp(80),
            padding=(dp(16), dp(10)), spacing=dp(4),
            opacity=0
        )
        self._banner.add_widget(Label(
            text="WAKE UP!",
            font_size=dp(24),
            bold=True,
            color=GREEN,
            halign='center', valign='middle',
            size_hint=(1, None), height=dp(36)
        ))
        self._banner.add_widget(Label(
            text="You have almost reached your stop!",
            font_size=dp(13),
            color=WHITE,
            halign='center', valign='middle',
            size_hint=(1, None), height=dp(22)
        ))
        scroll.add_widget(self._banner)

        # Spacer
        scroll.add_widget(Widget(size_hint=(1, None), height=dp(20)))

        root.add_widget(scroll)
        return root

    # ── Background ───────────────────────────────────────────
    def _upd_bg(self, i, v):
        self._bg.pos = i.pos
        self._bg.size = i.size

    # ── GPS ──────────────────────────────────────────────────
    def on_start(self):
        if GPS_AVAILABLE and platform.system() != 'Windows':
            try:
                gps.configure(
                    on_location=self.on_gps_location,
                    on_status=self.on_gps_status)
                gps.start(minTime=2000, minDistance=5)
            except Exception as e:
                self._set_gps(f"GPS error: {e}", RED, "◉")
        else:
            # PC simulation — place near Chennai Central
            self.current_coords = (13.0827, 80.2707)
            self._set_gps(
                "Simulation mode (PC)", TEAL, "◎")
            self._gps_acc.text = "sim"

        self._pulse_gps()

    def _pulse_gps(self):
        anim = (Animation(opacity=0.4, duration=0.8) +
                Animation(opacity=1.0, duration=0.8))
        anim.repeat = True
        anim.start(self._gps_dot)

    def on_gps_location(self, **kw):
        lat = round(kw.get('lat', 0), 6)
        lon = round(kw.get('lon', 0), 6)
        acc = kw.get('accuracy', 0)
        self.current_coords = (lat, lon)
        Clock.schedule_once(lambda dt:
            self._update_gps_ui(lat, lon, acc))

    def _update_gps_ui(self, lat, lon, acc):
        self._set_gps(f"{lat:.5f}, {lon:.5f}", GREEN, "◉")
        self._gps_acc.text = f"±{acc:.0f}m" if acc else ""

    def on_gps_status(self, stype, status):
        Clock.schedule_once(lambda dt:
            self._set_gps(f"GPS: {status}", WARN, "◎"))

    def _set_gps(self, text, color, dot="◉"):
        self._gps_lbl.text = text
        self._gps_lbl.color = color
        self._gps_dot.text = dot
        self._gps_dot.color = color

    # ── Slider ───────────────────────────────────────────────
    def _on_slider(self, _, v):
        self.buffer_meters = int(v)
        if v >= 1000:
            self._buf_val.text = f"{v/1000:.1f} km"
        else:
            self._buf_val.text = f"{int(v)} m"

    # ── Search ───────────────────────────────────────────────
    def search_destination(self, *_):
        place = self.dest_input.text.strip()
        if not place:
            self._dest_status.text = "Please enter a place name first"
            self._dest_status.color = RED
            return
        self._dest_status.text = "Searching..."
        self._dest_status.color = GREY
        self.search_btn.text = "Searching..."
        threading.Thread(
            target=self._geocode, args=(place,), daemon=True).start()

    def _geocode(self, place):
        try:
            geo = Nominatim(user_agent="arrivals_app_v4")
            loc = geo.geocode(place, timeout=10)
            if loc:
                self.destination_coords = (
                    loc.latitude, loc.longitude)
                addr = loc.address
                short = (addr[:44] + "…") if len(addr) > 44 else addr
                Clock.schedule_once(
                    lambda dt: self._dest_ok(short,
                                             loc.latitude,
                                             loc.longitude))
            else:
                Clock.schedule_once(lambda dt: self._dest_fail())
        except Exception as e:
            Clock.schedule_once(lambda dt: self._dest_fail(str(e)))

    def _dest_ok(self, addr, lat, lon):
        self._dest_status.text = f"✓  {addr}"
        self._dest_status.color = GREEN
        self.search_btn.text = "Search Destination"
        self._dest_name.text = addr[:30] + "…" \
            if len(addr) > 30 else addr
        self._coord_lbl.text = f"{lat:.4f}, {lon:.4f}"
        # Update distance immediately
        if self.current_coords:
            d = geodesic(
                self.current_coords,
                self.destination_coords).meters
            self._refresh_distance_ui(d)

    def _dest_fail(self, err=""):
        self._dest_status.text = \
            "Not found — add ', India' at the end"
        self._dest_status.color = RED
        self.search_btn.text = "Search Destination"

    # ── Distance UI ──────────────────────────────────────────
    def _refresh_distance_ui(self, meters):
        self._last_distance = meters

        # Format distance smartly
        if meters >= 1000:
            dist_str = f"{meters/1000:.2f}"
            unit_str = "km away"
        else:
            dist_str = f"{meters:.0f}"
            unit_str = "meters away"

        self._dist_big.text = dist_str
        self._dist_unit.text = unit_str

        # Color based on proximity
        col = dist_color(meters, self.buffer_meters)
        self._dist_big.color = col

        # Ring progress — full circle when at buffer distance
        # Ring goes from 0 (far) to 1 (at destination)
        max_dist = 50000  # 50km baseline
        progress = 1.0 - min(meters / max_dist, 1.0)
        self._ring.update(
            progress, col, dist_str, unit_str)

        # ETA estimate (assuming 30km/h average bus speed)
        speed_mps = 30 * 1000 / 3600
        eta_sec = meters / speed_mps
        if eta_sec < 60:
            eta_str = f"~{eta_sec:.0f} sec away (est.)"
        elif eta_sec < 3600:
            eta_str = f"~{eta_sec/60:.0f} min away (est.)"
        else:
            eta_str = f"~{eta_sec/3600:.1f} hr away (est.)"
        self._eta_lbl.text = eta_str
        self._eta_lbl.color = col

    # ── Alarm ────────────────────────────────────────────────
    def toggle_alarm(self, *_):
        if not self.destination_coords:
            self._dest_status.text = "Set a destination first!"
            self._dest_status.color = RED
            return
        if not self.current_coords:
            self._set_status("NO GPS", WARN)
            return

        if not self.alarm_active:
            self.alarm_active = True
            self.alarm_btn.text = "STOP ALARM"
            self.alarm_btn.set_bg(RED)
            self._set_status("● ACTIVE", GREEN)
            Animation(opacity=0, duration=0.2).start(self._banner)
            # Check every 3 seconds for better precision
            Clock.schedule_interval(self.check_location, 3)
        else:
            self._stop_alarm()

    def _stop_alarm(self):
        self.alarm_active = False
        Clock.unschedule(self.check_location)
        self.alarm_btn.text = "START ALARM"
        self.alarm_btn.set_bg(GREEN)
        self._set_status("● IDLE", GREY)
        Animation(opacity=0, duration=0.3).start(self._banner)

    def _set_status(self, text, color):
        self._status_dot.text = text
        self._status_dot.color = color

    # ── Location check ───────────────────────────────────────
    def check_location(self, dt):
        if not (self.current_coords and self.destination_coords):
            return
        try:
            d = geodesic(
                self.current_coords,
                self.destination_coords).meters
            Clock.schedule_once(
                lambda dt: self._on_distance(d))
        except Exception:
            pass

    def _on_distance(self, d):
        self._refresh_distance_ui(d)
        if d <= self.buffer_meters:
            self._trigger_alarm()

    # ── Trigger ──────────────────────────────────────────────
    def _trigger_alarm(self):
        Clock.unschedule(self.check_location)
        self.alarm_active = False
        self.alarm_btn.text = "START ALARM"
        self.alarm_btn.set_bg(GREEN)
        self._set_status("● ARRIVED", GREEN)
        self._dist_big.text = "0"
        self._dist_unit.text = "Destination reached!"
        self._eta_lbl.text = "You are here!"

        # Flash banner
        self._banner.opacity = 0
        anim = (Animation(opacity=1.0, duration=0.25) +
                Animation(opacity=0.5, duration=0.25))
        anim.repeat = True
        anim.start(self._banner)

        if GPS_AVAILABLE:
            try:
                from plyer import notification
                notification.notify(
                    title="Arrivals — Wake Up!",
                    message="You have almost reached your stop!",
                    timeout=15
                )
            except Exception:
                pass

        # Also try vibration
        if GPS_AVAILABLE:
            try:
                from plyer import vibrator
                vibrator.vibrate(2)
            except Exception:
                pass


if __name__ == "__main__":
    ArrivalsApp().run()
