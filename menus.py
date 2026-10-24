"""Menu bar bawaan Windows (tk.Menu). Satu tabel memuat label, perintah, teks shortcut, binding tombol, dan syarat aktif."""
import tkinter as tk

import theme
from system import IS_MAC, MOD, MOD_LABEL

LANG_LABELS = {"ID": "Bahasa Indonesia (ID)", "EN": "English (EN)"}
# Binding kelas Tk yang mengubah isi widget untuk shortcut menu: diganti agar shortcut tidak berefek ganda
CLASS_CLASH = {"<Control-o>": ("Text",)}  # Text: Ctrl+O = sisipkan baris baru (tidak ada padanannya untuk Cmd)



def plain(text):
    """'[ SALIN HASIL ]' -> 'Salin hasil': label tombol dipakai ulang sebagai label menu."""
    return text.strip("[] ").capitalize()


class MenuBar:
    def __init__(self, app, langs):
        self.app = app
        self.items = []  # (menu, index, fungsi label, fungsi syarat aktif atau None)
        self.bar = tk.Menu(app, tearoff=0)
        tr, a = app.tr, app

        m = self.cascade(self.bar, "m_file")
        self.add(m, lambda: plain(tr("open")) + "…", a.open_file, f"{MOD_LABEL}+O", (f"<{MOD}-o>", f"<{MOD}-O>"),
                 lambda: not a.busy())
        self.add(m, lambda: plain(a.copy_btn.cget("text")), a.copy, f"{MOD_LABEL}+Shift+C", (f"<{MOD}-Shift-C>",),
                 a.can_export)
        self.add(m, lambda: plain(a.save_btn.cget("text")) + "…", a.save, f"{MOD_LABEL}+S", (f"<{MOD}-s>", f"<{MOD}-S>"),
                 a.can_export)
        m.add_separator()
        self.add(m, lambda: tr("mi_exit"), a.destroy)

        m = self.cascade(self.bar, "m_view")
        self.add(m, lambda: tr("page_analysis").capitalize(), lambda: a.show_page("analysis"), f"{MOD_LABEL}+1",
                 (f"<{MOD}-Key-1>",))
        self.add(m, lambda: tr("page_history").capitalize(), lambda: a.show_page("history"), f"{MOD_LABEL}+2",
                 (f"<{MOD}-Key-2>",))
        self.add(m, lambda: tr("m_overview"), lambda: a.show_page("collection"), f"{MOD_LABEL}+3",
                 (f"<{MOD}-Key-3>",))
        m.add_separator()
        for pane, key in (("DASHBOARD", "tab_dash"), ("ANALISIS", "analysis_tab"), ("TRANSKRIP", "transcript_tab")):
            self.add(m, lambda k=key: tr(k).capitalize(), lambda p=pane: a.show_tab(p))
        m.add_separator()
        sub = self.cascade(m, "mi_theme")
        for name in theme.CHOICES:
            sub.add_radiobutton(label="", variable=a.theme_var, value=name, command=lambda n=name: a.menu_theme(n))
            self.items.append((sub, sub.index("end"), lambda n=name: tr("theme_" + n), None))
        sub = self.cascade(m, "mi_lang")
        for code in langs:
            sub.add_radiobutton(label=LANG_LABELS.get(code, code), variable=a.ui_var, value=code,
                                command=lambda c=code: a.set_lang(c))

        m = self.cascade(self.bar, "m_job")
        self.add(m, lambda: plain(tr("analyze")), a.start, "Enter", (), lambda: not a.busy())
        self.add(m, lambda: plain(a.pause_btn.cget("text")), a.toggle_pause, "",
                 (), lambda: a.pause_btn.cget("state") == "normal")
        self.add(m, lambda: plain(tr("cancel")), a.stop, "Esc", ("<Escape>",), a.busy)

        m = self.cascade(self.bar, "m_tools")
        self.add(m, lambda: tr("set_title") + "…", a.open_settings, f"{MOD_LABEL}+,", (f"<{MOD}-comma>",))
        self.add(m, lambda: plain(tr("set_pick")) + "…", a.pick_model)
        self.add(m, lambda: tr("mi_colab"), a.test_colab)

        m = self.cascade(self.bar, "m_help")
        self.add(m, lambda: tr("mi_guide"), a.open_guide)
        self.add(m, lambda: tr("mi_about"), a.show_about)

        app.config(menu=self.bar)
        if IS_MAC:  # menu aplikasi macOS: Preferences (Cmd+,) dan Quit (Cmd+Q) memanggil aplikasi ini
            app.createcommand("tk::mac::ShowPreferences", a.open_settings)
            app.createcommand("tk::mac::Quit", a.destroy)

    def cascade(self, parent, key):
        menu = tk.Menu(parent, tearoff=0)
        parent.add_cascade(label="", menu=menu, underline=0)
        self.items.append((parent, parent.index("end"), lambda: self.app.tr(key), None))
        return menu

    def add(self, menu, label, command, accel="", keys=(), enabled=None):
        menu.add_command(label="", command=command, accelerator=accel)
        index = menu.index("end")
        self.items.append((menu, index, label, enabled))
        for seq in keys:
            self.bind(seq, menu, index)

    def bind(self, seq, menu, index):
        def fire(e):
            if e.widget.winfo_toplevel() is not self.app:  # tombol di dialog lain bukan shortcut jendela utama
                return None
            self.refresh_state()
            menu.invoke(index)  # item nonaktif tidak menjalankan apa pun
            return "break"

        self.app.bind(seq, fire)
        for cls in CLASS_CLASH.get(seq, ()):
            self.app.bind_class(cls, seq, fire)

    def refresh_labels(self):
        for menu, index, label, _ in self.items:
            menu.entryconfig(index, label=label())

    def refresh_state(self):
        """Label dinamis (SALIN/SIMPAN per tab, JEDA/LANJUT) dan aktif/nonaktif mengikuti keadaan aplikasi."""
        for menu, index, label, enabled in self.items:
            menu.entryconfig(index, label=label())
            if enabled is not None:
                menu.entryconfig(index, state="normal" if enabled() else "disabled")
