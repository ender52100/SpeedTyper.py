#!/usr/bin/env python3
# speed_typer.py
"""
Speed Typer - Application de jeu de dactylographie multijoueur.

Remarques:
- L'écran d'accueil est préservé.
- Le bouton "Jouer" lance la partie via start_from_home().
- Mode Hardcore : ajuste la plage du slider temps et affiche status pendant la partie.
- Ne pas ajouter de modes d'équipe (2v2/3v3/...), n'ai rien changé à l'UI d'accueil.
"""

import tkinter as tk
import random
import json
import os
import sys
import time

APP_TITLE = "Speed Typer"
WINDOW_SIZE = "980x700"
SCORE_FILE = "scores.json"

PHRASES = [
    "Bonjour tout le monde",
    "Python est génial",
    "Je teste mon speed typer",
    "Ceci est une phrase aléatoire",
    "Battle Royale commence",
    "Équipe gagnante",
    "Les accents aussi comptent",
    "Tape la phrase exactement",
    "Voici une phrase un peu plus longue pour tester le comportement du widget Text"
]

# Optional winsound for Windows
try:
    import winsound
except Exception:
    winsound = None

def play_sound(filename):
    if not filename:
        return
    if winsound and os.name == "nt" and os.path.exists(filename):
        try:
            winsound.PlaySound(filename, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception:
            pass
    else:
        try:
            sys.stdout.write("\a")
            sys.stdout.flush()
        except Exception:
            pass

class SpeedTyper:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry(WINDOW_SIZE)
        self.root.config(bg="#2c3e50")

        # Options
        self.hardcore = tk.BooleanVar(value=False)
        self.long_phrases_mode = tk.BooleanVar(value=False)

        # Runtime state
        self.time_per_player = 30
        self.nb_players = 1
        self.current_mode = "classic"
        self.names = []
        self.team_assignments = {}
        self.num_teams = 1

        self.current_player_index = 0
        self.scores = {}               # {name: total_points}
        self.timer_job = None
        self.time_left = 0
        self.current_phrase = ""
        self.current_player_name = ""
        self.phase_results = []

        self.global_scores = self.load_global_scores()

        # UI refs
        self.main_frame = None
        self.names_frame = None
        self.name_vars = []
        self.entry_text = None
        self.phrase_label = None
        self.timer_label = None
        self.status_label = None
        self.player_info_label = None
        self.home_status_label = None
        self.time_slider = None
        self.nb_players_var = tk.IntVar(value=1)
        self.hardcore_status_label = None

        # Build home (preserve appearance)
        self.show_home()

    # ---------- Persistence ----------
    def load_global_scores(self):
        if not os.path.exists(SCORE_FILE):
            return []
        try:
            with open(SCORE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []


    def save_global_scores(self, entries):
        """entries expected as dict {name: [result_dicts]} or similar; append to file."""
        new_scores = []
        current_timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(entries, dict):
            for name, results in entries.items():
                if isinstance(results, list):
                    for r in results:
                        new_scores.append({
                            "name": name,
                            "score": r.get("wpm", 0),
                            "timestamp": current_timestamp,
                            "phrase": r.get("phrase", "")
                        })
                elif isinstance(results, (int, float)):
                    new_scores.append({"name": name, "score": int(results), "timestamp": current_timestamp, "phrase": ""})
        try:
            data = self.global_scores + new_scores
            data.sort(key=lambda x: x.get("score", 0), reverse=True)
            with open(SCORE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.global_scores = data
        except Exception:
            pass




    def clear_global_scores_inline(self):
        try:
            if os.path.exists(SCORE_FILE):
                os.remove(SCORE_FILE)
            self.global_scores = []
            if self.home_status_label:
                self.home_status_label.config(text="Scores globaux effacés.", fg="#2ecc71")
        except Exception as e:
            if self.home_status_label:
                self.home_status_label.config(text=f"Erreur: {e}", fg="#e74c3c")


                 # ---------- Affichage des scores globaux ----------
    def display_global_scores(self):
        scores_window = tk.Toplevel(self.root)
        scores_window.title("Scores Globaux")
        scores_window.geometry("600x400")
        scores_window.config(bg="#2c3e50")

        tk.Label(
            scores_window,
            text="Scores Globaux (Top 10)",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#2c3e50"
        ).pack(pady=10)

        if not self.global_scores:
            tk.Label(
                scores_window,
                text="Aucun score enregistré.",
                font=("Arial", 14),
                fg="white",
                bg="#2c3e50"
            ).pack(pady=5)
            return

        for i, entry in enumerate(self.global_scores[:10], start=1):
            text = f"{i}. {entry['name']} - {entry['score']} pts ({entry['timestamp']})"
            tk.Label(
                scores_window,
                text=text,
                font=("Arial", 14),
                fg="white",
                bg="#2c3e50",
                anchor="w"
            ).pack(fill="x", padx=10, pady=2)


    # ---------- Utilities ----------
    def clear(self):
        # cancel timers and destroy children safely
        self.cancel_timer()
        for w in self.root.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

    def cancel_timer(self):
        if self.timer_job is not None:
            try:
                self.root.after_cancel(self.timer_job)
            except Exception:
                pass
            self.timer_job = None

    # ---------- Phrase ----------
    def pick_phrase(self):
        if self.long_phrases_mode.get():
            return " ".join(random.choices(PHRASES, k=random.randint(3, 5)))
        return random.choice(PHRASES)

    # ---------- Hardcore slider behavior ----------
    def toggle_hardcore(self):
        # Adjust slider range & color when toggled (home UI unchanged)
        if not self.time_slider:
            return
        if self.hardcore.get():
            self.time_slider.config(from_=10, to=20)
            val = self.time_slider.get()
            if val < 10 or val > 20:
                try:
                    self.time_slider.set(10)
                except Exception:
                    pass
            # Try to set troughcolor (may not work on all platforms)
            try:
                self.time_slider.config(troughcolor="#e74c3c")
            except Exception:
                pass
        else:
            self.time_slider.config(from_=30, to=50)
            val = self.time_slider.get()
            if val < 30 or val > 50:
                try:
                    self.time_slider.set(30)
                except Exception:
                    pass
            try:
                self.time_slider.config(troughcolor="#2ecc71")
            except Exception:
                pass
        # update internal value
        try:
            self.time_per_player = int(self.time_slider.get())
        except Exception:
            self.time_per_player = 30
        # if shown during a running game, update label
        if hasattr(self, "hardcore_status_label") and self.hardcore_status_label and getattr(self.hardcore_status_label, "winfo_exists", lambda: False)():
            try:
                self.hardcore_status_label.config(text=f"Mode Hardcore - Temps: {self.time_per_player}s")
            except Exception:
                pass

    # ---------- Home UI (appearance preserved) ----------
    def show_home(self):
        self.clear()
        self.main_frame = tk.Frame(self.root, bg="#2c3e50")
        self.main_frame.pack(fill="both", expand=True)

        frame = self.main_frame

        # Title
        tk.Label(frame, text="Speed Typer", font=("Helvetica", 36), fg="white", bg="#2c3e50").pack(pady=(12,6))
        tk.Label(frame, text="Choisis ton mode et le nombre de joueurs", font=("Helvetica", 14), fg="#ecf0f1", bg="#2c3e50").pack(pady=(0,12))

        controls = tk.Frame(frame, bg="#2c3e50")
        controls.pack(pady=6)

        # Number of players slider 1..10
        tk.Label(controls, text="Nombre de joueurs (1-10):", fg="white", bg="#2c3e50").grid(row=0, column=0, padx=6, pady=6, sticky="e")
        self.nb_players_var = tk.IntVar(value=1)
        self.nb_players_scale = tk.Scale(controls, from_=1, to=10, orient="horizontal", length=300, bg="#2c3e50",
                                         fg="white", troughcolor="#1abc9c", variable=self.nb_players_var, command=self.on_player_count_change)
        self.nb_players_scale.grid(row=0, column=1, padx=6, pady=6, sticky="w")

        # Time slider (default normal 30..50)
        tk.Label(controls, text="Temps par joueur :", fg="white", bg="#2c3e50").grid(row=1, column=0, padx=6, pady=6, sticky="e")
        self.time_slider = tk.Scale(controls, from_=30, to=50, orient="horizontal", length=300, bg="#2c3e50", fg="white", troughcolor="#2ecc71", command=self.update_slider_time)
        self.time_slider.set(self.time_per_player)
        self.time_slider.grid(row=1, column=1, padx=6, pady=6, sticky="w")

        # Options
        opts = tk.Frame(frame, bg="#2c3e50")
        opts.pack(pady=6)
        tk.Checkbutton(opts, text="Mode Hardcore", variable=self.hardcore, fg="white", bg="#2c3e50", selectcolor="#34495e", command=self.toggle_hardcore).pack(side="left", padx=8)
        tk.Checkbutton(opts, text="Phrases longues", variable=self.long_phrases_mode, fg="white", bg="#2c3e50", selectcolor="#34495e").pack(side="left", padx=8)

        # Buttons (appearance preserved)
        btns = tk.Frame(frame, bg="#2c3e50")
        btns.pack(pady=12)
        tk.Button(btns, text="🔥 Jouer", font=("Helvetica", 14), bg="#2980b9", fg="white", width=18, command=self.start_from_home).grid(row=0, column=0, padx=8)
        

        # Extra controls
        extra = tk.Frame(frame, bg="#2c3e50")
        extra.pack(pady=6)
        tk.Button(extra, text="Effacer scores globaux", font=("Helvetica", 12), bg="#c0392b", fg="white", command=self.clear_global_scores_inline).grid(row=0, column=0, padx=6)
        tk.Button(self.main_frame,text="Afficher scores globaux", font=("Arial", 14), bg="#34495e", fg="white", command=self.display_global_scores).pack(pady=5)



        # Names fields at bottom
        self.names_frame = tk.Frame(frame, bg="#2c3e50")
        self.names_frame.pack(side="bottom", pady=20)  # pas de fill="x"
        tk.Label(self.names_frame, text="Pseudos (modifiable) :", fg="white",bg="#2c3e50").pack(pady=5)
        self._build_name_fields(self.nb_players_var.get())

        # Inline home status
        self.home_status_label = tk.Label(frame, text="", font=("Helvetica", 11), fg="white", bg="#2c3e50")
        self.home_status_label.pack(pady=4)

    def _build_name_fields(self, count):
        for w in self.names_frame.winfo_children():
            w.destroy()
        grid = tk.Frame(self.names_frame, bg="#2c3e50")
        grid.pack(anchor="w", padx=12)
        self.name_vars = []
        for i in range(count):
            lbl = tk.Label(grid, text=f"Joueur {i+1} :", fg="white", bg="#2c3e50")
            lbl.grid(row=i, column=0, padx=6, pady=4, sticky="e")
            var = tk.StringVar(value=f"Joueur{i+1}")
            ent = tk.Entry(grid, width=30, textvariable=var)
            ent.grid(row=i, column=1, padx=6, pady=4, sticky="w")
            self.name_vars.append(var)

    def on_player_count_change(self, v):
        try:
            n = int(float(v))
        except Exception:
            n = 1
        n = max(1, min(10, n))
        self._build_name_fields(n)

    def print_global_scores(self):
        print("--- Global scores ---")
        for s in self.global_scores:
            print(s)

    def update_slider_time(self, val):
        try:
            self.time_per_player = int(float(val))
        except Exception:
            self.time_per_player = 30
        # Only update timer label if it exists and hasn't been destroyed
        if hasattr(self, "timer_label") and self.timer_label and getattr(self.timer_label, "winfo_exists", lambda: False)():
            try:
                self.timer_label.config(text=f"Temps restant: {self.time_per_player}s")
            except Exception:
                pass
        # Also update hardcore status label if visible
        if hasattr(self, "hardcore_status_label") and self.hardcore_status_label and getattr(self.hardcore_status_label, "winfo_exists", lambda: False)():
            try:
                self.hardcore_status_label.config(text=f"Mode Hardcore - Temps: {self.time_per_player}s")
            except Exception:
                pass

    # ---------- Start game ----------
    def start_from_home(self):
        # Initialize current state
        self.nb_players = self.nb_players_var.get() if hasattr(self, "nb_players_var") else 1
        # read names
        self.names = [v.get() for v in self.name_vars] if self.name_vars else [f"Joueur{i+1}" for i in range(self.nb_players)]
        # set time from slider
        try:
            self.time_per_player = int(self.time_slider.get())
        except Exception:
            pass
        self.time_left = self.time_per_player
        self.current_player_index = 0
        self.scores = {}  # reset scores for this session
        self.current_phrase = self.pick_phrase()
        # show game UI
        self.show_game()



    # ---------- Game UI ----------
    def show_game(self):
        self.clear()
        self.main_frame = tk.Frame(self.root, bg="#2c3e50")
        self.main_frame.pack(fill="both", expand=True)

         # Timer label
        top_frame = tk.Frame(self.main_frame, bg="#2c3e50")
        top_frame.pack(fill="x", pady=6, padx=8)
        self.timer_label = tk.Label(top_frame, text=f"Temps restant: {self.time_left}s", fg="white", bg="#2c3e50", font=("Arial", 14))
        self.timer_label.pack(side="right")


  # Phrase à taper
        if self.hardcore.get():
            self.hardcore_status_label = tk.Label(top_frame, text=f"Mode Hardcore - Temps: {self.time_left}s", fg="#e74c3c", bg="#2c3e50", font=("Arial", 12, "bold"))
            self.hardcore_status_label.pack(side="right", padx=12)
        else:
            self.hardcore_status_label = None

        # Zone de texte
        self.phrase_label = tk.Label(self.main_frame, text=self.current_phrase, font=("Arial", 18), fg="white", bg="#2c3e50", wraplength=900, justify="left")
        self.phrase_label.pack(pady=20)

        # text entry area
        self.entry_text = tk.Text(self.main_frame, width=90, height=8, font=("Arial", 16))
        self.entry_text.pack(pady=10)
        self.entry_text.focus()
        # block paste / middle click
        self.entry_text.bind("<<Paste>>", lambda e: "break")
        self.entry_text.bind("<Control-v>", lambda e: "break")
        self.entry_text.bind("<Control-V>", lambda e: "break")
        self.entry_text.bind("<Shift-Insert>", lambda e: "break")
        # real-time validation on typing
        self.entry_text.bind("<KeyRelease>", self.on_text_change)
        self.entry_text.tag_config("green", foreground="#2ecc71")
        self.entry_text.tag_config("red", foreground="#e74c3c")


        # set tags on the text widget (must be on the widget, not on root)
        try:
            self.entry_text.tag_config("green", foreground="#2ecc71")
            self.entry_text.tag_config("red", foreground="#e74c3c")
            self.entry_text.tag_config("black", foreground="#000000")
        except Exception:
            pass

        # reset timer for this round and start countdown
        self.time_left = self.time_per_player
        self.start_time = time.time()
        self.run_timer()


        # Start timer
        self.run_timer()

    def on_text_change(self, event=None):
        # Compare current typed text to phrase prefix-by-prefix and tag colors
        if not self.entry_text or not self.current_phrase:
            return
        typed = self.entry_text.get("1.0", "end-1c")
        # Remove all tags then reapply
        try:
            self.entry_text.tag_remove("green", "1.0", "end")
            self.entry_text.tag_remove("red", "1.0", "end")
            self.entry_text.tag_remove("black", "1.0", "end")
        except Exception:
            pass

        # walk through characters
        for i, ch in enumerate(typed):
            idx_start = f"1.{i}"
            idx_end = f"1.{i+1}"
            if i < len(self.current_phrase) and ch == self.current_phrase[i]:
                try:
                    self.entry_text.tag_add("green", idx_start, idx_end)
                except Exception:
                    pass
            else:
                try:
                    self.entry_text.tag_add("red", idx_start, idx_end)
                except Exception:
                    pass
        # remainder (if any) keep default black (no tag)

    def run_timer(self):
        # update timer label and schedule next tick
        if self.time_left <= 0:
            self.time_left = 0
            if hasattr(self, "timer_label") and self.timer_label and getattr(self.timer_label, "winfo_exists", lambda: False)():
                try:
                    self.timer_label.config(text=f"Temps restant: 0s")
                except Exception:
                    pass
            self.end_round()
            return

        if hasattr(self, "timer_label") and self.timer_label and getattr(self.timer_label, "winfo_exists", lambda: False)():
            try:
                self.timer_label.config(text=f"Temps restant: {self.time_left}s")
            except Exception:
                pass
        if self.hardcore.get() and self.hardcore_status_label and getattr(self.hardcore_status_label, "winfo_exists", lambda: False)():
            try:
                self.hardcore_status_label.config(text=f"Mode Hardcore - Temps: {self.time_left}s")
            except Exception:
                pass

        # decrement and schedule
        self.time_left -= 1
        self.cancel_timer()
        self.timer_job = self.root.after(1000, self.run_timer)

    def end_round(self):
        # Called when time runs out for the current player
        if self.entry_text:
            typed = self.entry_text.get("1.0", "end-1c")
            correct = sum(1 for i, ch in enumerate(typed) if i < len(self.current_phrase) and ch == self.current_phrase[i])
            wpm = int((len(typed) / 5) * (60 / max(1, self.time_per_player)))  # rough estimate
        else:
            correct = 0
            wpm = 0

        # store score as points (you can adapt)
        name = self.names[self.current_player_index] if self.names and self.current_player_index < len(self.names) else f"Joueur{self.current_player_index+1}"
        # Use 'correct' as points for ranking simplicity
        self.scores.setdefault(name, 0)
        self.scores[name] += correct

        # Save this player's result to history (for global save)
        self.phase_results.append({ "name": name, "wpm": wpm, "correct": correct, "phrase": self.current_phrase })

        # Move to next player
        self.current_player_index += 1

        # If all players done -> show podium
        if self.current_player_index >= len(self.names):
            # Save to global (structure expects dict name -> list)
            out = {}
            for r in self.phase_results:
                out.setdefault(r["name"], []).append({"wpm": r["wpm"], "phrase": r["phrase"]})
            try:
                self.save_global_scores(out)
            except Exception:
                pass

            # Build ranking list (name, points)
            ranking = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
            self.show_podium(ranking)
            return

        # Otherwise prepare next round
        self.current_phrase = self.pick_phrase()
        # show the next player's game UI
        self.show_game()

    # ---------- Podium / end screen ----------
    def show_podium(self, ranking):
        self.clear()
        frame = tk.Frame(self.root, bg="#2c3e50")
        frame.pack(fill="both", expand=True)
        self.main_frame = frame



        tk.Label(frame, text="Classement final", font=("Helvetica", 36), fg="white", bg="#2c3e50").pack(pady=8)

        canvas = tk.Canvas(frame, width=900, height=360, bg="#2c3e50", highlightthickness=0)
        canvas.pack()

        # top3 placeholders
        top3 = [("", 0), ("", 0), ("", 0)]
        for i in range(min(3, len(ranking))):
            top3[i] = ranking[i]

        base_y = 300
        gold_h = 160 if top3[0][1] > 0 else 80
        silver_h = 110 if top3[1][1] > 0 else 60
        bronze_h = 70 if top3[2][1] > 0 else 40

        center_x = 450
        gap = 220

        rects = {}
        texts = {}
        rects['gold'] = canvas.create_rectangle(center_x-80, base_y, center_x+80, base_y, fill="#f1c40f", outline="")
        rects['silver'] = canvas.create_rectangle(center_x-gap-70, base_y, center_x-gap+70, base_y, fill="#bdc3c7", outline="")
        rects['bronze'] = canvas.create_rectangle(center_x+gap-60, base_y, center_x+gap+60, base_y, fill="#cd7f32", outline="")

        texts['gold'] = canvas.create_text(center_x, base_y-30, text=f"{top3[0][0]}\n{top3[0][1]} pts", font=("Helvetica", 12, "bold"), fill="#2c3e50", justify="center")
        texts['silver'] = canvas.create_text(center_x-gap, base_y-30, text=f"{top3[1][0]}\n{top3[1][1]} pts", font=("Helvetica", 12, "bold"), fill="#2c3e50", justify="center")
        texts['bronze'] = canvas.create_text(center_x+gap, base_y-30, text=f"{top3[2][0]}\n{top3[2][1]} pts", font=("Helvetica", 12, "bold"), fill="#2c3e50", justify="center")

        steps = 30
        def animate(step=0):
            if step > steps:
                # show full ranking
                list_frame = tk.Frame(frame, bg="#2c3e50")
                list_frame.pack(pady=8, fill="x")
                tk.Label(list_frame, text="Classement complet :", font=("Helvetica", 14), fg="white", bg="#2c3e50").pack(anchor="w")
                txt = tk.Text(list_frame, height=8)
                txt.pack(fill="both", expand=True, padx=12)
                for i, (name, score) in enumerate(ranking, 1):
                    txt.insert("end", f"{i}. {name} - {score} pts\n")
                    txt.config(state="disabled")
                btnf = tk.Frame(frame, bg="#2c3e50")
                btnf.pack(pady=4)


                # Buttons
                btn_frame = tk.Frame(frame, bg="#2c3e50")
                btn_frame.pack(pady=24)
                tk.Button(btn_frame, text="🏠 Accueil", font=("Arial", 14), bg="#3498db", fg="white", command=self.show_home).pack(side="left", padx=12)
                tk.Button(btn_frame, text="Quitter", font=("Arial", 14), bg="#e74c3c", fg="white", command=self.root.quit).pack(side="left", padx=12)
                play_sound("fin.wav")
                return

            # animate heights
            frac = step / steps
            try:
                canvas.coords(rects['gold'], center_x-80, base_y - gold_h*frac, center_x+80, base_y)
                canvas.coords(rects['silver'], center_x-gap-70, base_y - silver_h*frac, center_x-gap+70, base_y)
                canvas.coords(rects['bronze'], center_x+gap-60, base_y - bronze_h*frac, center_x+gap+60, base_y)
            except Exception:
                pass
            self.root.after(15, lambda: animate(step+1))

        animate()



if __name__ == "__main__":
    root = tk.Tk()
    SpeedTyper(root)
    root.mainloop()

  
