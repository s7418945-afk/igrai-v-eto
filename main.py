import math
import random
import time
import tkinter as tk


WIDTH, HEIGHT = 960, 600
WORLD_LIMIT = 68
KEY_ALIASES = {
    "ц": "w", "ф": "a", "ы": "s", "в": "d",
    "у": "e", "к": "r", "м": "v",
    "cyrillic_tse": "w", "cyrillic_ef": "a",
    "cyrillic_yeru": "s", "cyrillic_ve": "d",
    "cyrillic_u": "e", "cyrillic_ka": "r",
    "cyrillic_softsign": "v",
}


def clamp(value, low, high):
    return max(low, min(high, value))


class CityGame:
    def __init__(self, root):
        self.root = root
        root.title("NEON DISTRICT")
        root.geometry(f"{WIDTH}x{HEIGHT}")
        root.minsize(720, 450)
        root.configure(bg="#18242b")

        self.canvas = tk.Canvas(root, bg="#547650", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        root.after_idle(self.canvas.focus_set)

        self.keys = set()
        self.player = {"x": -2.0, "z": -1.0, "yaw": 0.0}
        self.walk_phase = 0.0
        self.walking = False
        self.car = {"x": 1.0, "z": 2.0, "yaw": 0.0, "speed": 0.0}
        self.driving = False
        self.shop = None
        self.cash = 300
        self.health = 100
        self.ammo = 12
        self.reserve = 36
        self.weapon_level = 1
        self.targets = []
        self.buildings = []
        self.shops = []
        self.notice = ""
        self.notice_until = 0.0
        self.shot_until = 0.0
        self.shot_start = None
        self.shot_end = None
        self.aim = (self.player["x"], self.player["z"] + 10)
        self.camera = (self.player["x"], self.player["z"])
        self.scale = 1.0
        self.last_time = time.perf_counter()
        self.make_city()

        root.bind_all("<KeyPress>", self.key_down)
        root.bind_all("<KeyRelease>", self.key_up)
        root.bind_all("<FocusOut>", self.clear_keys)
        self.canvas.bind("<Motion>", self.mouse_move)
        self.canvas.bind("<Button-1>", self.on_mouse_click)
        self.canvas.bind("<Configure>", self.on_resize)
        self.loop()

    def on_resize(self, event):
        if event.width >= 100 and event.height >= 100:
            self.draw()

    def make_city(self):
        palette = ("#87999b", "#aa947d", "#738b98", "#9d8798", "#849181")
        for block_x in range(-36, 37, 24):
            for block_z in range(-36, 37, 24):
                for offset_x in (-5, 5):
                    for offset_z in (-5, 5):
                        x, z = block_x + offset_x, block_z + offset_z
                        if abs(x) < 17 and abs(z) < 21:
                            continue
                        self.buildings.append({
                            "x": x, "z": z, "w": 8, "d": 8,
                            "color": random.choice(palette),
                        })

        self.add_shop(-8, 11, "ОРУЖЕЙНЫЙ", "weapons", "#d45b62")
        self.add_shop(8, 11, "АВТОСЕРВИС", "garage", "#40a88d")
        for x, z in ((0, 28), (-13, 34), (14, 43), (30, -23), (-35, 18)):
            self.targets.append({
                "x": x, "z": z, "active": True, "respawn_at": 0,
            })

    def add_shop(self, x, z, title, kind, tint):
        shop = {
            "x": x, "z": z, "title": title, "kind": kind, "color": tint,
            "w": 5, "d": 4,
        }
        self.shops.append(shop)
        self.buildings.append({
            "x": x, "z": z, "w": 5, "d": 4,
            "color": "#555e6d", "shop": shop,
        })

    def key_down(self, event):
        self.canvas.focus_set()
        key = self.normalize_key(event)
        if key not in self.keys:
            if key == "e":
                self.interact()
            elif key == "r":
                self.reload()
            elif key == "space":
                self.shoot()
            elif key == "escape":
                if self.shop:
                    self.shop = None
                elif self.driving:
                    self.interact()
            elif key in ("1", "2") and self.shop:
                self.buy(key)
        self.keys.add(key)

    def key_up(self, event):
        char = event.char.lower()
        keysym = event.keysym.lower()
        self.keys.discard(KEY_ALIASES.get(char, char))
        self.keys.discard(KEY_ALIASES.get(keysym, keysym))

    def clear_keys(self, _event=None):
        if _event is None or _event.widget in (self.canvas, self.root):
            self.keys.clear()

    @staticmethod
    def normalize_key(event):
        char = event.char.lower()
        keysym = event.keysym.lower()
        return KEY_ALIASES.get(char, KEY_ALIASES.get(keysym, keysym))

    def on_mouse_click(self, event):
        self.canvas.focus_set()
        self.update_aim(event.x, event.y)
        self.shoot()

    def mouse_move(self, event):
        self.update_aim(event.x, event.y)

    def update_aim(self, screen_x, screen_y):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        camera_x, camera_z = self.camera
        self.aim = (
            camera_x + (screen_x - width / 2) / self.scale,
            camera_z + (screen_y - height / 2) / self.scale,
        )

    def actor(self):
        return self.car if self.driving else self.player

    def distance_to(self, x, z):
        actor = self.actor()
        return math.hypot(actor["x"] - x, actor["z"] - z)

    def interact(self):
        if self.shop:
            self.shop = None
            return
        if self.driving:
            self.driving = False
            self.player["x"] = self.car["x"] - math.sin(self.car["yaw"]) * 2
            self.player["z"] = self.car["z"] - math.cos(self.car["yaw"]) * 2
            return
        for shop in self.shops:
            if self.distance_to(shop["x"], shop["z"]) < 8:
                self.shop = shop
                return
        if self.distance_to(self.car["x"], self.car["z"]) < 5:
            self.driving = True
            self.car["speed"] = 0

    def buy(self, key):
        if self.shop["kind"] == "weapons" and key == "1":
            if self.cash >= 25:
                self.cash -= 25
                self.reserve += 12
                self.notify("Куплено 12 зарядов")
            else:
                self.notify("Не хватает денег")
        elif self.shop["kind"] == "weapons" and key == "2":
            if self.weapon_level >= 3:
                self.notify("Улучшение максимальное")
            elif self.cash >= 75:
                self.cash -= 75
                self.weapon_level += 1
                self.notify("Бластер улучшен")
            else:
                self.notify("Не хватает денег")
        elif self.shop["kind"] == "garage" and key == "1":
            self.car["speed"] = 0
            self.health = 100
            self.notify("Машина обслужена")

    def reload(self):
        count = min(12 - self.ammo, self.reserve)
        if count > 0:
            self.ammo += count
            self.reserve -= count
            self.notify("Бластер перезаряжен")
        else:
            self.notify("Нет зарядов — купи их в магазине")

    def shoot(self):
        if self.shop:
            return
        if self.ammo <= 0:
            self.notify("Нет зарядов — нажми R")
            return

        actor = self.actor()
        dx, dz = self.aim[0] - actor["x"], self.aim[1] - actor["z"]
        length = math.hypot(dx, dz)
        if length < 0.01:
            return
        dx, dz = dx / length, dz / length
        actor["yaw"] = math.atan2(dx, dz)
        self.ammo -= 1
        self.shot_start = (actor["x"], actor["z"])
        self.shot_end = (actor["x"] + dx * 35, actor["z"] + dz * 35)
        self.shot_until = time.perf_counter() + 0.12

        for target in self.targets:
            if not target["active"]:
                continue
            to_x, to_z = target["x"] - actor["x"], target["z"] - actor["z"]
            along = to_x * dx + to_z * dz
            side = abs(to_x * dz - to_z * dx)
            if 0 < along < 35 and side < 0.8 + self.weapon_level * 0.15:
                target["active"] = False
                target["respawn_at"] = time.perf_counter() + 3
                self.shot_end = (target["x"], target["z"])
                self.cash += 20
                self.notify("Мишень! +$20")
                break

    def notify(self, text):
        self.notice = text
        self.notice_until = time.perf_counter() + 2

    def blocked(self, x, z, radius):
        if abs(x) > WORLD_LIMIT or abs(z) > WORLD_LIMIT:
            return True
        for building in self.buildings:
            half_w, half_d = building["w"] / 2, building["d"] / 2
            nearest_x = clamp(x, building["x"] - half_w, building["x"] + half_w)
            nearest_z = clamp(z, building["z"] - half_d, building["z"] + half_d)
            if math.hypot(x - nearest_x, z - nearest_z) < radius:
                return True
        return False

    def update(self, dt):
        if self.shop:
            return
        now = time.perf_counter()
        for target in self.targets:
            if not target["active"] and now >= target["respawn_at"]:
                target["active"] = True

        actor = self.actor()
        self.walking = False
        if self.driving:
            throttle = int("w" in self.keys or "up" in self.keys) - int(
                "s" in self.keys or "down" in self.keys
            )
            steer = int("d" in self.keys or "right" in self.keys) - int(
                "a" in self.keys or "left" in self.keys
            )
            self.car["speed"] = clamp(self.car["speed"] + throttle * 16 * dt, -8, 22)
            self.car["speed"] *= max(0, 1 - 0.6 * dt)
            if abs(self.car["speed"]) > 0.1:
                self.car["yaw"] += (
                    steer * dt * 1.5 * (1 if self.car["speed"] > 0 else -1)
                )
                x = self.car["x"] + math.sin(self.car["yaw"]) * self.car["speed"] * dt
                z = self.car["z"] + math.cos(self.car["yaw"]) * self.car["speed"] * dt
                if not self.blocked(x, z, 1.3):
                    self.car["x"], self.car["z"] = x, z
                else:
                    self.car["speed"] = 0
        else:
            forward = int("w" in self.keys or "up" in self.keys) - int(
                "s" in self.keys or "down" in self.keys
            )
            sideways = int("d" in self.keys or "right" in self.keys) - int(
                "a" in self.keys or "left" in self.keys
            )
            magnitude = math.hypot(forward, sideways)
            speed = 8 if "shift" in self.keys else 5
            if magnitude:
                dx = sideways / magnitude * speed * dt
                dz = forward / magnitude * speed * dt
                old_x, old_z = actor["x"], actor["z"]
                if not self.blocked(actor["x"] + dx, actor["z"], 0.35):
                    actor["x"] += dx
                if not self.blocked(actor["x"], actor["z"] + dz, 0.35):
                    actor["z"] += dz
                moved_x = actor["x"] - old_x
                moved_z = actor["z"] - old_z
                self.walking = bool(moved_x or moved_z)
                if self.walking:
                    actor["yaw"] = math.atan2(moved_x, moved_z)
                    self.walk_phase += dt * 12

    def to_screen(self, x, z):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        return (
            width / 2 + (x - self.camera[0]) * self.scale,
            height / 2 + (z - self.camera[1]) * self.scale,
        )

    def draw(self):
        canvas = self.canvas
        canvas.delete("all")
        width, height = canvas.winfo_width(), canvas.winfo_height()
        if width < 100 or height < 100:
            return

        actor = self.actor()
        self.camera = (actor["x"], actor["z"])
        self.scale = min(width / 94, height / 62)
        scale = self.scale
        canvas.create_rectangle(0, 0, width, height, fill="#547650", outline="")

        view_left = self.camera[0] - width / (2 * scale) - 24
        view_right = self.camera[0] + width / (2 * scale) + 24
        view_top = self.camera[1] - height / (2 * scale) - 24
        view_bottom = self.camera[1] + height / (2 * scale) + 24
        for road in range(-48, 49, 24):
            x1, y1 = self.to_screen(road, view_top)
            x2, y2 = self.to_screen(road, view_bottom)
            canvas.create_rectangle(
                x1 - 3.5 * scale, y1, x2 + 3.5 * scale, y2,
                fill="#3b424c", outline="",
            )
            x1, y1 = self.to_screen(view_left, road)
            x2, y2 = self.to_screen(view_right, road)
            canvas.create_rectangle(
                x1, y1 - 3.5 * scale, x2, y2 + 3.5 * scale,
                fill="#3b424c", outline="",
            )
            for mark in range(-72, 73, 10):
                px, py = self.to_screen(road, mark)
                if -20 < px < width + 20 and -20 < py < height + 20:
                    canvas.create_rectangle(
                        px - 1, py - scale, px + 1, py + scale,
                        fill="#d9c982", outline="",
                    )
                px, py = self.to_screen(mark, road)
                if -20 < px < width + 20 and -20 < py < height + 20:
                    canvas.create_rectangle(
                        px - scale, py - 1, px + scale, py + 1,
                        fill="#d9c982", outline="",
                    )

        for building in self.buildings:
            x, y = self.to_screen(building["x"], building["z"])
            half_w = building["w"] * scale / 2
            half_d = building["d"] * scale / 2
            x1, y1, x2, y2 = x - half_w, y - half_d, x + half_w, y + half_d
            if x2 < 0 or x1 > width or y2 < 0 or y1 > height:
                continue
            canvas.create_rectangle(
                x1 + 3, y1 + 5, x2 + 3, y2 + 5, fill="#26353a", outline="",
            )
            canvas.create_rectangle(
                x1, y1, x2, y2, fill=building["color"],
                outline="#34444a", width=2,
            )
            shop = building.get("shop")
            if shop:
                canvas.create_rectangle(
                    x1 + 4, y1 + 4, x2 - 4, y1 + 9,
                    fill=shop["color"], outline="",
                )
                canvas.create_rectangle(
                    x1 + 5, y1 + 13, x2 - 5, y2 - 5,
                    fill="#69b9d1", outline="",
                )
                canvas.create_text(
                    x, y1 - 5, text=shop["title"], fill="white",
                    font=("Arial", max(7, int(scale * 0.85)), "bold"),
                )
            else:
                window = max(3, scale * 0.18)
                for wx in (-1.8, 1.8):
                    for wz in (-1.8, 1.8):
                        px, py = self.to_screen(
                            building["x"] + wx, building["z"] + wz,
                        )
                        canvas.create_rectangle(
                            px - window, py - window, px + window, py + window,
                            fill="#6fb8ca", outline="",
                        )

        for target in self.targets:
            if not target["active"]:
                continue
            x, y = self.to_screen(target["x"], target["z"])
            radius = max(6, scale * 0.48)
            canvas.create_oval(
                x - radius - 3, y - radius - 3, x + radius + 3, y + radius + 3,
                fill="#f3d16c", outline="#fff0a8", width=2,
            )
            canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill="#df7554", outline="#7f3f42", width=2,
            )
            canvas.create_oval(
                x - radius * 0.28, y - radius * 0.28,
                x + radius * 0.28, y + radius * 0.28,
                fill="#fff0a8", outline="",
            )

        self.draw_car()
        if not self.driving:
            self.draw_player()

        if (time.perf_counter() < self.shot_until
                and self.shot_start is not None and self.shot_end is not None):
            start = self.to_screen(*self.shot_start)
            end = self.to_screen(*self.shot_end)
            canvas.create_line(*start, *end, fill="#ffe17a", width=3)

        aim_x, aim_y = self.to_screen(*self.aim)
        canvas.create_oval(
            aim_x - 7, aim_y - 7, aim_x + 7, aim_y + 7,
            outline="#fff0a8", width=2,
        )
        canvas.create_line(aim_x - 11, aim_y, aim_x + 11, aim_y,
                           fill="#fff0a8")
        canvas.create_line(aim_x, aim_y - 11, aim_x, aim_y + 11,
                           fill="#fff0a8")

        mode = "МАШИНА" if self.driving else "ПЕШКОМ"
        speed = f"   {abs(int(self.car['speed'] * 4))} км/ч" if self.driving else ""
        canvas.create_rectangle(
            12, 12, 380, 78, fill="#17202c", stipple="gray50", outline="",
        )
        canvas.create_text(
            22, 20, anchor="nw", fill="white", font=("Arial", 12, "bold"),
            text=f"NEON DISTRICT  |  ${self.cash}  |  {mode}{speed}\n"
                 f"Здоровье {self.health}   Бластер {self.ammo}/{self.reserve}"
                 f"   Ур. {self.weapon_level}",
        )
        canvas.create_text(
            16, height - 14, anchor="sw", fill="white", font=("Arial", 10),
            text="WASD / стрелки — движение   мышь — прицел   "
                 "E — машина/магазин   "
                 "ЛКМ/Space — огонь   R — перезарядка   Esc — выйти",
        )

        prompt = ""
        if self.shop:
            prompt = "1/2 — покупки   E — выйти"
        elif self.driving:
            prompt = "E — выйти из машины"
        elif self.distance_to(self.car["x"], self.car["z"]) < 5:
            prompt = "E — сесть в машину"
        else:
            for shop in self.shops:
                if self.distance_to(shop["x"], shop["z"]) < 8:
                    prompt = f"E — войти: {shop['title']}"
                    break
        if prompt:
            canvas.create_text(
                width / 2, height - 45, text=prompt,
                fill="#fff0a8", font=("Arial", 12, "bold"),
            )

        if self.shop:
            text = self.shop["title"] + "\n"
            if self.shop["kind"] == "weapons":
                text += "1 — 12 зарядов ($25)\n2 — улучшить бластер ($75)\nE / Esc — выйти"
            else:
                text += "1 — обслуживание машины\nE / Esc — выйти"
            canvas.create_rectangle(
                width / 2 - 190, height / 2 - 78,
                width / 2 + 190, height / 2 + 78,
                fill="#17202c", outline="#e8d68d", width=2,
            )
            canvas.create_text(
                width / 2, height / 2, text=text,
                fill="white", font=("Arial", 14, "bold"), justify="center",
            )
        elif self.notice and time.perf_counter() < self.notice_until:
            canvas.create_text(
                width / 2, height * 0.78, text=self.notice,
                fill="#fff0a8", font=("Arial", 15, "bold"),
            )

    def draw_player(self):
        x, y = self.to_screen(self.player["x"], self.player["z"])
        if self.walking:
            y += math.sin(self.walk_phase * 2) * 2
        size = max(9, self.scale * 0.65)
        self.draw_directional_shape(
            x, y, self.player["yaw"],
            ((0, 1.35), (-0.8, -0.75), (0, -0.35), (0.8, -0.75)),
            "#3176a2", size,
        )
        self.canvas.create_oval(
            x - size * 0.25, y - size * 0.25,
            x + size * 0.25, y + size * 0.25,
            fill="#d7aa87", outline="",
        )

    def draw_car(self):
        x, y = self.to_screen(self.car["x"], self.car["z"])
        size = self.scale
        self.draw_directional_shape(
            x, y, self.car["yaw"],
            ((-1.0, -1.4), (1.0, -1.4), (1.0, 1.0),
             (0.65, 1.45), (-0.65, 1.45), (-1.0, 1.0)),
            "#208fa5", size * 1.15,
        )
        self.draw_directional_shape(
            x, y, self.car["yaw"],
            ((-0.7, -0.65), (0.7, -0.65), (0.62, 0.45), (-0.62, 0.45)),
            "#426d7b", size * 1.15,
        )
        for side in (-1, 1):
            for front in (-1, 1):
                wheel_x, wheel_y = self.rotated_point(
                    x, y, self.car["yaw"], side * 0.92, front * 0.8, size * 1.15,
                )
                self.canvas.create_oval(
                    wheel_x - size * 0.15, wheel_y - size * 0.22,
                    wheel_x + size * 0.15, wheel_y + size * 0.22,
                    fill="#20242a", outline="",
                )

    @staticmethod
    def rotated_point(x, y, yaw, local_x, local_z, size):
        return (
            x + size * (local_x * math.cos(yaw) + local_z * math.sin(yaw)),
            y + size * (-local_x * math.sin(yaw) + local_z * math.cos(yaw)),
        )

    def draw_directional_shape(self, x, y, yaw, points, color, size):
        coords = []
        for local_x, local_z in points:
            point = self.rotated_point(x, y, yaw, local_x, local_z, size)
            coords.extend(point)
        self.canvas.create_polygon(
            coords, fill=color, outline="#17202c", width=2,
        )

    def loop(self):
        now = time.perf_counter()
        dt = min(0.04, now - self.last_time)
        self.last_time = now
        self.update(dt)
        self.draw()
        self.root.after(16, self.loop)


def main():
    root = tk.Tk()
    CityGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
