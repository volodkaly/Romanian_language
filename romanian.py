import tkinter as tk
from tkinter import messagebox, filedialog
import random
import re
from collections import Counter
import os
import threading

# --- ІМПОРТ ПЕРЕКЛАДАЧА ---
try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False

# --- ФУНКЦІЯ ДЛЯ ДІАКРИТИКИ ---
def normalize_ro_text(text):
    replacements = str.maketrans(
        "ăâîșțşţĂÂÎȘȚŞŢ", 
        "aaiisstAAIISST"
    )
    return text.translate(replacements)

# --- ЛОГІКА ОБРОБКИ ТЕКСТУ ---
def extract_recurring_phrases(file_path, min_repeats, min_words=3, max_words=5):
    try:
        if not os.path.exists(file_path):
            return [], "Файл не знайдено."
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        return [], str(e)

    text = text.lower()
    words = re.findall(r'\w+', text)

    if not words:
        return [], "Файл порожній."

    found_phrases = []
    for n in range(min_words, max_words + 1):
        ngrams = zip(*[words[i:] for i in range(n)])
        phrases_list = [" ".join(ngram) for ngram in ngrams]
        counts = Counter(phrases_list)
        
        for phrase, count in counts.items():
            if count >= min_repeats:
                found_phrases.append({
                    "ro": phrase,
                    "ua": f"Знайдено ({count} разів) | Натисни кнопку перекладу ⬇"
                })

    found_phrases.sort(key=lambda x: int(re.search(r'\d+', x['ua']).group()), reverse=True)
    return found_phrases, None

# --- ГРАФІЧНИЙ ІНТЕРФЕЙС ---

default_phrases = [
    {"ro": "nu știu nimic", "ua": "Я нічого не знаю"},
    {"ro": "ce mai faci", "ua": "Як справи"},
    {"ro": "o zi buna", "ua": "Гарного дня"},
]

class RomanianGapTrainer:
    def __init__(self, root):
        self.root = root
        self.root.title("🇷🇴 Румунський Text-Miner (Навігація Alt+Стрілки)")
        self.root.geometry("700x650")
        
        self.phrases_db = default_phrases
        self.current_pair = None
        
        # --- ІСТОРІЯ ПЕРЕГЛЯДУ ---
        self.history = []        
        self.history_index = -1  
        self.is_solved = False   

        # --- ВЕРХНЯ ПАНЕЛЬ ---
        top_frame = tk.Frame(root, bg="#f0f0f0", pady=10)
        top_frame.pack(fill=tk.X)
        
        tk.Label(top_frame, text="Мін. повторів:", bg="#f0f0f0").pack(side=tk.LEFT, padx=(10, 5))
        self.spin_repeats = tk.Spinbox(top_frame, from_=2, to=100, width=5)
        self.spin_repeats.delete(0, "end")
        self.spin_repeats.insert(0, 5)
        self.spin_repeats.pack(side=tk.LEFT, padx=5)
        
        btn_load = tk.Button(top_frame, text="📂 Відкрити файл", command=self.load_file_action, bg="#FFCC80")
        btn_load.pack(side=tk.LEFT, padx=10)
        
        self.lbl_file_info = tk.Label(top_frame, text="(Старт: стандартні фрази)", bg="#f0f0f0", font=("Arial", 8))
        self.lbl_file_info.pack(side=tk.LEFT, padx=10)

        # --- ІНФОРМАЦІЯ ---
        self.lbl_info = tk.Label(root, text="", font=("Arial", 11, "italic"), fg="#555", wraplength=600)
        self.lbl_info.pack(pady=(20, 5))

        self.btn_translate = tk.Button(root, text="🌐 Показати переклад (Google)", command=self.translate_current_phrase, bg="#E0F7FA", font=("Arial", 9))
        self.btn_translate.pack(pady=(0, 10))

        # --- ТЕКСТ ЗАВДАННЯ ---
        self.lbl_ro_masked = tk.Text(root, font=("Consolas", 20, "bold"), fg="#0055A4",
                             wrap="word", height=2, width=50, bg=root.cget("bg"), bd=0)
        self.lbl_ro_masked.pack(pady=10)
        self.lbl_ro_masked.config(state="disabled")

        self.lbl_slider_info = tk.Label(root, text="Кількість прихованих літер:", font=("Arial", 10))
        self.lbl_slider_info.pack(pady=(5, 0))
        
        self.difficulty_scale = tk.Scale(root, from_=0, to=1, orient=tk.HORIZONTAL, length=400, command=self.update_mask_on_slide)
        self.difficulty_scale.pack(pady=5)

        tk.Label(root, text="Виправ пропуски тут:", font=("Arial", 10, "bold")).pack(pady=(15, 5))
        
        self.entry_answer = tk.Entry(root, font=("Consolas", 16), width=40)
        self.entry_answer.pack(pady=5)
        
        # --- БІНДИ КЛАВІШ (ЗМІНЕНО) ---
        
        # Enter: Перевірка або Наступне
        self.entry_answer.bind('<Return>', self.handle_enter_key)
        
        # Alt + Стрілки: Навігація по історії
        # Звичайні стрілки тепер працюють штатно (рухають курсор)
        self.root.bind('<Alt-Right>', lambda e: self.next_phrase())
        self.root.bind('<Alt-Left>', lambda e: self.prev_phrase())

        # --- КНОПКИ ---
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=20)

        self.btn_prev = tk.Button(btn_frame, text="← Назад (Alt+←)", command=self.prev_phrase, bg="#FFCCBC", font=("Arial", 11))
        self.btn_prev.pack(side=tk.LEFT, padx=10)

        self.btn_check = tk.Button(btn_frame, text="Перевірити (Enter)", command=self.check_answer, bg="#DDDDDD", font=("Arial", 11))
        self.btn_check.pack(side=tk.LEFT, padx=10)

        self.btn_next = tk.Button(btn_frame, text="Вперед (Alt+→)", command=self.next_phrase, bg="#AED581", font=("Arial", 11))
        self.btn_next.pack(side=tk.LEFT, padx=10)

        self.lbl_status = tk.Label(root, text="", font=("Arial", 12))
        self.lbl_status.pack(pady=10)
        
        # Оновлена підказка
        tk.Label(root, text="Підказка: Enter = Перевірити | Alt + ←/→ = Навігація по картках", font=("Arial", 9), fg="gray").pack(side=tk.BOTTOM, pady=5)

        if not HAS_TRANSLATOR:
            self.btn_translate.config(state="disabled", text="Встановіть deep-translator")

        self.next_phrase()

    def load_file_action(self):
        filepath = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt")])
        if not filepath: return
        try:
            repeats = int(self.spin_repeats.get())
        except ValueError:
            repeats = 3

        phrases, error = extract_recurring_phrases(filepath, min_repeats=repeats)
        if error:
            messagebox.showerror("Помилка", error)
            return
        if not phrases:
            messagebox.showwarning("Пусто", f"Не знайдено фраз.")
            return

        self.phrases_db = phrases
        self.history = []
        self.history_index = -1
        
        self.lbl_file_info.config(text=f"Завантажено: {len(phrases)} фраз")
        messagebox.showinfo("Успіх", f"Знайдено {len(phrases)} фраз!")
        self.next_phrase()

    def translate_current_phrase(self):
        if not self.current_pair or not HAS_TRANSLATOR: return
        ro_text = self.current_pair['ro']
        self.btn_translate.config(text="⏳ Завантаження...", state="disabled")

        def run_translation():
            try:
                translator = GoogleTranslator(source='ro', target='uk')
                translated_text = translator.translate(ro_text)
                self.root.after(0, lambda: self.update_ui_with_translation(translated_text))
            except Exception as e:
                self.root.after(0, lambda: self.update_ui_with_translation(f"Помилка: {e}"))

        threading.Thread(target=run_translation, daemon=True).start()

    def update_ui_with_translation(self, text):
        self.lbl_info.config(text=f"🇺🇦 {text}", fg="#000000", font=("Arial", 12, "bold"))
        self.btn_translate.config(text="🌐 Показати переклад (Google)", state="normal")

    def get_masked_string(self, text, num_chars_to_hide):
        indices = [i for i, char in enumerate(text) if char != ' ']
        if not indices: return text
        num_chars_to_hide = min(num_chars_to_hide, len(indices))
        indices_to_hide = set(random.sample(indices, num_chars_to_hide))
        result = []
        for i, char in enumerate(text):
            if i in indices_to_hide: result.append("_")
            else: result.append(char)
        return "".join(result)

    def update_mask_on_slide(self, val):
        if self.current_pair:
            count_to_hide = int(val)
            ro_text = self.current_pair['ro']
            total_chars = len([c for c in ro_text if c != ' '])
            self.lbl_slider_info.config(text=f"Приховано символів: {count_to_hide} / {total_chars}")
            
            masked = self.get_masked_string(ro_text, count_to_hide)
            
            self.lbl_ro_masked.config(state="normal")
            self.lbl_ro_masked.delete("1.0", tk.END)
            self.lbl_ro_masked.insert(tk.END, masked)
            self.lbl_ro_masked.config(state="disabled")

            self.entry_answer.config(bg="white")
            self.entry_answer.delete(0, tk.END)
            self.entry_answer.insert(0, masked)

    def setup_ui_for_current_pair(self):
        self.is_solved = False
        self.lbl_info.config(text=self.current_pair['ua'], fg="#555", font=("Arial", 11, "italic"))
        self.lbl_status.config(text="", fg="black")
        
        ro_text = self.current_pair['ro']
        char_count = len([c for c in ro_text if c != ' '])
        self.difficulty_scale.config(from_=0, to=char_count)
        
        default_hide = 1 if char_count > 0 else 0
        self.difficulty_scale.set(default_hide)
        self.update_mask_on_slide(default_hide)
        self.entry_answer.focus_set()
        
        if self.history_index > 0:
            self.btn_prev.config(state="normal")
        else:
            self.btn_prev.config(state="disabled")

    def prev_phrase(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.current_pair = self.history[self.history_index]
            self.setup_ui_for_current_pair()
            self.lbl_status.config(text="⏮ Повернулися назад", fg="gray")

    def next_phrase(self):
        if not self.phrases_db: return
        
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.current_pair = self.history[self.history_index]
        else:
            self.current_pair = random.choice(self.phrases_db)
            self.history.append(self.current_pair)
            self.history_index += 1
            
        self.setup_ui_for_current_pair()

    def handle_enter_key(self, event):
        if self.is_solved:
            self.next_phrase()
        else:
            self.check_answer()

    def check_answer(self, event=None):
        if not self.current_pair: return
        
        user_input = self.entry_answer.get().strip().lower()
        correct_text = self.current_pair['ro'].strip().lower()

        user_norm = normalize_ro_text(user_input)
        correct_norm = normalize_ro_text(correct_text)

        if user_norm == correct_norm:
            self.is_solved = True
            
            if user_input == correct_text:
                self.lbl_status.config(text="✅ Ідеально! (Тисни Enter або Alt+→)", fg="green")
            else:
                self.lbl_status.config(text=f"✅ Зараховано! (Правильно: {correct_text})", fg="#2E7D32")
            
            self.entry_answer.config(bg="#DFF2BF")
        else:
            self.lbl_status.config(text=f"❌ Ще є помилки...", fg="red")
            self.entry_answer.config(bg="#FFBABA")

if __name__ == "__main__":
    root = tk.Tk()
    app = RomanianGapTrainer(root)
    root.mainloop()