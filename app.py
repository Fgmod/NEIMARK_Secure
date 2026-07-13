import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from PIL import Image, ImageDraw, ImageTk
import models
import qrcode
import io
import os
import json

# ------------------------------------------------------------
# 1. СОЗДАНИЕ ИКОНКИ (оранжевый круг с буквой N)
# ------------------------------------------------------------
def create_icon():
    if os.path.exists("icon.ico"):
        return "icon.ico"
    size = 64
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, size-4, size-4), fill=(255, 140, 0, 255))  # оранжевый
    draw.text((size//2-12, size//2-14), "N", fill="white", font=None, size=36)
    img.save("icon.ico", format="ICO", sizes=[(size, size)])
    return "icon.ico"

ICON_PATH = create_icon()

# ------------------------------------------------------------
# 2. НАСТРОЙКА СТИЛЕЙ 
# ------------------------------------------------------------
def setup_styles():
    style = ttk.Style()
    style.theme_use('clam')
    
    bg = "#1a1a1a"         
    fg = "#f0f0f0"          
    accent = "#FF8C00"     
    accent_dark = "#CC7000"
    card_bg = "#2a2a2a"
    
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 12))
    style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"), foreground=accent)
    style.configure("Subtitle.TLabel", font=("Segoe UI", 14), foreground=fg)
    style.configure("Accent.TLabel", foreground=accent, font=("Segoe UI", 12, "bold"))
    style.configure("TButton", font=("Segoe UI", 12, "bold"), padding=8,
                    background=accent, foreground=bg)
    style.map("TButton",
              background=[('active', accent_dark), ('pressed', accent_dark)],
              foreground=[('active', bg)])
    style.configure("Card.TFrame", background=card_bg, relief="flat", borderwidth=0)
    style.configure("TEntry", fieldbackground=card_bg, foreground=fg,
                    insertcolor=accent, font=("Segoe UI", 14), borderwidth=0, padding=8)
    style.configure("TNotebook", background=bg, borderwidth=0)
    style.configure("TNotebook.Tab", font=("Segoe UI", 11), padding=[10, 5],
                    background=bg, foreground=fg)
    style.map("TNotebook.Tab", background=[('selected', accent)], foreground=[('selected', bg)])
    return style

# ------------------------------------------------------------
# 3. ОСНОВНОЕ ПРИЛОЖЕНИЕ
# ------------------------------------------------------------
class SecureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NEIMARK Secure")
        self.root.geometry("700x800")
        self.root.minsize(650, 750)
        self.root.configure(bg="#1a1a1a")
        try:
            self.root.iconbitmap(ICON_PATH)
        except:
            pass
        
        self.current_user = None
        self.pending_user = None
        self.totp_secret = None
        self.after_registration = False
        self.frames = {}
        
        self.container = ttk.Frame(root, padding=30)
        self.container.pack(fill="both", expand=True)
        
        for F in (LoginPage, RegisterPage, Setup2FAPage, ProfilePage):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.place(relwidth=1, relheight=1)
        
        self.show_frame("LoginPage", animate=False)
    
    def show_frame(self, page_name, animate=True):
        frame = self.frames[page_name]
        frame.place(relwidth=1, relheight=1)
        frame.tkraise()
        if hasattr(frame, 'on_show'):
            frame.on_show()
    
    def login_success(self, username):
        self.current_user = username
        models.log_security_event("LOGIN", username, "Успешный вход с 2FA")
        self.show_frame("ProfilePage")
    
    def logout(self):
        if self.current_user:
            models.log_security_event("LOGOUT", self.current_user, "Выход")
        self.current_user = None
        self.pending_user = None
        self.after_registration = False
        self.show_frame("LoginPage")

# ------------------------------------------------------------
# 4. СТРАНИЦА ВХОДА
# ------------------------------------------------------------
class LoginPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="TFrame")
        self.controller = controller
        self.init_ui()
    
    def init_ui(self):
        ttk.Label(self, text="🔐 NEIMARK Secure", style="Title.TLabel").pack(pady=(0, 5))
        ttk.Label(self, text="Двухфакторная аутентификация", style="Subtitle.TLabel").pack(pady=(0, 30))
        
        card = ttk.Frame(self, style="Card.TFrame")
        card.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(card, text="Имя пользователя", style="Accent.TLabel").pack(anchor="w", pady=(10, 2))
        self.username_entry = ttk.Entry(card, width=30)
        self.username_entry.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(card, text="Пароль", style="Accent.TLabel").pack(anchor="w", pady=(10, 2))
        self.password_entry = ttk.Entry(card, width=30, show="*")
        self.password_entry.pack(fill="x", padx=5, pady=5)
        
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="🔓 Войти", command=self.do_login).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="📝 Регистрация", 
                   command=lambda: self.controller.show_frame("RegisterPage")).pack(side="left", padx=5)
        
        self.status_label = ttk.Label(self, text="", foreground="#FF6B6B", font=("Segoe UI", 12))
        self.status_label.pack(pady=5)
    
    def do_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not username or not password:
            self.status_label.config(text="Заполните все поля")
            return
        if models.verify_password(username, password):
            self.controller.pending_user = username
            self.prompt_2fa(username)
        else:
            models.log_security_event("FAILED_LOGIN", username, "Неверный пароль")
            self.status_label.config(text="Неверное имя или пароль")
    
    def prompt_2fa(self, username):
        win = tk.Toplevel(self)
        win.title("Подтверждение 2FA")
        win.geometry("380x220")
        win.resizable(False, False)
        win.configure(bg="#1a1a1a")
        try:
            win.iconbitmap(ICON_PATH)
        except: pass
        win.grab_set()
        
        ttk.Label(win, text=f"👤 {username}", font=("Segoe UI", 14), background="#1a1a1a", foreground="#f0f0f0").pack(pady=10)
        ttk.Label(win, text="Введите 6-значный код из аутентификатора:", font=("Segoe UI", 12), background="#1a1a1a", foreground="#f0f0f0").pack()
        code_entry = ttk.Entry(win, width=10, font=("Segoe UI", 18), show="*")
        code_entry.pack(pady=10)
        code_entry.focus()
        
        def verify():
            code = code_entry.get().strip()
            if len(code) != 6 or not code.isdigit():
                messagebox.showerror("Ошибка", "Введите 6 цифр")
                return
            if models.verify_totp(username, code):
                models.log_security_event("2FA_OK", username, "Код верный")
                win.destroy()
                self.controller.login_success(username)
            else:
                models.log_security_event("FAILED_2FA", username, "Неверный TOTP-код")
                messagebox.showerror("Ошибка", "Неверный код. Попробуйте снова.")
                code_entry.delete(0, tk.END)
        
        ttk.Button(win, text="✅ Подтвердить", command=verify).pack(pady=10)
        win.bind('<Return>', lambda e: verify())
    
    def on_show(self):
        self.status_label.config(text="")
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)

# ------------------------------------------------------------
# 5. СТРАНИЦА РЕГИСТРАЦИИ
# ------------------------------------------------------------
class RegisterPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="TFrame")
        self.controller = controller
        self.init_ui()
    
    def init_ui(self):
        ttk.Label(self, text="📝 Регистрация", style="Title.TLabel").pack(pady=(0, 10))
        ttk.Label(self, text="Создайте защищённую учётную запись", style="Subtitle.TLabel").pack(pady=(0, 20))
        
        card = ttk.Frame(self, style="Card.TFrame")
        card.pack(fill="x", padx=20, pady=10)
        
        ttk.Label(card, text="Имя пользователя", style="Accent.TLabel").pack(anchor="w", pady=(10, 2))
        self.username_entry = ttk.Entry(card, width=30)
        self.username_entry.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(card, text="Пароль", style="Accent.TLabel").pack(anchor="w", pady=(10, 2))
        self.password_entry = ttk.Entry(card, width=30, show="*")
        self.password_entry.pack(fill="x", padx=5, pady=5)
        self.password_entry.bind('<KeyRelease>', self.check_strength)
        
        ttk.Label(card, text="Подтвердите пароль", style="Accent.TLabel").pack(anchor="w", pady=(10, 2))
        self.confirm_entry = ttk.Entry(card, width=30, show="*")
        self.confirm_entry.pack(fill="x", padx=5, pady=5)
        
        self.pw_status = ttk.Label(card, text="", foreground="#FF8C00", font=("Segoe UI", 11))
        self.pw_status.pack(anchor="w", padx=5, pady=5)
        
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="📝 Зарегистрироваться", command=self.do_register).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="🔙 Назад", 
                   command=lambda: self.controller.show_frame("LoginPage")).pack(side="left", padx=5)
        
        self.status_label = ttk.Label(self, text="", foreground="#FF6B6B", font=("Segoe UI", 12))
        self.status_label.pack(pady=5)
    
    def check_strength(self, event=None):
        pw = self.password_entry.get()
        if pw:
            ok, msg = models.is_password_strong(pw)
            color = "#28B463" if ok else "#FF8C00"
            self.pw_status.config(text=msg, foreground=color)
        else:
            self.pw_status.config(text="")
    
    def do_register(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        confirm = self.confirm_entry.get()
        if not username or not password or not confirm:
            self.status_label.config(text="Заполните все поля")
            return
        if password != confirm:
            self.status_label.config(text="Пароли не совпадают")
            return
        ok, msg = models.is_password_strong(password)
        if not ok:
            self.status_label.config(text="❌ " + msg)
            return
        result, error = models.create_user(username, password)
        if result:
            models.log_security_event("REGISTER", username, "Успешная регистрация")
            self.controller.totp_secret = result["totp_secret"]
            self.controller.pending_user = username
            self.controller.after_registration = True
            self.controller.show_frame("Setup2FAPage")
            self.username_entry.delete(0, tk.END)
            self.password_entry.delete(0, tk.END)
            self.confirm_entry.delete(0, tk.END)
            self.pw_status.config(text="")
            self.status_label.config(text="")
        else:
            self.status_label.config(text="❌ " + error)
    
    def on_show(self):
        self.status_label.config(text="")
        self.pw_status.config(text="")

# ------------------------------------------------------------
# 6. СТРАНИЦА НАСТРОЙКИ 2FA
# ------------------------------------------------------------
class Setup2FAPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="TFrame")
        self.controller = controller
        self.init_ui()
    
    def init_ui(self):
        ttk.Label(self, text="📱 Настройка 2FA", style="Title.TLabel").pack(pady=(0, 10))
        self.info_label = ttk.Label(self, text="", style="Subtitle.TLabel", wraplength=500)
        self.info_label.pack(pady=(0, 15))
        
        self.qr_label = ttk.Label(self)
        self.qr_label.pack(pady=10)
        
        self.secret_label = ttk.Label(self, text="", font=("Courier", 10), foreground="#FF8C00")
        self.secret_label.pack(pady=5)
        
        ttk.Label(self, text="Введите код для подтверждения:", style="Accent.TLabel").pack(pady=(15, 5))
        self.code_entry = ttk.Entry(self, width=10, font=("Segoe UI", 18), show="*")
        self.code_entry.pack()
        self.code_entry.focus()
        
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="✅ Подтвердить", command=self.verify_setup).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Пропустить", command=self.skip_setup).pack(side="left", padx=5)
        
        self.status_label = ttk.Label(self, text="", font=("Segoe UI", 12))
        self.status_label.pack(pady=5)
        self.code_entry.bind('<Return>', lambda e: self.verify_setup())
    
    def on_show(self):
        if not self.controller.after_registration:
            self.controller.show_frame("LoginPage")
            return
        username = self.controller.pending_user
        self.info_label.config(text=f"Пользователь: {username}\nОтсканируйте QR-код в приложении-аутентификаторе")
        uri = models.get_totp_uri(username)
        if uri:
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            pil_img = Image.open(buf).resize((200, 200), Image.LANCZOS)
            self.qr_img = ImageTk.PhotoImage(pil_img)
            self.qr_label.config(image=self.qr_img)
            self.secret_label.config(text=f"Секрет: {self.controller.totp_secret}")
        self.code_entry.delete(0, tk.END)
        self.status_label.config(text="")
    
    def verify_setup(self):
        code = self.code_entry.get().strip()
        username = self.controller.pending_user
        if len(code) != 6 or not code.isdigit():
            self.status_label.config(text="Введите 6 цифр", foreground="#FF6B6B")
            return
        if models.verify_totp(username, code):
            models.log_security_event("2FA_ENABLED", username, "2FA успешно настроена")
            self.status_label.config(text="✅ 2FA настроена!", foreground="#28B463")
            self.controller.after_registration = False
            self.controller.show_frame("LoginPage")
        else:
            self.status_label.config(text="❌ Неверный код", foreground="#FF6B6B")
            self.code_entry.delete(0, tk.END)
    
    def skip_setup(self):
        self.controller.after_registration = False
        messagebox.showwarning("Внимание", "Вы пропустили настройку 2FA. Ваш аккаунт менее защищён.")
        self.controller.show_frame("LoginPage")

# ------------------------------------------------------------
# 7. СТРАНИЦА ПРОФИЛЯ С ВКЛАДКАМИ (с профилем студента)
# ------------------------------------------------------------
class ProfilePage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent, style="TFrame")
        self.controller = controller
        self.init_ui()
    
    def init_ui(self):
        # верхняя панель
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", pady=(0, 15))
        ttk.Label(top_frame, text="👤 NEIMARK Secure", style="Title.TLabel").pack(side="left")
        ttk.Button(top_frame, text="🚪 Выйти", command=self.controller.logout).pack(side="right")
        
        
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        
        # вкладка "Профиль"
        profile_tab = ttk.Frame(notebook, style="TFrame")
        notebook.add(profile_tab, text="📋 Профиль")
        self.build_profile_tab(profile_tab)
        
        # вкладка "Кампус"
        about_tab = ttk.Frame(notebook, style="TFrame")
        notebook.add(about_tab, text="🏛️ Кампус NEIMARK")
        self.build_about_tab(about_tab)
        
        # вкладка "Карта"
        map_tab = ttk.Frame(notebook, style="TFrame")
        notebook.add(map_tab, text="🗺️ Карта")
        self.build_map_tab(map_tab)
        
        # вкладка "Логи"
        logs_tab = ttk.Frame(notebook, style="TFrame")
        notebook.add(logs_tab, text="📜 Логи")
        self.build_logs_tab(logs_tab)
    
    def build_profile_tab(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(card, text="Информация о студенте", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 10))
        
        # сохраненные данные
        user = models.get_user(self.controller.current_user)
        profile = {}
        if user and user.get("profile_data"):
            try:
                profile = json.loads(user["profile_data"])
            except:
                profile = {}
        
        # поля
        fields = [
            ("fullname", "ФИО"),
            ("course", "Курс"),
            ("faculty", "Факультет"),
            ("group", "Группа"),
            ("schedule", "Текущие пары")
        ]
        self.entries = {}
        for key, label in fields:
            ttk.Label(card, text=label, style="Accent.TLabel").pack(anchor="w", pady=(5, 0))
            entry = ttk.Entry(card, width=40)
            entry.insert(0, profile.get(key, ""))
            entry.pack(fill="x", padx=5, pady=2)
            self.entries[key] = entry
        
        # кнопка сохранения
        btn_save = ttk.Button(card, text="💾 Сохранить профиль", command=self.save_profile)
        btn_save.pack(pady=15)
        
        self.profile_status = ttk.Label(card, text="", foreground="#28B463", font=("Segoe UI", 11))
        self.profile_status.pack()
    
    def save_profile(self):
        data = {key: entry.get().strip() for key, entry in self.entries.items()}
        profile_json = json.dumps(data, ensure_ascii=False)
        models.update_profile(self.controller.current_user, profile_json)
        models.log_security_event("PROFILE_UPDATED", self.controller.current_user, "Обновлён профиль")
        self.profile_status.config(text="✅ Профиль сохранён", foreground="#28B463")
    
    def build_about_tab(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(card, text="🏛️ IT-кампус «NEIMARK»", style="Title.TLabel").pack(anchor="w", pady=(0,10))
        about_text = (
            "📍 Нижний Новгород, ул. Большая Печёрская, 25\n\n"
            "NEIMARK — современный кампус для IT-специалистов. "
            "Здесь проводятся хакатоны, лекции, менторские программы. "
            "Кампус объединяет студентов, разработчиков и предпринимателей.\n\n"
            "🌟 Ключевые направления:\n"
            "• Искусственный интеллект\n"
            "• Кибербезопасность\n"
            "• Веб-разработка\n"
            "• Data Science\n\n"
            "В NEIMARK создана уникальная экосистема для роста и нетворкинга."
        )
        text_widget = tk.Text(card, wrap="word", font=("Segoe UI", 13), bg="#2a2a2a", fg="#f0f0f0",
                              relief="flat", highlightthickness=0)
        text_widget.insert("1.0", about_text)
        text_widget.config(state="disabled")
        text_widget.pack(fill="both", expand=True, pady=5)
    
    def build_map_tab(self, parent):
        # Карта 
        canvas = tk.Canvas(parent, bg="#1a1a1a", highlightthickness=0)
        canvas.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Сами здания 
        # главный корпус
        canvas.create_rectangle(120, 100, 320, 200, fill="#FF8C00", outline="#CC7000", width=3)
        canvas.create_text(220, 150, text="Главный корпус", fill="white", font=("Segoe UI", 14, "bold"))
        # коворкинг
        canvas.create_rectangle(370, 80, 520, 180, fill="#E67E00", outline="#CC7000", width=3)
        canvas.create_text(445, 130, text="Коворкинг", fill="white", font=("Segoe UI", 14, "bold"))
        # лаборатория
        canvas.create_rectangle(140, 250, 300, 350, fill="#FF8C00", outline="#CC7000", width=3)
        canvas.create_text(220, 300, text="Лаборатория", fill="white", font=("Segoe UI", 14, "bold"))
        # амфитеатр
        canvas.create_oval(370, 240, 500, 380, fill="#E67E00", outline="#CC7000", width=3)
        canvas.create_text(435, 310, text="Амфитеатр", fill="white", font=("Segoe UI", 14, "bold"))
        # дорожки
        canvas.create_line(220, 200, 220, 250, fill="#FF8C00", width=6, dash=(4,2))
        canvas.create_line(320, 150, 370, 130, fill="#FF8C00", width=6, dash=(4,2))
        canvas.create_line(220, 350, 220, 400, fill="#FF8C00", width=6, dash=(4,2))
        canvas.create_line(445, 180, 445, 240, fill="#FF8C00", width=6, dash=(4,2))
        # подпись
        canvas.create_text(550, 10, text="🗺️ Схема кампуса", fill="#FF8C00", font=("Segoe UI", 16, "bold"), anchor="ne")
        canvas.create_text(550, 35, text="NEIMARK", fill="#f0f0f0", font=("Segoe UI", 12), anchor="ne")
    
    def build_logs_tab(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(card, text="📜 Журнал событий", style="Subtitle.TLabel").pack(anchor="w", pady=(0,10))
        self.log_text = scrolledtext.ScrolledText(card, height=12, font=("Courier", 10),
                                                   bg="#2a2a2a", fg="#f0f0f0", relief="flat")
        self.log_text.pack(fill="both", expand=True)
        ttk.Button(card, text="🔄 Обновить", command=self.refresh_logs).pack(pady=5)
        self.refresh_logs()
    
    def refresh_logs(self):
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        try:
            with open("security.log", "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-20:]:
                    self.log_text.insert(tk.END, line)
        except FileNotFoundError:
            self.log_text.insert(tk.END, "Лог-файл пока пуст")
        self.log_text.config(state="disabled")
    
    def on_show(self):
        if not self.controller.current_user:
            self.controller.show_frame("LoginPage")
        else:
            self.refresh_logs()
            user = models.get_user(self.controller.current_user)
            if user and user.get("profile_data"):
                try:
                    profile = json.loads(user["profile_data"])
                    for key, entry in self.entries.items():
                        entry.delete(0, tk.END)
                        entry.insert(0, profile.get(key, ""))
                except:
                    pass

# ------------------------------------------------------------
# 8. ЗАПУСК
# ------------------------------------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    setup_styles()
    app = SecureApp(root)
    root.mainloop()