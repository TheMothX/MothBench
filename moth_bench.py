"""
Moth-Bench - GUI benchmark client for /v1/chat/completions-compatible LLM endpoints.

Features:
- Runs a fixed battery of 43 moth-themed prompts (logic, math, code, reasoning)
- Measures latency per test and overall average
- Shows live progress in a CustomTkinter UI
- Exports an HTML scorecard with a simple leaderboard
- Leaderboard can use community reference benchmarks from benchmarks.json

Author: Christian Hay
License: MIT
"""

__version__ = "1.0.0"

import customtkinter as ctk
import requests
import threading
import time
import webbrowser
import html
import json
from pathlib import Path
from tkinter import filedialog


class MothBench(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Moth-Bench v1.8")
        self.geometry("1150x900")
        ctk.set_appearance_mode("dark")

        self.accent_color = "#e84393"
        self.secondary_color = "#6c5ce7"
        self._last_results = None
        self.cancel_evt = threading.Event()

        # Sidebar setup
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar.pack(side="left", fill="y", padx=0, pady=0)

        ctk.CTkLabel(
            self.sidebar,
            text="🦋 MOTH-BENCH",
            font=("Helvetica", 26, "bold"),
            text_color=self.secondary_color,
        ).pack(pady=(40, 5))

        ctk.CTkLabel(
            self.sidebar,
            text="HARDCORE BENCHMARK",
            font=("Helvetica", 10, "italic"),
        ).pack(pady=(0, 20))

        # Endpoint entry (nøytral for GitHub)
        self.url_entry = ctk.CTkEntry(
            self.sidebar,
            width=220,
            border_color=self.secondary_color,
        )
        self.url_entry.insert(0, "http://127.0.0.1:8081/v1")
        self.url_entry.pack(pady=5)

        # Max tokens
        ctk.CTkLabel(
            self.sidebar,
            text="Max tokens",
            font=("Helvetica", 11),
        ).pack(pady=(10, 0))

        self.max_tokens_entry = ctk.CTkEntry(
            self.sidebar,
            width=80,
            border_color=self.secondary_color,
        )
        self.max_tokens_entry.insert(0, "512")
        self.max_tokens_entry.pack(pady=(0, 10))

        # System prompt
        ctk.CTkLabel(
            self.sidebar,
            text="System prompt",
            font=("Helvetica", 11),
        ).pack(pady=(5, 0))

        self.system_prompt_box = ctk.CTkTextbox(
            self.sidebar,
            width=240,
            height=90,
            border_width=1,
            border_color="#353b48",
            wrap="word",
        )
        self.system_prompt_box.insert(
            "1.0",
            (
                "You are a precise assistant being benchmarked with "
                "moth-themed logic, math, code and reasoning tasks. "
                "Answer clearly and concisely, show reasoning for logic/math, "
                "and return valid code where requested."
            ),
        )
        self.system_prompt_box.pack(pady=(0, 10))

        # Progress
        self.prog_label = ctk.CTkLabel(
            self.sidebar,
            text="PROGRESS: 0%",
            font=("Helvetica", 11),
        )
        self.prog_label.pack(pady=(5, 5))

        self.progress_bar = ctk.CTkProgressBar(
            self.sidebar,
            width=220,
            progress_color=self.accent_color,
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(pady=5)

        # Buttons
        self.btn = ctk.CTkButton(
            self.sidebar,
            text="🚀 START MOTH-TEST",
            command=self.start_thread,
            fg_color=self.secondary_color,
            hover_color="#5849c4",
            height=45,
            font=("Helvetica", 14, "bold"),
        )
        self.btn.pack(pady=10, padx=20)

        self.cancel_btn = ctk.CTkButton(
            self.sidebar,
            text="🛑 CANCEL",
            fg_color="#555",
            hover_color="#444",
            command=self.cancel_run,
            height=34,
            state="disabled",
        )
        self.cancel_btn.pack(pady=5, padx=20)

        self.export_btn = ctk.CTkButton(
            self.sidebar,
            text="🌐 Export Scorecard",
            fg_color="#27ae60",
            hover_color="#219150",
            height=34,
            command=self.export_scorecard,
        )
        self.export_btn.pack(pady=(20, 5), padx=20)

        self.copy_btn = ctk.CTkButton(
            self.sidebar,
            text="📋 Copy Log",
            height=34,
            command=self.copy_log,
        )
        self.copy_btn.pack(pady=5, padx=20)

        self.stats_label = ctk.CTkLabel(
            self.sidebar,
            text="System Ready",
            font=("Helvetica", 13),
        )
        self.stats_label.pack(pady=20)

        # Main Log Window
        self.txt = ctk.CTkTextbox(
            self,
            width=850,
            font=("Consolas", 11),
            border_width=2,
            border_color="#353b48",
            wrap="none",
        )
        self.txt.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        # Tilgang til underliggende tk.Text for tagging
        self.txt._textbox.tag_configure("ok", foreground="#55efc4")
        self.txt._textbox.tag_configure("fail", foreground="#ff7675")
        self.txt._textbox.tag_configure("pending", foreground="#fdcb6e")

        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ---------------------
    # Tests
    # ---------------------
    def get_tests(self):
        raw = [
            # LOGIKK
            {
                "c": "Logic",
                "n": "Moth & Flame",
                "q": "A moth is 10m from a flame. Every second it flies half the remaining distance. Will it ever reach the flame?",
            },
            {
                "c": "Logic",
                "n": "The Silk Lie",
                "q": "A Silk-moth always tells the truth, a Dust-moth always lies. One says: 'I am a Dust-moth.' Which moth is it?",
            },
            {
                "c": "Logic",
                "n": "Lunar Navigation",
                "q": "Moths use the moon to fly straight. If a moth mistakes a street lamp for the moon, what path will it fly?",
            },
            {
                "c": "Logic",
                "n": "Camouflage",
                "q": "A Peppered Moth sits on a soot-covered tree. If it is white, it gets eaten. If it is black, it survives. Explain the evolution.",
            },
            {
                "c": "Logic",
                "n": "Moth Box",
                "q": "3 boxes: 'Silk', 'Dust', 'Mixed'. All labels wrong. Pick item from 'Mixed' and see silk. Label the boxes.",
            },
            {
                "c": "Logic",
                "n": "Night Flight",
                "q": "If all moths fly at night, and this creature flies at noon, can it be a moth?",
            },
            {
                "c": "Logic",
                "n": "Cocoon Math",
                "q": "It takes 10 moths 10 days to spin 10 cocoons. How long for 100 moths to spin 100 cocoons?",
            },
            {
                "c": "Logic",
                "n": "Attraction",
                "q": "Why do moths fly toward light if it leads to death? Analyze the paradox.",
            },
            {
                "c": "Logic",
                "n": "Moth Paradox",
                "q": "The sentence: 'This moth is currently invisible.' Is it true or false?",
            },
            {
                "c": "Logic",
                "n": "Lamp Trap",
                "q": "Moth in lamp. Blue or red wire exit. Blue safe if red is hot. Red is hot. Is blue safe?",
            },

            # MATTE
            {
                "c": "Math",
                "n": "Wing Beats",
                "q": "A moth beats wings 25 times/sec. How many beats in 7^3 seconds?",
            },
            {
                "c": "Math",
                "n": "Silk Length",
                "q": "A cocoon has 900m silk. If 13 cocoons are unraveled, how much silk is there mod 7?",
            },
            {
                "c": "Math",
                "n": "Population",
                "q": "Population doubles every Tuesday. Have 1 moth on Tuesday, how many after 5 weeks?",
            },
            {
                "c": "Math",
                "n": "Flight Path",
                "q": "Find derivative of moth spiral: f(x) = e^x * cos(x^2).",
            },
            {
                "c": "Math",
                "n": "Antenna Prob",
                "q": "1/13 chance of finding mate. Probability it fails 5 times in a row?",
            },
            {
                "c": "Math",
                "n": "Moth Stats",
                "q": "Explain the Bell Curve in terms of moth wing spans.",
            },
            {
                "c": "Math",
                "n": "Sphere Moth",
                "q": "A spherical moth has a radius of 3cm. What is its volume?",
            },
            {
                "c": "Math",
                "n": "Larva Growth",
                "q": "Solve for x: 5x (larva weight) + 12 = 3x + 30.",
            },
            {
                "c": "Math",
                "n": "Fibonacci Moth",
                "q": "Moths reproduce in Fibonacci sequence. What is the 10th number?",
            },
            {
                "c": "Math",
                "n": "Binary Wing",
                "q": "Convert number of moth species (160,000) to Hexadecimal.",
            },

            # KODING
            {
                "c": "Code",
                "n": "Moth-Cache",
                "q": "Write a Python LRU Cache for 'Moth-Images' with O(1) access.",
            },
            {
                "c": "Code",
                "n": "Light Sync",
                "q": "Code a C++ Mutex to prevent moths hitting the same 'Lamp' (resource).",
            },
            {
                "c": "Code",
                "n": "Moth-SQL",
                "q": "SQL: Find average wingspan grouped by 'Forest_ID' where wingspan > 10.",
            },
            {
                "c": "Code",
                "n": "Wing Regex",
                "q": "Regex to match moth serials: MOTH-2024-XXXX (X=digits).",
            },
            {
                "c": "Code",
                "n": "Moth-Sort",
                "q": "Explain QuickSort by using moths of different sizes in a line.",
            },
            {
                "c": "Code",
                "n": "Recursive Moth",
                "q": "Write recursive function to calculate 'Dust-factor' of moth wing.",
            },
            {
                "c": "Code",
                "n": "Git Moth",
                "q": "Explain 'git checkout -b new-wing' vs merging back to main.",
            },
            {
                "c": "Code",
                "n": "Moth API",
                "q": "Create FastAPI endpoint '/moth_status' that returns JSON {'status': 'flying'}.",
            },
            {
                "c": "Code",
                "n": "Search Moth",
                "q": "Implement Binary Search to find specific moth ID in sorted list.",
            },
            {
                "c": "Code",
                "n": "Moth-Docker",
                "q": "Write Dockerfile to containerize a 'Moth-Detection' script.",
            },

            # TRICK & SENSE
            {
                "c": "Trick",
                "n": "Noah's Moth",
                "q": "How many moths did Moses bring on the Ark?",
            },
            {
                "c": "Trick",
                "n": "Wing Armor",
                "q": "Moths return with holes in wings. Where should you add armor? (Think Wald).",
            },
            {
                "c": "Trick",
                "n": "Silk Price",
                "q": "3 moths buy lamp for $30. Each gets $1 back. Bellboy keeps $2. Where is the missing dollar?",
            },
            {
                "c": "Sense",
                "n": "Moth Theory",
                "q": "Sally hides silk in leaf. Anne moves it to log. Where will Sally look?",
            },
            {
                "c": "Sense",
                "n": "Gravity",
                "q": "A moth and a pebble fall in a vacuum. Which hits first?",
            },
            {
                "c": "Sense",
                "n": "Compass",
                "q": "Direction a moth flies if the North Star is on its left?",
            },
            {
                "c": "Sense",
                "n": "Energy",
                "q": "Which part of moth anatomy uses the most oxygen during flight?",
            },
            {
                "c": "Sense",
                "n": "Reaction",
                "q": "What happens when a moth touches a bug zapper? Physics.",
            },
            {
                "c": "Sense",
                "n": "History",
                "q": "How did 'Computer Bug' relate to a real moth in 1947?",
            },
            {
                "c": "Stress",
                "n": "Moth Poetry",
                "q": "Write a haiku about a moth longing for the moon.",
            },
            {
                "c": "Stress",
                "n": "No-Lie World",
                "q": "Describe moth colony where nobody can lie for 24 hours.",
            },
            {
                "c": "Stress",
                "n": "Moth Future",
                "q": "Will AI-Moths replace real moths? Argue both sides.",
            },
            {
                "c": "Stress",
                "n": "Final Moth",
                "q": "Explain Quantum Entanglement using two moths on opposite sides of galaxy.",
            },
        ]

        for t in raw:
            t["q"] = html.unescape(t["q"])
            t["n"] = html.unescape(t["n"])
        return raw

    # ---------------------
    # Control actions
    # ---------------------
    def cancel_run(self):
        self.cancel_evt.set()
        self.stats_label.configure(text="Cancelling...")

    def copy_log(self):
        txt = self.txt.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(txt)
        self.stats_label.configure(text="Log copied")

    # ---------------------
    # Scorecard / leaderboard
    # ---------------------
    def load_benchmarks(self, avg_s: float):
        """Load community reference benchmarks from benchmarks.json if present."""
        path = Path(__file__).with_name("benchmarks.json")
        refs = []
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    refs = json.load(f)
            except Exception:
                refs = []

        # fallback defaults if no file or parse error
        if not refs:
            refs = [
                {"name": "GPT-4o (ref)", "avg_seconds": 4.2},
                {"name": "Claude 3.5 Sonnet (ref)", "avg_seconds": 5.8},
                {"name": "Llama 3 70B (ref)", "avg_seconds": 8.5},
            ]

        # Legg til lokal modell
        refs.append({"name": "Local endpoint (this run)", "avg_seconds": round(avg_s, 2)})

        # Sorter etter tid
        refs.sort(key=lambda x: x.get("avg_seconds", 9999))
        return refs

    def export_scorecard(self):
        if not self._last_results:
            self.stats_label.configure(text="Kjør test først!")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", ".html")],
        )
        if not path:
            return
        html_doc = self.build_scorecard_html(self._last_results)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_doc)
        webbrowser.open_new_tab(path)

    def build_scorecard_html(self, results):
        avg_s = results.get("avg_seconds", 0.0)
        lb_data = self.load_benchmarks(avg_s)

        rows_html = []
        for i, row in enumerate(lb_data):
            name = row.get("name", "Unknown")
            score = row.get("avg_seconds", 0.0)
            bg = "#6c5ce733" if "Local endpoint" in name else "none"
            rows_html.append(
                f"<tr style='background:{bg}'><td>#{i+1} {name}</td><td>{score:.2f}s</td></tr>"
            )
        lb_rows = "".join(rows_html)

        return f"""
<html>
<head>
    <meta charset="UTF-8" />
    <title>Moth-Bench Performance Scorecard</title>
    <style>
        body {{
            background: #07070c;
            color: #e4e4ef;
            font-family: sans-serif;
            padding: 50px;
        }}
        .hero {{
            border: 1px solid #252540;
            background: linear-gradient(135deg, #6c5ce711, #e8439311);
            padding: 40px;
            border-radius: 24px;
            text-align: center;
        }}
        .grade {{
            font-size: 80px;
            color: #10b981;
            font-weight: 800;
        }}
        table {{
            width: 100%;
            margin-top: 20px;
            border-collapse: collapse;
        }}
        td, th {{
            padding: 15px;
            border-bottom: 1px solid #252540;
            text-align: left;
        }}
    </style>
</head>
<body>
    <div class="hero">
        <h1>🦋 MOTH-BENCH PERFORMANCE SCORECARD</h1>
        <div class="grade">{results.get("grade")}</div>
        <p>Avg latency: {avg_s:.2f}s | Success: {results.get("success")}/{results.get("total")}</p>
        <p style="font-size: 12px; opacity: 0.7;">
            Reference times are community-based and illustrative only. They are not official benchmarks
            for any provider. Your local endpoint is measured in this run.
        </p>
    </div>
    <table>
        <tr><th>Rank &amp; Model</th><th>Avg Response Time</th></tr>
        {lb_rows}
    </table>
</body>
</html>
        """.strip()

    # ---------------------
    # Benchmark run
    # ---------------------
    def start_thread(self):
        self.btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.progress_bar.set(0)
        self.cancel_evt.clear()
        threading.Thread(target=self.run_bench, daemon=True).start()

    def update_result(self, tag, result, color_tag):
        ranges = self.txt._textbox.tag_ranges(tag)
        if ranges:
            start, end = ranges[0], ranges[1]
            self.txt._textbox.delete(start, end)
            self.txt._textbox.insert(start, result, (color_tag, tag))

    def run_bench(self):
        url = self.url_entry.get().strip().rstrip("/") + "/chat/completions"
        tests = self.get_tests()
        test_tags = []

        # Parse max_tokens, med fallback
        try:
            max_tokens = int(self.max_tokens_entry.get().strip())
        except Exception:
            max_tokens = 512

        self.txt.insert(
            "end",
            "⚡ INITIALIZING MOTH-BENCH HARDCORE PROTOCOL...\n" + "-" * 65 + "\n",
        )

        for i, t in enumerate(tests):
            tag_id = f"ID_{i:02d}"
            test_tags.append(tag_id)
            self.txt.insert(
                "end",
                f"[{i+1:2d}/{len(tests)}] {t['c'].ljust(8)} | {t['n'].ljust(18)}... ",
            )
            start_idx = self.txt._textbox.index("end-1c")
            self.txt.insert("end", "PENDING", "pending")
            self.txt._textbox.tag_add(
                tag_id,
                start_idx,
                self.txt._textbox.index("end-1c"),
            )
            self.txt.insert("end", "\n")

        times = []
        success = 0

        system_prompt = self.system_prompt_box.get("1.0", "end").strip()

        for i, t in enumerate(tests):
            if self.cancel_evt.is_set():
                break

            self.after(
                0,
                lambda n=t["n"]: self.stats_label.configure(text=f"ACTIVE: {n}"),
            )
            self.after(0, self.update_result, test_tags[i], "RUNNING ...", "pending")

            try:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": t["q"]})

                start_t = time.perf_counter()
                r = self.session.post(
                    url,
                    json={
                        "messages": messages,
                        "max_tokens": max_tokens,
                    },
                    timeout=(5, 45),
                )
                elapsed = time.perf_counter() - start_t

                if r.status_code == 200:
                    res = f"✅ {elapsed:.2f}s"
                    c_tag = "ok"
                    times.append(elapsed)
                    success += 1
                else:
                    res = f"⚠️ E{r.status_code}"
                    c_tag = "fail"
            except Exception as e:
                res = f"❌ {type(e).__name__}"
                c_tag = "fail"

            self.after(0, self.update_result, test_tags[i], res, c_tag)
            prog = (i + 1) / len(tests)
            self.after(0, self.progress_bar.set, prog)
            self.after(
                0,
                lambda p=prog: self.prog_label.configure(
                    text=f"PROGRESS: {int(p * 100)}%"
                ),
            )

        if times:
            avg = sum(times) / len(times)

            if avg < 5:
                grade = "S"
            elif avg < 10:
                grade = "A"
            elif avg < 18:
                grade = "B"
            else:
                grade = "C"

            self._last_results = {
                "grade": grade,
                "avg_seconds": avg,
                "success": success,
                "total": len(tests),
            }
            self.after(
                0,
                lambda: self.txt.insert(
                    "end",
                    f"\nDONE: {grade} | AVG: {avg:.2f}s | SUCCESS: {success}/{len(tests)}\n",
                ),
            )
            self.after(0, self.export_scorecard)

        self.after(0, lambda: self.btn.configure(state="normal"))
        self.after(0, lambda: self.cancel_btn.configure(state="disabled"))


if __name__ == "__main__":
    app = MothBench()
    app.mainloop()