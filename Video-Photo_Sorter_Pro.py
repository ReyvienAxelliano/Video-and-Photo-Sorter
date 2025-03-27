import os
import shutil
import subprocess
import sys
import logging
import cv2
from functools import partial
from PIL import Image, ImageTk
from tkinter import messagebox, simpledialog, filedialog  # <-- Perbaikan di sini
from tkinterdnd2 import TkinterDnD, DND_FILES
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from moviepy.video.io.VideoFileClip import VideoFileClip

# Konfigurasi dasar
if getattr(sys, 'frozen', False):
    # Jika dijalankan sebagai EXE (PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Jika dijalankan sebagai script Python
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

MAIN_DIR = BASE_DIR
TRASH_DIR = os.path.join(MAIN_DIR, "Sampah")
SUPPORTED_EXT = ('.mp4', '.avi', '.mkv', '.mov', '.flv', 
                '.wmv', '.png', '.jpg', '.jpeg', '.webp')

class MediaSorter:
    def __init__(self, root):
        self.root = root
        self.root.title("Video/Photo Sorter Pro")
        self.root.geometry("1200x800")
        self.style = ttk.Style(theme='flatly')
        
        # Inisialisasi direktori
        try:
            self.current_dir = MAIN_DIR
            if not os.path.exists(self.current_dir):
                os.makedirs(self.current_dir)
        except Exception as e:
            messagebox.showerror("Error", f"Gagal mengakses direktori:\n{str(e)}")
            sys.exit(1)
        self.create_trash_folder()
        
        # Setup UI
        self.create_widgets()
        self.setup_bindings()
        self.update_file_list()

    def create_trash_folder(self):
        """Membuat folder Sampah jika belum ada"""
        if not os.path.exists(TRASH_DIR):
            os.makedirs(TRASH_DIR)
            logging.basicConfig(level=logging.INFO)
            logging.info(f"Created trash directory: {TRASH_DIR}")

    def create_widgets(self):
        """Membangun antarmuka pengguna"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Panel Atas - Navigasi
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=X)
        
        self.path_label = ttk.Label(top_frame, text=f"Lokasi: {self.current_dir}", bootstyle=INFO)
        self.path_label.pack(side=LEFT, fill=X, expand=True)
        
        ttk.Button(top_frame, text="Segarkan", command=self.update_file_list, bootstyle=INFO).pack(side=RIGHT)
        ttk.Button(top_frame, text="Folder Utama", command=self.go_to_main_dir, bootstyle=INFO).pack(side=RIGHT, padx=5)

        # Panel Tengah - Konten Utama
        middle_frame = ttk.Frame(main_frame)
        middle_frame.pack(fill=BOTH, expand=True)

        # Panel Kiri - Daftar File
        left_panel = ttk.Frame(middle_frame, width=300)
        left_panel.pack(side=LEFT, fill=Y)

        self.search_entry = ttk.Entry(left_panel)
        self.search_entry.pack(fill=X, padx=5, pady=5)

        # Treeview untuk daftar file
        self.tree = ttk.Treeview(
            left_panel,
            show='tree',
            selectmode='extended',
            style="Custom.Treeview"
        )
        scrollbar = ttk.Scrollbar(left_panel, orient=VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Panel Kontrol
        control_frame = ttk.Frame(left_panel)
        control_frame.pack(fill=X, pady=5)
        
        actions = [
            ('Putar', self.play_media),
            ('Ganti Nama', self.rename_file),
            ('Hapus', self.delete_files),
            ('Pindahkan', lambda: self.move_to_folder()),  # Tanpa argumen folder_name
            ('Buat Folder', self.create_folder)
        ]
        for text, cmd in actions:
            ttk.Button(control_frame, text=text, command=cmd, bootstyle=INFO).pack(side=LEFT, padx=2)

        # Panel Preview Kanan
        self.preview_frame = ttk.Frame(middle_frame)
        self.preview_frame.pack(side=RIGHT, fill=BOTH, expand=True)

        # Panel Folder Cepat
        self.folder_btn_frame = ttk.Frame(main_frame)
        self.folder_btn_frame.pack(fill=X, pady=10)
        self.update_folder_buttons()

    def setup_bindings(self):
        """Mengatur event binding"""
        self.tree.bind("<<TreeviewSelect>>", self.show_preview)
        self.tree.bind("<Double-Button-1>", self.navigate_folder)
        self.root.bind("<Delete>", lambda e: self.delete_files())
        self.root.bind("1", lambda e: self.move_to_folder("Sampah"))
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind('<<Drop>>', self.handle_drop)
        self.search_entry.bind("<KeyRelease>", self.search_files)

    def update_folder_buttons(self):
        """Memperbarui tombol folder cepat"""
        for widget in self.folder_btn_frame.winfo_children():
            widget.destroy()
            
        folders = [f for f in os.listdir(MAIN_DIR) 
                 if os.path.isdir(os.path.join(MAIN_DIR, f)) and f != "Sampah"]
        
        for i, folder in enumerate(folders):
            hotkey = str(i+1) if i < 9 else None
            btn_text = f"{folder} ({i+1})" if hotkey else folder
            btn = ttk.Button(self.folder_btn_frame, text=btn_text,
                            command=partial(self.move_to_folder, folder),
                            bootstyle=INFO)
            btn.pack(side=LEFT, padx=2)
            if hotkey:
                self.root.bind(hotkey, lambda e, f=folder: self.move_to_folder(f))

    def update_file_list(self):
        """Memperbarui daftar file"""
        self.tree.delete(*self.tree.get_children())
        try:
            items = os.listdir(self.current_dir)
            for item in sorted(items):
                full_path = os.path.join(self.current_dir, item)
                if os.path.isdir(full_path):
                    self.tree.insert('', 'end', text=f"📁 {item}", tags=('folder',))
                elif item.lower().endswith(SUPPORTED_EXT):
                    self.tree.insert('', 'end', text=f"📄 {item}", tags=('file',))
        except Exception as e:
            messagebox.showerror("Error", f"Gagal memuat direktori:\n{str(e)}")

    def get_selected_files(self):
        """Mendapatkan daftar file terpilih"""
        return [self.tree.item(iid)['text'] for iid in self.tree.selection()]

    def show_preview(self, event):
        """Menampilkan preview file (hanya untuk file, bukan folder)"""
        for widget in self.preview_frame.winfo_children():
            widget.destroy()

        selected = self.get_selected_files()
        if not selected:
            return
            
        # Hanya tampilkan preview jika yang dipilih adalah file
        if not selected[0].startswith("📁 "):
            file_path = os.path.join(self.current_dir, selected[0][2:])
            self.create_thumbnail(file_path)

    def create_thumbnail(self, path):
        """Membuat thumbnail untuk file"""
        try:
            if path.lower().endswith(('.png', '.jpg', '.jpeg')):
                img = Image.open(path)
            else:
                cap = cv2.VideoCapture(path)
                ret, frame = cap.read()
                cap.release()
                if not ret:
                    return
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            
            img.thumbnail((400, 400))  # Ukuran preview yang lebih besar
            photo = ImageTk.PhotoImage(img)
            label = ttk.Label(self.preview_frame, image=photo)
            label.image = photo
            label.pack(padx=10, pady=10)
        except Exception as e:
            logging.error(f"Gagal membuat thumbnail: {str(e)}")

    def search_files(self, event=None):
        """Mencari file berdasarkan input di search bar"""
        query = self.search_entry.get().lower()
        self.tree.delete(*self.tree.get_children())
        
        try:
            items = os.listdir(self.current_dir)
            for item in items:
                full_path = os.path.join(self.current_dir, item)
                if query in item.lower():
                    if os.path.isdir(full_path):
                        self.tree.insert('', 'end', text=f"📁 {item}", tags=('folder',))
                    elif item.lower().endswith(SUPPORTED_EXT):
                        self.tree.insert('', 'end', text=f"📄 {item}", tags=('file',))
        except Exception as e:
            messagebox.showerror("Error", f"Gagal melakukan pencarian:\n{str(e)}")

    def play_media(self):
        """Memutar media terpilih"""
        for item in self.get_selected_files():
            if item.startswith("📁 "):
                continue
            file_path = os.path.join(self.current_dir, item[2:])
            try:
                if sys.platform == "win32":
                    os.startfile(file_path)
                else:
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.call([opener, file_path])
            except Exception as e:
                messagebox.showerror("Error", f"Gagal memutar file:\n{str(e)}")

    def delete_files(self):
        """Memindahkan file/folder ke folder Sampah"""
        for item in self.get_selected_files():
            src_name = item[2:]  # Hapus emoji dan spasi
            src = os.path.join(self.current_dir, src_name)
            dest = os.path.join(TRASH_DIR, src_name)
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dest)
                    shutil.rmtree(src)
                else:
                    shutil.move(src, dest)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menghapus:\n{str(e)}")
        self.update_file_list()

    def move_to_folder(self, folder_name=None):
        """Memindahkan file/folder ke folder tertentu"""
        if folder_name is None:
            # Jika folder_name tidak diberikan, buka dialog untuk memilih folder
            target_dir = filedialog.askdirectory(
                initialdir=MAIN_DIR,
                title="Pilih Folder Tujuan"
            )
            if not target_dir:  # Jika user membatalkan dialog
                return
        else:
            target_dir = os.path.join(MAIN_DIR, folder_name)
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        moved_items = []
        failed_items = []
        
        for item in self.get_selected_files():
            src_name = item[2:]  # Hapus emoji dan spasi
            src = os.path.join(self.current_dir, src_name)
            dest = os.path.join(target_dir, src_name)
            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dest)
                    shutil.rmtree(src)
                else:
                    shutil.move(src, dest)
                moved_items.append(src_name)
            except Exception as e:
                failed_items.append((src_name, str(e)))
        
        # Berikan feedback kepada pengguna
        if moved_items:
            messagebox.showinfo(
                "Berhasil",
                f"Berhasil memindahkan:\n{', '.join(moved_items)}"
            )
        if failed_items:
            error_messages = "\n".join([f"{item}: {error}" for item, error in failed_items])
            messagebox.showerror(
                "Gagal Memindahkan",
                f"Gagal memindahkan:\n{error_messages}"
            )
        
        self.update_file_list()

    def handle_drop(self, event):
        files = self.root.tk.splitlist(event.data)
        for path in files:
            try:
                if os.path.isfile(path):
                    dest = os.path.join(self.current_dir, os.path.basename(path))
                    shutil.copy(path, dest)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menambahkan file:\n{str(e)}")
        self.update_file_list()

    def navigate_folder(self, event):
        """Navigasi folder dengan double-click"""
        selected = self.get_selected_files()
        if not selected:
            return
        
        item = selected[0]
        if item.startswith("📁 "):
            folder_name = item[2:]
            new_path = os.path.join(self.current_dir, folder_name)
            
            try:
                if os.path.exists(new_path):
                    self.current_dir = new_path
                    self.path_label.config(text=f"Lokasi: {self.current_dir}")
                    self.update_file_list()
                    self.update_folder_buttons()
            except Exception as e:
                messagebox.showerror("Error", f"Gagal membuka folder:\n{str(e)}")

    def go_to_main_dir(self):
        """Kembali ke folder utama"""
        self.current_dir = MAIN_DIR
        self.path_label.config(text=f"Lokasi: {self.current_dir}")
        self.update_file_list()
        self.update_folder_buttons()

    def create_folder(self):
        """Membuat folder baru"""
        name = simpledialog.askstring("Buat Folder", "Nama folder:")
        if name:
            try:
                os.makedirs(os.path.join(self.current_dir, name))
                self.update_file_list()
            except Exception as e:
                messagebox.showerror("Error", f"Gagal membuat folder:\n{str(e)}")

    def rename_file(self):
        """Mengubah nama file/folder dengan mempertahankan ekstensi"""
        selected = self.get_selected_files()
        if len(selected) != 1:
            messagebox.showwarning("Peringatan", "Pilih satu item saja!")
            return
            
        old_full_name = selected[0][2:]  # Hapus emoji dan spasi
        old_name, old_ext = os.path.splitext(old_full_name)
        
        new_name = simpledialog.askstring("Ganti Nama", "Nama baru:", initialvalue=old_full_name)
        if new_name and new_name != old_full_name:
            # Pertahankan ekstensi jika tidak diubah
            if '.' not in new_name and old_ext:
                new_name += old_ext
                
            try:
                src = os.path.join(self.current_dir, old_full_name)
                dest = os.path.join(self.current_dir, new_name)
                os.rename(src, dest)
                self.update_file_list()
            except Exception as e:
                messagebox.showerror("Error", f"Gagal mengubah nama:\n{str(e)}")

if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = MediaSorter(root)
    root.mainloop()