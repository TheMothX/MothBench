"""
Moth-Bench - GUI benchmark client for /v1/chat/completions-compatible LLM endpoints.

Features:
- Runs a fixed battery of 43 moth-themed prompts (logic, math, code, reasoning)
- Measures latency per test and overall average
- Shows live progress in a CustomTkinter UI
- Results tab with expandable/collapsible Q&A per test
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

# ---------------------------------------------------------------------------
# Quality criteria for each of the 43 tests.
# "correct": keywords whose presence raises the score (+1 each).
# "wrong":   keywords whose presence lowers the score (-2 each).
# Base score is 5; clamped to [0, 10].
# ---------------------------------------------------------------------------
QUALITY_CRITERIA = {
    # Logic
    "Moth & Flame":     {"correct": ["never", "infinite", "asymptote", "not reach", "won't reach"], "wrong": ["will reach", "yes it will"]},
    "The Silk Lie":     {"correct": ["paradox", "impossible", "neither", "dust-moth", "dust moth"], "wrong": []},
    "Lunar Navigation": {"correct": ["spiral", "circle", "loop", "curved"], "wrong": ["straight line", "straight path"]},
    "Camouflage":       {"correct": ["natural selection", "evolution", "predator", "melanism", "survival of"], "wrong": []},
    "Moth Box":         {"correct": ["silk", "dust", "relabel", "mixed box", "must be"], "wrong": []},
    "Night Flight":     {"correct": ["no", "cannot", "not a moth", "diurnal"], "wrong": ["yes", "could be a moth"]},
    "Cocoon Math":      {"correct": ["10 days", "10 cocoon", "same time", "same rate"], "wrong": ["100 day", "1 day"]},
    "Attraction":       {"correct": ["transverse orientation", "transverse", "navigation", "moon", "evolutionary"], "wrong": []},
    "Moth Paradox":     {"correct": ["paradox", "self-referential", "liar", "neither true nor false", "undecidable"], "wrong": []},
    "Lamp Trap":        {"correct": ["blue is safe", "yes", "safe", "red is hot"], "wrong": ["blue is hot", "not safe"]},
    # Math
    "Wing Beats":       {"correct": ["8575", "8,575"], "wrong": []},
    "Silk Length":      {"correct": ["= 3", "is 3", "remainder 3", "answer is 3"], "wrong": []},
    "Population":       {"correct": ["32"], "wrong": ["16", "64"]},
    "Flight Path":      {"correct": ["e^x", "product rule", "chain rule", "cos(x", "-2x sin"], "wrong": []},
    "Antenna Prob":     {"correct": ["(12/13)^5", "12/13", "0.67", "0.66", "67%"], "wrong": []},
    "Moth Stats":       {"correct": ["mean", "standard deviation", "normal distribution", "bell curve"], "wrong": []},
    "Sphere Moth":      {"correct": ["113", "36π", "36pi"], "wrong": []},
    "Larva Growth":     {"correct": ["= 9", "x = 9", "x=9", "equals 9"], "wrong": ["= 8", "= 10"]},
    "Fibonacci Moth":   {"correct": ["55"], "wrong": ["34", "89"]},
    "Binary Wing":      {"correct": ["27100", "0x27100"], "wrong": []},
    # Code
    "Moth-Cache":       {"correct": ["lru", "ordereddict", "capacity", "evict"], "wrong": []},
    "Light Sync":       {"correct": ["mutex", "lock", "std::mutex", "lock_guard"], "wrong": []},
    "Moth-SQL":         {"correct": ["avg(", "group by", "forest_id", "having"], "wrong": []},
    "Wing Regex":       {"correct": ["moth-", "\\d", "[0-9]", "\\d{4}"], "wrong": []},
    "Moth-Sort":        {"correct": ["pivot", "partition", "quicksort", "quick sort", "o(n log"], "wrong": []},
    "Recursive Moth":   {"correct": ["def ", "return", "base case", "recursion"], "wrong": []},
    "Git Moth":         {"correct": ["branch", "new branch", "checkout", "merge"], "wrong": []},
    "Moth API":         {"correct": ["@app", "fastapi", "flying", "return", "json"], "wrong": []},
    "Search Moth":      {"correct": ["binary", "mid", "low", "high", "o(log"], "wrong": []},
    "Moth-Docker":      {"correct": ["from ", "run ", "cmd", "copy ", "python"], "wrong": []},
    # Trick
    "Noah's Moth":      {"correct": ["moses", "noah", "none", "zero", "trick", "not moses"], "wrong": []},
    "Wing Armor":       {"correct": ["survivorship", "survivor bias", "wald", "unwounded", "not hit"], "wrong": ["add armor where holes", "damaged area"]},
    "Silk Price":       {"correct": ["no missing", "false", "accounting", "25", "27"], "wrong": ["missing dollar"]},
    # Sense
    "Moth Theory":      {"correct": ["leaf", "where she left", "original", "false belief"], "wrong": ["log", "where anne put"]},
    "Gravity":          {"correct": ["same time", "simultaneously", "equal time", "vacuum", "galileo"], "wrong": ["pebble first", "heavier"]},
    "Compass":          {"correct": ["east"], "wrong": ["west", "south"]},
    "Energy":           {"correct": ["flight muscle", "thorax", "wing muscle"], "wrong": []},
    "Reaction":         {"correct": ["electric", "shock", "voltage", "electrocuted", "high voltage"], "wrong": []},
    "History":          {"correct": ["grace hopper", "harvard mark", "1947", "relay", "computer bug"], "wrong": []},
    # Stress (creative – check for relevance)
    "Moth Poetry":      {"correct": ["moth", "moon", "light", "flame", "night", "haiku"], "wrong": []},
    "No-Lie World":     {"correct": ["truth", "honest", "colony", "trust", "transparent"], "wrong": []},
    "Moth Future":      {"correct": ["both", "sides", "replace", "argument", "artificial"], "wrong": []},
    "Final Moth":       {"correct": ["entanglement", "quantum", "instantaneous", "non-local", "correlation"], "wrong": []},
}

# ---------------------------------------------------------------------------
# Category badge colours
# ---------------------------------------------------------------------------
CATEGORY_COLORS = {
    "Logic":  "#6c5ce7",
    "Math":   "#0984e3",
    "Code":   "#00b894",
    "Trick":  "#e17055",
    "Sense":  "#fdcb6e",
    "Stress": "#e84393",
}


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

        # ----------------------------------------------------------------
        # Sidebar
        # ----------------------------------------------------------------
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

        # Endpoint entry
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

        # ----------------------------------------------------------------
        # Main content area: TabView with Log + Results tabs
        # ----------------------------------------------------------------
        self.tabview = ctk.CTkTabview(
            self,
            border_width=2,
            border_color="#353b48",
            segmented_button_selected_color=self.secondary_color,
            segmented_button_selected_hover_color="#5849c4",
            segmented_button_unselected_hover_color="#353b48",
        )
        self.tabview.pack(side="right", fill="both", expand=True, padx=20, pady=20)

        self.tabview.add("Log")
        self.tabview.add("Results")
        self.tabview.set("Log")

        # Log tab: keep the original textbox behaviour unchanged
        self.txt = ctk.CTkTextbox(
            self.tabview.tab("Log"),
            font=("Consolas", 11),
            border_width=2,
            border_color="#353b48",
            wrap="none",
        )
        self.txt.pack(fill="both", expand=True)

        self.txt._textbox.tag_configure("ok", foreground="#55efc4")
        self.txt._textbox.tag_configure("fail", foreground="#ff7675")
        self.txt._textbox.tag_configure("pending", foreground="#fdcb6e")

        # Results tab: scrollable frame holding collapsible cards
        self._results_cards = []   # list of (header_frame, body_frame, toggle_btn) per card

        self._results_outer = ctk.CTkFrame(
            self.tabview.tab("Results"),
            fg_color="transparent",
        )
        self._results_outer.pack(fill="both", expand=True)

        # "Expand all / Collapse all" toolbar
        self._results_toolbar = ctk.CTkFrame(
            self._results_outer,
            fg_color="transparent",
            height=36,
        )
        self._results_toolbar.pack(fill="x", pady=(0, 4))

        self._expand_all_btn = ctk.CTkButton(
            self._results_toolbar,
            text="Expand All",
            width=110,
            height=28,
            fg_color="#353b48",
            hover_color="#444",
            font=("Helvetica", 11),
            command=self._expand_all,
        )
        self._expand_all_btn.pack(side="left", padx=(0, 6))

        self._collapse_all_btn = ctk.CTkButton(
            self._results_toolbar,
            text="Collapse All",
            width=110,
            height=28,
            fg_color="#353b48",
            hover_color="#444",
            font=("Helvetica", 11),
            command=self._collapse_all,
        )
        self._collapse_all_btn.pack(side="left")

        self._results_placeholder = ctk.CTkLabel(
            self._results_outer,
            text="Run a benchmark to see results here.",
            font=("Helvetica", 13),
            text_color="#555",
        )
        self._results_placeholder.pack(expand=True)

        self._results_scroll = None   # created on first results population

        # ----------------------------------------------------------------
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    # ----------------------------------------------------------------
    # Collapsible card helpers
    # ----------------------------------------------------------------
    def _make_q_color(self, score):
        """Return a hex colour for a quality score."""
        if score is None:
            return "#555555"
        if score >= 9:
            return "#10b981"
        if score >= 7:
            return "#6c5ce7"
        if score >= 5:
            return "#fdcb6e"
        if score >= 3:
            return "#e17055"
        return "#ff7675"

    def _build_results_tab(self, details):
        """Populate the Results tab with one collapsible card per test item."""
        # Destroy previous scroll frame if it exists
        if self._results_scroll is not None:
            self._results_scroll.destroy()
            self._results_scroll = None

        self._results_placeholder.pack_forget()
        self._results_cards.clear()

        self._results_scroll = ctk.CTkScrollableFrame(
            self._results_outer,
            fg_color="#0d0d1a",
            corner_radius=8,
            border_width=1,
            border_color="#252540",
        )
        self._results_scroll.pack(fill="both", expand=True)

        for item in details:
            self._add_result_card(self._results_scroll, item)

    def _add_result_card(self, parent, item):
        """Add a single collapsible Q&A card to *parent*."""
        cat = item.get("category", "")
        name = item.get("name", "")
        elapsed = item.get("elapsed")
        quality = item.get("quality")
        question = item.get("question", "")
        answer = item.get("answer", "")

        t_str = f"{elapsed:.2f}s" if elapsed is not None else "N/A"
        q_color = self._make_q_color(quality)
        q_str = f"Q:{quality}/10" if quality is not None else "Q:N/A"
        cat_color = CATEGORY_COLORS.get(cat, "#aaaaaa")

        # Outer card frame
        card = ctk.CTkFrame(
            parent,
            fg_color="#131320",
            corner_radius=8,
            border_width=1,
            border_color="#252540",
        )
        card.pack(fill="x", padx=6, pady=4)

        # ---- Header row (always visible) ----
        header = ctk.CTkFrame(card, fg_color="transparent", height=44)
        header.pack(fill="x", padx=8, pady=(6, 0))
        header.pack_propagate(False)

        # Category badge
        ctk.CTkLabel(
            header,
            text=f" {cat} ",
            font=("Helvetica", 10, "bold"),
            fg_color=cat_color,
            text_color="#07070c",
            corner_radius=4,
            width=52,
            height=20,
        ).pack(side="left", padx=(0, 8))

        # Test name
        ctk.CTkLabel(
            header,
            text=name,
            font=("Helvetica", 12, "bold"),
            text_color="#e4e4ef",
            anchor="w",
        ).pack(side="left")

        # Time label
        ctk.CTkLabel(
            header,
            text=f"  {t_str}",
            font=("Consolas", 11),
            text_color=self.accent_color,
        ).pack(side="left", padx=(8, 0))

        # Quality badge
        ctk.CTkLabel(
            header,
            text=f"  {q_str}",
            font=("Helvetica", 11, "bold"),
            text_color=q_color,
        ).pack(side="left", padx=(6, 0))

        # Toggle button (right-aligned)
        toggle_btn = ctk.CTkButton(
            header,
            text="+ Show",
            width=76,
            height=26,
            fg_color="#252540",
            hover_color="#353b48",
            font=("Helvetica", 11),
        )
        toggle_btn.pack(side="right", padx=(0, 4))

        # ---- Body (hidden by default) ----
        body = ctk.CTkFrame(card, fg_color="#0a0a15", corner_radius=6)
        # body is NOT packed yet — shown only when expanded

        # Question label
        q_frame = ctk.CTkFrame(body, fg_color="transparent")
        q_frame.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            q_frame,
            text="Q:",
            font=("Helvetica", 11, "bold"),
            text_color="#fdcb6e",
            width=20,
            anchor="nw",
        ).pack(side="left", anchor="nw", padx=(0, 6))

        q_text = ctk.CTkLabel(
            q_frame,
            text=question,
            font=("Helvetica", 11),
            text_color="#dfe6e9",
            anchor="w",
            justify="left",
            wraplength=680,
        )
        q_text.pack(side="left", fill="x", expand=True)

        # Separator
        ctk.CTkFrame(body, height=1, fg_color="#252540").pack(
            fill="x", padx=12, pady=4
        )

        # Answer textbox (scrollable, read-only)
        a_frame = ctk.CTkFrame(body, fg_color="transparent")
        a_frame.pack(fill="x", padx=12, pady=(4, 10))

        ctk.CTkLabel(
            a_frame,
            text="A:",
            font=("Helvetica", 11, "bold"),
            text_color="#55efc4",
            width=20,
            anchor="nw",
        ).pack(side="left", anchor="nw", padx=(0, 6))

        # Use a CTkTextbox so long answers can be scrolled
        a_box = ctk.CTkTextbox(
            a_frame,
            height=160,
            font=("Consolas", 11),
            fg_color="#0d0d1a",
            border_width=1,
            border_color="#252540",
            wrap="word",
            state="normal",
        )
        a_box.pack(side="left", fill="x", expand=True)
        a_box.insert("1.0", answer)
        a_box.configure(state="disabled")

        # Wire up the toggle button with a closure
        def make_toggle(btn, bd, card_ref):
            expanded = [False]

            def toggle():
                if expanded[0]:
                    bd.pack_forget()
                    btn.configure(text="+ Show")
                    expanded[0] = False
                else:
                    bd.pack(fill="x", padx=6, pady=(0, 8))
                    btn.configure(text="- Hide")
                    expanded[0] = True

            btn.configure(command=toggle)
            return expanded  # return ref so expand/collapse-all can read it

        expanded_ref = make_toggle(toggle_btn, body, card)
        self._results_cards.append((toggle_btn, body, expanded_ref))

    def _expand_all(self):
        for btn, body, expanded_ref in self._results_cards:
            if not expanded_ref[0]:
                body.pack(fill="x", padx=6, pady=(0, 8))
                btn.configure(text="- Hide")
                expanded_ref[0] = True

    def _collapse_all(self):
        for btn, body, expanded_ref in self._results_cards:
            if expanded_ref[0]:
                body.pack_forget()
                btn.configure(text="+ Show")
                expanded_ref[0] = False

    # ----------------------------------------------------------------
    # Tests
    # ----------------------------------------------------------------
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

    # ----------------------------------------------------------------
    # Control actions
    # ----------------------------------------------------------------
    def cancel_run(self):
        self.cancel_evt.set()
        self.stats_label.configure(text="Cancelling...")

    def copy_log(self):
        txt = self.txt.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(txt)
        self.stats_label.configure(text="Log copied")

    # ----------------------------------------------------------------
    # Scorecard / leaderboard
    # ----------------------------------------------------------------
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

        if not refs:
            refs = [
                {"name": "GPT-4o (ref)", "avg_seconds": 4.2},
                {"name": "Claude 3.5 Sonnet (ref)", "avg_seconds": 5.8},
                {"name": "Llama 3 70B (ref)", "avg_seconds": 8.5},
            ]

        refs.append({"name": "Local endpoint (this run)", "avg_seconds": round(avg_s, 2)})
        refs.sort(key=lambda x: x.get("avg_seconds", 9999))
        return refs

    def score_answer(self, name: str, answer: str) -> int:
        """Return a quality score 0-10 for an answer based on keyword criteria."""
        if not answer:
            return 0
        criteria = QUALITY_CRITERIA.get(name)
        if not criteria:
            return 5
        a = answer.lower()
        score = 5
        for kw in criteria.get("correct", []):
            if kw.lower() in a:
                score += 1
        for kw in criteria.get("wrong", []):
            if kw.lower() in a:
                score -= 2
        return max(0, min(10, score))

    def export_scorecard(self):
        if not self._last_results:
            self.stats_label.configure(text="Kjor test forst!")
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
        avg_quality = results.get("avg_quality", 0.0)
        lb_data = self.load_benchmarks(avg_s)

        def q_color(score):
            if score is None:
                return "#555"
            if score >= 9:
                return "#10b981"
            if score >= 7:
                return "#6c5ce7"
            if score >= 5:
                return "#fdcb6e"
            if score >= 3:
                return "#e17055"
            return "#ff7675"

        rows_html = []
        for i, row in enumerate(lb_data):
            name = row.get("name", "Unknown")
            score = row.get("avg_seconds", 0.0)
            bg = "#6c5ce733" if "Local endpoint" in name else "none"
            q_cell = f"<span style='color:{q_color(avg_quality)}'>{avg_quality}/10</span>" if "Local endpoint" in name else "—"
            rows_html.append(
                f"<tr style='background:{bg}'><td>#{i+1} {name}</td><td>{score:.2f}s</td><td>{q_cell}</td></tr>"
            )
        lb_rows = "".join(rows_html)

        details = results.get("details", [])
        detail_rows = []
        for item in details:
            t_str = f"{item['elapsed']:.2f}s" if item.get("elapsed") is not None else "N/A"
            qs = item.get("quality")
            q_badge = f'<span class="q-badge" style="background:{q_color(qs)}">Q: {qs}/10</span>' if qs is not None else ""
            q = html.escape(item.get("question", ""))
            a = html.escape(item.get("answer", "")).replace("\n", "<br>")
            cat = html.escape(item.get("category", ""))
            name = html.escape(item.get("name", ""))
            detail_rows.append(f"""
<details class="qa-block">
    <summary class="qa-summary">
        <span class="qa-meta">{cat} | {name} &nbsp;—&nbsp; <span class="qa-time">&#9201; {t_str}</span> &nbsp;{q_badge}</span>
    </summary>
    <div class="qa-body">
        <div class="qa-question"><strong>Q:</strong> {q}</div>
        <div class="qa-answer"><strong>A:</strong> {a}</div>
    </div>
</details>""")
        detail_html = "".join(detail_rows)

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
        h2 {{
            margin-top: 50px;
            color: #6c5ce7;
            border-bottom: 1px solid #252540;
            padding-bottom: 10px;
        }}
        .qa-block {{
            border: 1px solid #252540;
            border-radius: 10px;
            margin: 16px 0;
            background: #0d0d1a;
            overflow: hidden;
        }}
        .qa-block[open] {{
            border-color: #6c5ce7;
        }}
        .qa-summary {{
            display: flex;
            align-items: center;
            padding: 14px 20px;
            cursor: pointer;
            list-style: none;
            user-select: none;
        }}
        .qa-summary::-webkit-details-marker {{
            display: none;
        }}
        .qa-summary::before {{
            content: "\\25B6";
            font-size: 10px;
            color: #6c5ce7;
            margin-right: 10px;
            transition: transform 0.2s;
            flex-shrink: 0;
        }}
        .qa-block[open] > .qa-summary::before {{
            transform: rotate(90deg);
        }}
        .qa-summary:hover {{
            background: #14142a;
        }}
        .qa-meta {{
            font-size: 12px;
            color: #6c5ce7;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .qa-time {{
            color: #e84393;
        }}
        .qa-body {{
            padding: 0 20px 20px 40px;
            border-top: 1px solid #252540;
        }}
        .qa-question {{
            margin: 14px 0 10px 0;
            color: #fdcb6e;
        }}
        .qa-answer {{
            color: #55efc4;
            white-space: pre-wrap;
            line-height: 1.6;
        }}
        .q-badge {{
            display: inline-block;
            padding: 2px 9px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            color: #07070c;
        }}
    </style>
</head>
<body>
    <div class="hero">
        <h1>MOTH-BENCH PERFORMANCE SCORECARD</h1>
        <div class="grade">{results.get("grade")}</div>
        <p>Avg latency: {avg_s:.2f}s &nbsp;|&nbsp; Quality: <span style="color:{q_color(avg_quality)};font-weight:bold">{avg_quality}/10</span> &nbsp;|&nbsp; Success: {results.get("success")}/{results.get("total")}</p>
        <p style="font-size: 12px; opacity: 0.7;">
            Reference times are community-based and illustrative only. They are not official benchmarks
            for any provider. Your local endpoint is measured in this run.
        </p>
    </div>
    <table>
        <tr><th>Rank &amp; Model</th><th>Avg Response Time</th><th>Quality Score</th></tr>
        {lb_rows}
    </table>
    <h2>Detailed Questions and Answers</h2>
    {detail_html}
</body>
</html>
        """.strip()

    # ----------------------------------------------------------------
    # Benchmark run
    # ----------------------------------------------------------------
    def start_thread(self):
        self.btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.progress_bar.set(0)
        self.cancel_evt.clear()
        # Switch to Log tab so the user sees live output
        self.tabview.set("Log")
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

        try:
            max_tokens = int(self.max_tokens_entry.get().strip())
        except Exception:
            max_tokens = 512

        self.txt.insert(
            "end",
            "INITIALIZING MOTH-BENCH HARDCORE PROTOCOL...\n" + "-" * 65 + "\n",
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
        details = []

        system_prompt = self.system_prompt_box.get("1.0", "end").strip()

        for i, t in enumerate(tests):
            if self.cancel_evt.is_set():
                break

            self.after(
                0,
                lambda n=t["n"]: self.stats_label.configure(text=f"ACTIVE: {n}"),
            )
            self.after(0, self.update_result, test_tags[i], "RUNNING ...", "pending")

            answer = None
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
                    times.append(elapsed)
                    success += 1
                    try:
                        answer = r.json()["choices"][0]["message"]["content"]
                    except Exception:
                        answer = "(kunne ikke hente svar)"
                    quality = self.score_answer(t["n"], answer)
                    res = f"OK {elapsed:.2f}s  Q:{quality}/10"
                    c_tag = "ok"
                    details.append({
                        "category": t["c"],
                        "name": t["n"],
                        "question": t["q"],
                        "answer": answer,
                        "elapsed": elapsed,
                        "quality": quality,
                    })
                else:
                    res = f"E{r.status_code}"
                    c_tag = "fail"
                    details.append({
                        "category": t["c"],
                        "name": t["n"],
                        "question": t["q"],
                        "answer": f"FEIL: HTTP {r.status_code}",
                        "elapsed": None,
                        "quality": None,
                    })
            except Exception as e:
                res = f"ERR {type(e).__name__}"
                c_tag = "fail"
                details.append({
                    "category": t["c"],
                    "name": t["n"],
                    "question": t["q"],
                    "answer": f"FEIL: {type(e).__name__}",
                    "elapsed": None,
                    "quality": None,
                })

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

            q_scores = [d["quality"] for d in details if d.get("quality") is not None]
            avg_quality = round(sum(q_scores) / len(q_scores), 1) if q_scores else 0.0

            self._last_results = {
                "grade": grade,
                "avg_seconds": avg,
                "avg_quality": avg_quality,
                "success": success,
                "total": len(tests),
                "details": details,
            }
            self.after(
                0,
                lambda: self.txt.insert(
                    "end",
                    f"\nDONE: {grade} | AVG: {avg:.2f}s | QUALITY: {avg_quality:.1f}/10 | SUCCESS: {success}/{len(tests)}\n",
                ),
            )

            # Build the Results tab and switch to it
            self.after(0, lambda d=details: self._build_results_tab(d))
            self.after(100, lambda: self.tabview.set("Results"))

        self.after(0, lambda: self.btn.configure(state="normal"))
        self.after(0, lambda: self.cancel_btn.configure(state="disabled"))
        self.after(
            0,
            lambda: self.stats_label.configure(
                text=f"Done  {success}/{len(tests)} OK"
            ),
        )


if __name__ == "__main__":
    app = MothBench()
    app.mainloop()
