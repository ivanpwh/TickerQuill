"""Widget bersama. RetroButton: tombol berbasis Label, karena tk.Button di macOS mengabaikan warna latar/teks."""
import tkinter as tk

from theme import FONT_B, T


class RetroButton(tk.Label):
    """Tombol bergaya terminal yang tampil sama di Windows, macOS, dan Linux.

    API yang dipakai aplikasi sama dengan tk.Button: config(text=..., state=...), cget("state"), invoke().
    `selected` menandai tab aktif (warna aksen saat kursor keluar).
    """

    def __init__(self, parent, text, command=None):
        super().__init__(parent, text=text, font=FONT_B, bg=T.BG, fg=T.FG, disabledforeground=T.DIM, cursor="hand2",
                         padx=10, pady=3, takefocus=1, highlightthickness=1, highlightbackground=T.BG,
                         highlightcolor=T.AMBER)  # garis fokus hanya terlihat saat dipilih dengan Tab
        self.command = command
        self.selected = False
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<space>", lambda e: self.invoke())
        self.bind("<Return>", lambda e: self.invoke())

    def _enter(self, _e):
        if self["state"] != "disabled":
            self.config(bg=T.FG, fg=T.BG)  # T dibaca saat event: ikut tema yang aktif

    def _leave(self, _e):
        self.config(bg=T.BG, fg=T.AMBER if self.selected else T.FG)

    def _release(self, e):
        if 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():  # dilepas di luar tombol = batal
            self.invoke()

    def invoke(self):
        if self["state"] != "disabled" and self.command:
            return self.command()
        return None
