import os
import sys
import threading
import platform

os.environ['KIVY_NO_CONSOLELOG'] = '1'

try:
    from kivy.app import App
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.uix.textinput import TextInput
    from kivy.uix.slider import Slider
    from kivy.uix.widget import Widget
    from kivy.graphics import Color, Rectangle, RoundedRectangle
    from kivy.clock import Clock
    from kivy.animation import Animation
    from kivy.metrics import dp
    from kivy.utils import platform as kivy_platform
except Exception as e:
    sys.exit(1)

try:
    from geopy.distance import geodesic
    from geopy.geocoders import Nominatim
    GEOPY_AVAILABLE = True
except Exception:
    GEOPY_AVAILABLE = False

try:
    from plyer import gps
    GPS_AVAILABLE = True
except Exception:
    GPS_AVAILABLE = False

# ── Colours ──────────────────────────────────────────────────
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


class ArrivalsApp(App):

    def build(self):
        self.title = "Arrivals"
        self.destination_coords = None
        self.alarm_active = False
        self.buffer_meters = 500
        self.current_coords = None

        # Root
        root = BoxLayout(
            orientation='vertical',
            padding=dp(18),
            spacing=dp(14)
        )
        with root.canvas.before:
            Color(*BG)
            self._bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._upd_bg, size=self._upd_bg)

        # ── HEADER ────────────────────────────────────────────
        hdr = BoxLayout(
            orientation='vertical',
            size_hint=(1, None), height=dp(70),
            spacing=dp(4)
        )

        title = Label(
            text="ARRIVALS",
            font_size=dp(34),
            bold=True,
            color=WHITE,
            size_hint=(1, None), height=dp(46),
            halign='center', valign='middle'
        )
        title.bind(size=title.setter('text_size'))

        tagline = Label(
            text="Sleep on the bus. Wake up at your stop.",
            font_size=dp(13),
            color=GREY,
            size_hint=(1, None), height=dp(20),
            halign='center', valign='middle'
        )
        tagline.bind(size=tagline.setter('text_size'))

        hdr.add_widget(title)
        hdr.add_widget(tagline)
        root.add_widget(hdr)

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

        gps_card.add_widget(self._gps_dot)
        gps_card.add_widget(self._gps_lbl)
        root.add_widget(gps_card)

        # ── DISTANCE CARD ─────────────────────────────────────
        dist_card = RCard(
            orientation='horizontal',
            size_hint=(1, None), height=dp(100),
            padding=(dp(16), dp(10)), spacing=dp(10)
        )

        dist_col = BoxLayout(
            orientation='vertical',
            size_hint=(0.65, 1),
            spacing=dp(2)
        )

        dist_col.add_widget(Label(
            text="DISTANCE TO STOP",
            font_size=dp(10),
            bold=True,
            color=GREY,
            halign='left', valign='middle',
            size_hint=(1, None), height=dp(18)
        ))

        self._dist_val = Label(
            text="-- m",
            font_size=dp(32),
            bold=True,
            color=WHITE,
            halign='left', valign='middle',
            size_hint=(1, None), height=dp(42)
        )
        self._dist_val.bind(size=self._dist_val.setter('text_size'))
        dist_col.add_widget(self._dist_val)

        self._eta_lbl = Label(
            text="Set destination to begin",
            font_size=dp(11),
            color=GREY,
            halign='left', valign='middle',
            size_hint=(1, None), height=dp(16)
        )
        self._eta_lbl.bind(size=self._eta_lbl.setter('text_size'))
        dist_col.add_widget(self._eta_lbl)

        status_col = BoxLayout(
            orientation='vertical',
            size_hint=(0.35, 1)
        )

        self._status_lbl = Label(
            text="IDLE",
            font_size=dp(13),
            bold=True,
            color=GREY,
            halign='right', valign='middle'
        )
        self._status_lbl.bind(
            size=self._status_lbl.setter('text_size'))
        status_col.add_widget(self._status_lbl)

        dist_card.add_widget(dist_col)
        dist_card.add_widget(status_col)
        root.add_widget(dist_card)

        # ── DESTINATION CARD ──────────────────────────────────
        dest_card = RCard(
            orientation='vertical',
            size_hint=(1, None), height=dp(165),
            padding=dp(14), spacing=dp(10)
        )

        dest_card.add_widget(Label(
            text="DESTINATION",
            font_size=dp(10),
            bold=True,
            color=GREY,
            size_hint=(1, None), height=dp(16),
            halign='left', valign='middle'
        ))

        self.dest_input = TextInput(
            hint_text="e.g. Egmore Station, Tamil Nadu, India",
            multiline=False,
            font_size=dp(14),
            foreground_color=WHITE,
            hint_text_color=(*GREY[:3], 0.5),
            background_color=(0.14, 0.14, 0.24, 1),
            cursor_color=BLUE,
            padding=(dp(12), dp(10)),
            size_hint=(1, None), height=dp(46)
        )
        dest_card.add_widget(self.dest_input)

        self.search_btn = PillButton(
            text="Search Destination",
            bg=BLUE,
            font_size=dp(14),
            size_hint=(1, None), height=dp(44)
        )
        self.search_btn.bind(on_press=self.search_destination)
        dest_card.add_widget(self.search_btn)

        self._dest_status = Label(
            text="Type a place and tap Search",
            font_size=dp(12),
            color=GREY,
            size_hint=(1, None), height=dp(18),
            halign='left', valign='middle'
        )
        self._dest_status.bind(
            size=self._dest_status.setter('text_size'))
        dest_card.add_widget(self._dest_status)
        root.add_widget(dest_card)

        # ── BUFFER CARD ───────────────────────────────────────
        buf_card = RCard(
            orientation='vertical',
            size_hint=(1, None), height=dp(90),
            padding=(dp(14), dp(10)), spacing=dp(6)
        )

        buf_row = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None), height=dp(22)
        )

        buf_row.add_widget(Label(
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
        buf_row.add_widget(self._buf_val)
        buf_card.add_widget(buf_row)

        self.buf_slider = Slider(
            min=200, max=2000, value=500, step=50,
            size_hint=(1, None), height=dp(44)
        )
        self.buf_slider.bind(value=self._on_slider)
        buf_card.add_widget(self.buf_slider)
        root.add_widget(buf_card)

        # ── ALARM BUTTON ──────────────────────────────────────
        self.alarm_btn = PillButton(
            text="START ALARM",
            bg=GREEN,
            font_size=dp(18),
            size_hint=(1, None), height=dp(62)
        )
        self.alarm_btn.bind(on_press=self.toggle_alarm)
        root.add_widget(self.alarm_btn)

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
            font_size=dp(26),
            bold=True,
            color=GREEN,
            halign='center', valign='middle',
            size_hint=(1, None), height=dp(38)
        ))
        self._banner.add_widget(Label(
            text="You have almost reached your stop!",
            font_size=dp(13),
            color=WHITE,
            halign='center', valign='middle',
            size_hint=(1, None), height=dp(22)
        ))
        root.add_widget(self._banner)

        root.add_widget(Widget())
        return root

    def _upd_bg(self, i, v):
        self._bg.pos = i.pos
        self._bg.size = i.size

    def on_start(self):
        try:
            self._start_gps()
        except Exception:
            self.current_coords = (13.0827, 80.2707)
            self._set_gps("GPS: Ready (fallback)", TEAL)

    def _start_gps(self):
        if GPS_AVAILABLE and kivy_platform == 'android':
            try:
                gps.configure(
                    on_location=self.on_gps_location,
                    on_status=self.on_gps_status
                )
                gps.start(minTime=2000, minDistance=5)
                self._pulse_gps()
            except Exception as e:
                self._set_gps(f"GPS error: {e}", RED)
        else:
            self.current_coords = (13.0827, 80.2707)
            self._set_gps("GPS: Simulation mode", TEAL)
            self._pulse_gps()

    def _pulse_gps(self):
        anim = (Animation(opacity=0.3, duration=0.8) +
                Animation(opacity=1.0, duration=0.8))
        anim.repeat = True
        anim.start(self._gps_dot)

    def on_gps_location(self, **kw):
        lat = round(kw.get('lat', 0), 6)
        lon = round(kw.get('lon', 0), 6)
        acc = kw.get('accuracy', 0)
        self.current_coords = (lat, lon)
        Clock.schedule_once(
            lambda dt: self._update_gps_ui(lat, lon, acc))

    def _update_gps_ui(self, lat, lon, acc):
        acc_str = f" ±{acc:.0f}m" if acc else ""
        self._set_gps(
            f"{lat:.5f}, {lon:.5f}{acc_str}", GREEN)

    def on_gps_status(self, stype, status):
        Clock.schedule_once(
            lambda dt: self._set_gps(f"GPS: {status}", WARN))

    def _set_gps(self, text, color):
        self._gps_lbl.text = text
        self._gps_lbl.color = color
        self._gps_dot.color = color

    def _on_slider(self, _, v):
        self.buffer_meters = int(v)
        if v >= 1000:
            self._buf_val.text = f"{v/1000:.1f} km"
        else:
            self._buf_val.text = f"{int(v)} m"

    def search_destination(self, *_):
        if not GEOPY_AVAILABLE:
            self._dest_status.text = "Search unavailable"
            self._dest_status.color = RED
            return
        place = self.dest_input.text.strip()
        if not place:
            self._dest_status.text = "Please enter a place name"
            self._dest_status.color = RED
            return
        self._dest_status.text = "Searching..."
        self._dest_status.color = GREY
        self.search_btn.text = "Searching..."
        threading.Thread(
            target=self._geocode,
            args=(place,), daemon=True).start()

    def _geocode(self, place):
        try:
            geo = Nominatim(user_agent="arrivals_v5")
            loc = geo.geocode(place, timeout=10)
            if loc:
                self.destination_coords = (
                    loc.latitude, loc.longitude)
                addr = loc.address
                short = (addr[:44] + "…") \
                    if len(addr) > 44 else addr
                Clock.schedule_once(
                    lambda dt: self._dest_ok(short))
            else:
                Clock.schedule_once(
                    lambda dt: self._dest_fail())
        except Exception:
            Clock.schedule_once(
                lambda dt: self._dest_fail())

    def _dest_ok(self, addr):
        self._dest_status.text = f"✓  {addr}"
        self._dest_status.color = GREEN
        self.search_btn.text = "Search Destination"
        if self.current_coords:
            try:
                d = geodesic(
                    self.current_coords,
                    self.destination_coords).meters
                self._refresh_dist(d)
            except Exception:
                pass

    def _dest_fail(self):
        self._dest_status.text = \
            "Not found — add ', India' at end"
        self._dest_status.color = RED
        self.search_btn.text = "Search Destination"

    def _refresh_dist(self, meters):
        if meters >= 1000:
            self._dist_val.text = f"{meters/1000:.2f} km"
        else:
            self._dist_val.text = f"{meters:.0f} m"

        if meters <= self.buffer_meters:
            self._dist_val.color = GREEN
        elif meters <= self.buffer_meters * 2:
            self._dist_val.color = WARN
        else:
            self._dist_val.color = WHITE

        speed = 30 * 1000 / 3600
        secs = meters / speed
        if secs < 60:
            self._eta_lbl.text = f"~{secs:.0f} sec away"
        elif secs < 3600:
            self._eta_lbl.text = f"~{secs/60:.0f} min away"
        else:
            self._eta_lbl.text = f"~{secs/3600:.1f} hr away"

    def toggle_alarm(self, *_):
        if not self.destination_coords:
            self._dest_status.text = "Set a destination first!"
            self._dest_status.color = RED
            return
        if not self.current_coords:
            self._status_lbl.text = "NO GPS"
            self._status_lbl.color = WARN
            return

        if not self.alarm_active:
            self.alarm_active = True
            self.alarm_btn.text = "STOP ALARM"
            self.alarm_btn.set_bg(RED)
            self._status_lbl.text = "ACTIVE"
            self._status_lbl.color = GREEN
            Animation(opacity=0, duration=0.2).start(
                self._banner)
            Clock.schedule_interval(self.check_location, 3)
        else:
            self._stop_alarm()

    def _stop_alarm(self):
        self.alarm_active = False
        Clock.unschedule(self.check_location)
        self.alarm_btn.text = "START ALARM"
        self.alarm_btn.set_bg(GREEN)
        self._status_lbl.text = "IDLE"
        self._status_lbl.color = GREY
        self._dist_val.text = "-- m"
        Animation(opacity=0, duration=0.3).start(self._banner)

    def check_location(self, dt):
        if not (self.current_coords and
                self.destination_coords):
            return
        try:
            d = geodesic(
                self.current_coords,
                self.destination_coords).meters
            Clock.schedule_once(
                lambda dt: self._on_dist(d))
        except Exception:
            pass

    def _on_dist(self, d):
        self._refresh_dist(d)
        if d <= self.buffer_meters:
            self._trigger_alarm()

    def _trigger_alarm(self):
        Clock.unschedule(self.check_location)
        self.alarm_active = False
        self.alarm_btn.text = "START ALARM"
        self.alarm_btn.set_bg(GREEN)
        self._status_lbl.text = "ARRIVED!"
        self._status_lbl.color = GREEN
        self._dist_val.text = "0 m"
        self._eta_lbl.text = "You are here!"

        self._banner.opacity = 0
        anim = (Animation(opacity=1.0, duration=0.25) +
                Animation(opacity=0.5, duration=0.25))
        anim.repeat = True
        anim.start(self._banner)

        try:
            from plyer import notification
            notification.notify(
                title="Arrivals",
                message="Wake up! Almost at your stop!",
                timeout=15
            )
        except Exception:
            pass

        try:
            from plyer import vibrator
            vibrator.vibrate(3)
        except Exception:
            pass


if __name__ == "__main__":
    ArrivalsApp().run()
