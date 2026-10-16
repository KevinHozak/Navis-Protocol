import customtkinter as ctk
import re


class TacticalEditor(ctk.CTkTextbox):
    """
    High-fidelity, line-based Obsidian-style Markdown editor.
    Uses reverse-order injection to prevent index drift and syntax leaks.
    """

    def __init__(self, master, theme=None, render_emoji_cb=None, **kwargs):
        super().__init__(master, **kwargs)
        self.theme = theme or {"accent": "#1f538d", "text": "#f0f0f0"}
        self.render_emoji_cb = render_emoji_cb
        self._image_cache = {}

        inner_text = self._textbox

        # --- Configure High-Fidelity Tags ---
        inner_text.tag_config(
            "h1", font=("Segoe UI Emoji", 20, "bold"), foreground=self.theme["accent"]
        )
        inner_text.tag_config(
            "h2", font=("Segoe UI Emoji", 16, "bold"), foreground=self.theme["accent"]
        )
        inner_text.tag_config(
            "h3", font=("Segoe UI Emoji", 14, "bold"), foreground=self.theme["accent"]
        )
        inner_text.tag_config("bold", font=("Segoe UI Emoji", 13, "bold"))
        inner_text.tag_config("italic", font=("Segoe UI Emoji", 13, "italic"))
        inner_text.tag_config("syntax", elide=True, foreground="#444")
        inner_text.tag_config(
            "wikilink", foreground=self.theme["accent"], underline=True
        )
        inner_text.tag_config("list_marker", foreground="#666")
        inner_text.tag_config(
            "checkbox", foreground=self.theme["accent"], font=("Consolas", 13, "bold")
        )
        inner_text.tag_config(
            "checked_x", foreground="#ffffff", background=self.theme["accent"]
        )

        # Tag Priority: 'syntax' must be the absolute master of hiding
        for tag in [
            "h1",
            "h2",
            "h3",
            "bold",
            "italic",
            "wikilink",
            "list_marker",
            "checkbox",
            "checked_x",
            "syntax",
        ]:
            inner_text.tag_raise(tag)

        # --- Bindings ---
        self.bind("<KeyRelease>", self._on_key_release)
        self.bind("<ButtonRelease-1>", self._on_cursor_move)
        self.bind("<MouseWheel>", self._on_scroll)
        self.bind("<Key>", self._on_key_press)

    def _on_scroll(self, event):
        self.after(10, self.refresh_styling)

    def _on_key_press(self, event):
        if event.keysym in [
            "Up",
            "Down",
            "Left",
            "Right",
            "Next",
            "Prior",
            "Home",
            "End",
        ]:
            self.after(1, self.refresh_styling)

    def _on_key_release(self, event):
        if event.keysym in ["Return", "BackSpace", "Delete"]:
            self.refresh_styling()
        else:
            if hasattr(self, "_style_after_id"):
                self.after_cancel(self._style_after_id)
            self._style_after_id = self.after(50, self.refresh_styling)

    def _on_cursor_move(self, event):
        self.refresh_styling()

    def load_content(self, content):
        self.delete("1.0", "end")
        self.insert("1.0", content)
        self.refresh_styling()

    def refresh_styling(self):
        """Atomic line-based styling with drift-safe reverse injection."""
        inner_text = self._textbox

        try:
            start_line = int(inner_text.index("@0,0").split(".")[0])
            end_line = (
                int(inner_text.index(f"@0,{inner_text.winfo_height()}").split(".")[0])
                + 2
            )
            cursor_line = inner_text.index("insert").split(".")[0]
        except Exception:
            return

        # 1. Clean Sweep of Visible Range
        inner_text.tag_remove("syntax", f"{start_line}.0", f"{end_line}.end")
        for tag in [
            "h1",
            "h2",
            "h3",
            "bold",
            "italic",
            "wikilink",
            "list_marker",
            "checkbox",
            "checked_x",
        ]:
            inner_text.tag_remove(tag, f"{start_line}.0", f"{end_line}.end")

        for name in inner_text.image_names():
            idx = inner_text.index(name)
            if idx:
                l = int(idx.split(".")[0])
                if start_line <= l <= end_line:
                    inner_text.delete(name)

        # 2. Sequential Parser
        for i in range(start_line, end_line + 1):
            line_idx = str(i)
            line_content = inner_text.get(f"{line_idx}.0", f"{line_idx}.end")
            if not line_content:
                continue

            is_active = line_idx == cursor_line
            spans = []  # (tag, start, end)

            # -- Header Detection --
            h_match = re.match(r"^(#{1,3})\s+", line_content)
            if h_match:
                tag = f"h{len(h_match.group(1))}"
                if not is_active:
                    spans.append(("syntax", 0, len(h_match.group(0))))
                spans.append((tag, 0, len(line_content)))

            # -- Spans: Bold / Italic / Wikilink --
            for m in re.finditer(r"(\*\*)(.*?)(\*\*)", line_content):
                spans.append(("bold", m.start(2), m.end(2)))
                if not is_active:
                    spans.append(("syntax", m.start(1), m.end(1)))
                    spans.append(("syntax", m.start(3), m.end(3)))

            for m in re.finditer(r"(\*)([^\*\n]+)(\*)", line_content):
                if line_content.strip().startswith(m.group(0)):
                    continue
                spans.append(("italic", m.start(2), m.end(2)))
                if not is_active:
                    spans.append(("syntax", m.start(1), m.end(1)))
                    spans.append(("syntax", m.start(3), m.end(3)))

            for m in re.finditer(r"(\[\[)(.*?)(\]\])", line_content):
                spans.append(("wikilink", m.start(2), m.end(2)))
                if not is_active:
                    spans.append(("syntax", m.start(1), m.end(1)))
                    spans.append(("syntax", m.start(3), m.end(3)))

            # -- Lists & Checkboxes --
            list_match = re.search(r"^(\s*[-\*]\s+)(\[([ xX])\]\s+)?", line_content)
            if list_match:
                if not is_active:
                    spans.append(("syntax", list_match.start(1), list_match.end(1)))
                else:
                    spans.append(
                        ("list_marker", list_match.start(1), list_match.end(1))
                    )

                if list_match.group(2):
                    cb_s, cb_e = list_match.start(2), list_match.end(2)
                    spans.append(("checkbox", cb_s, cb_e))
                    if list_match.group(3).lower() == "x":
                        spans.append(("checked_x", cb_s + 1, cb_s + 2))

            # --- Atomic Application (Right-to-Left for Images, Tags safe) ---
            # 1. Apply Tags (Tags don't shift indices, so order doesn't matter much)
            for tag, start, end in spans:
                inner_text.tag_add(tag, f"{line_idx}.{start}", f"{line_idx}.{end}")

            # 2. Inject Emoji Images (REVERSED order to prevent drift)
            if not is_active and self.render_emoji_cb:
                emojis = list(re.finditer(r"[\U0001f000-\U0001fbff]", line_content))
                for m in reversed(emojis):
                    char = m.group(0)
                    offset = m.start()
                    if char not in self._image_cache:
                        self._image_cache[char] = self.render_emoji_cb(char)
                    if self._image_cache[char]:
                        idx = f"{line_idx}.{offset}"
                        inner_text.tag_add("syntax", idx, f"{idx} + 1 chars")
                        inner_text.image_create(
                            idx, image=self._image_cache[char], padx=2
                        )

            inner_text.tag_raise("syntax")
