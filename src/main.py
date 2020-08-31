# -*- coding:utf-8 -*-
import logging
import ctypes
import multiprocessing, tkinter as tk, time, os, signal, pickle, sys, argparse

from tkinter.constants import *
from tkinter.messagebox import showerror, showwarning
from tkinter.filedialog import askopenfilename
from tkinter.scrolledtext import ScrolledText

from macro_script import MacroController
import mapscripts
from util import get_config, save_config
from keybind_setup_window import SetKeyMap
from platform_data_creator import PlatformDataCaptureWindow
from screen_processor import MapleScreenCapturer
# from macro_script_astar import MacroControllerAStar as MacroController


default_logger = logging.getLogger("main")
default_logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

fh = logging.FileHandler("logging.log")
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
default_logger.addHandler(fh)


APP_TITLE = "MSV Kanna Ver"
VERSION = 0.1


def destroy_child_widgets(parent):
    for child in parent.winfo_children():
        child.destroy()


def macro_loop(input_queue, output_queue):
    logger = logging.getLogger("macro_loop")
    logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler("logging.log", encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

    try:
        while True:
            if input_queue.empty():
                time.sleep(0.5)
                continue

            command = input_queue.get()
            logger.debug("received command {}".format(command))
            if command[0] == "start":
                logger.debug("starting MacroController...")
                keymap = command[1]
                platform_file_dir = command[2]
                if platform_file_dir.find('mapscripts/') != -1:
                    name = os.path.splitext(os.path.basename(platform_file_dir))[0]
                    macro = mapscripts.map_scripts[name](keymap, output_queue)
                else:
                    macro = MacroController(keymap, log_queue=output_queue)
                macro.load_and_process_platform_map(platform_file_dir)

                while True:
                    macro.loop()
                    if not input_queue.empty():
                        command = input_queue.get()
                        if command[0] == "stop":
                            macro.abort()
                            break
    except Exception:
        logger.exception("Exception during loop execution:")
        output_queue.put(["exception", "exception"])


class MainScreen(tk.Frame):
    def __init__(self, master):
        self.master = master
        destroy_child_widgets(self.master)
        tk.Frame.__init__(self, master)
        self.pack(expand=YES, fill=BOTH)

        self._menubar = tk.Menu()
        terrain_menu = tk.Menu(tearoff=False)
        terrain_menu.add_command(label="Create", command=lambda: PlatformDataCaptureWindow(self.master))
        terrain_menu.add_command(label="Edit Current", command=lambda: self._on_edit_terrain())
        self._menubar.add_cascade(label="Terrain", menu=terrain_menu)
        options_menu = tk.Menu(tearoff=False)
        options_menu.add_command(label="Set Keys", command=lambda: SetKeyMap(self.master))
        self.auto_solve_rune = tk.BooleanVar()
        self.auto_solve_rune.set(get_config().get('auto_solve_rune', True))
        options_menu.add_checkbutton(label="Auto Solve Rune", onvalue=True, offvalue=False,
                                     variable=self.auto_solve_rune, command=self._on_auto_solve_rune_check)
        self._menubar.add_cascade(label="Options", menu=options_menu)
        help_menu = tk.Menu(tearoff=False)
        self._menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label='About', command=self._popup_about)

        self.master.config(menu=self._menubar)

        self.platform_file_path = tk.StringVar()
        self.platform_file_name = tk.StringVar()

        self.keymap = None

        self.macro_pid = 0
        self.macro_process = None
        self.macro_process_out_queue = multiprocessing.Queue()
        self.macro_process_in_queue = multiprocessing.Queue()

        self.macro_pid_infotext = tk.StringVar()
        self.macro_pid_infotext.set("Not executed")

        self.log_text_area = ScrolledText(self, height=10, width=20)
        self.log_text_area.pack(side=BOTTOM, expand=YES, fill=BOTH)
        self.log_text_area.bind("<Key>", lambda e: "break")
        self.macro_info_frame = tk.Frame(self, borderwidth=1, relief=GROOVE)
        self.macro_info_frame.pack(side=BOTTOM, anchor=S, expand=YES, fill=BOTH)

        tk.Label(self.macro_info_frame, text="Bot process status:").grid(row=0, column=0)

        self.macro_process_label = tk.Label(self.macro_info_frame, textvariable=self.macro_pid_infotext, fg="red")
        self.macro_process_label.grid(row=0, column=1, sticky=N+S+E+W)
        self.macro_process_toggle_button = tk.Button(self.macro_info_frame, text="Run", command=self.toggle_macro_process)
        self.macro_process_toggle_button.grid(row=0, column=2, sticky=N+S+E+W)

        tk.Label(self.macro_info_frame, text="Terrain file:").grid(row=1, column=0, sticky=N+S+E+W)
        tk.Label(self.macro_info_frame, textvariable=self.platform_file_name).grid(row=1, column=1, sticky=N+S+E+W)
        self.platform_file_button = tk.Button(self.macro_info_frame, text="Open...", command=self.on_platform_file_select)
        self.platform_file_button.grid(row=1, column=2, sticky=N+S+E+W)
        self.internal_platform_button = tk.Button(self.macro_info_frame, text="Presets", command=self.on_internal_platform_select)
        self.internal_platform_button.grid(row=1, column=3, sticky=N+S+E+W)

        self.macro_start_button = tk.Button(self.macro_info_frame, text="Start botting", fg="green", command=self.start_macro)
        self.macro_start_button.grid(row=2, column=0, sticky=N+S+E+W)
        self.macro_end_button = tk.Button(self.macro_info_frame, text="Stop botting", fg="red", command=self.stop_macro, state=DISABLED)
        self.macro_end_button.grid(row=2, column=1, sticky=N + S + E + W)

        for x in range(5):
            self.macro_info_frame.grid_columnconfigure(x, weight=1)
        self.log("MS-Visionify Kanna Ver v" + str(VERSION))
        self.log('\n')

        last_opened_platform_file = get_config().get('platform_file')
        if last_opened_platform_file and os.path.isfile(last_opened_platform_file):
            self.set_platform_file(last_opened_platform_file)

        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(500, self.toggle_macro_process)
        self.after(1000, self.check_input_queue)

    def on_close(self):
        if self.macro_process:
            try:
                self.macro_process_out_queue.put("stop")
                os.kill(self.macro_pid, signal.SIGTERM)
            except Exception:
                pass

        get_config()['geometry'] = self.master.geometry()
        save_config()
        sys.exit(0)

    def check_input_queue(self):
        while not self.macro_process_in_queue.empty():
            output = self.macro_process_in_queue.get()
            if output[0] == "log":
                self.log("Process - "+str(output[1]))
            elif output[0] == "stopped":
                self.log("Bot process has ended.")
            elif output[0] == "exception":
                self.macro_end_button.configure(state=DISABLED)
                self.macro_start_button.configure(state=NORMAL)
                self.platform_file_button.configure(state=NORMAL)
                self.macro_process = None
                self.macro_pid = 0
                self.macro_process_toggle_button.configure(state=NORMAL)
                self.macro_pid_infotext.set("Not executed")
                self.macro_process_label.configure(fg="red")
                self.macro_process_toggle_button.configure(text="Running")
                self.log("Bot process terminated due to an error. Please check the log file.")

        self.after(1000, self.check_input_queue)

    def start_macro(self):
        if not self.macro_process:
            self.toggle_macro_process()
        keymap = get_config().get('keymap')
        if not keymap:
            showerror(APP_TITLE, "The key setting could not be read. Please reset the key.")
        else:
            if not self.platform_file_path.get():
                showwarning(APP_TITLE, "Please select a terrain file.")
            else:
                if not MapleScreenCapturer().ms_get_screen_hwnd():
                    showwarning(APP_TITLE, "MapleStory window not found")
                else:
                    cap = MapleScreenCapturer()
                    hwnd = cap.ms_get_screen_hwnd()
                    rect = cap.ms_get_screen_rect(hwnd)
                    self.log("MS hwnd", hwnd)
                    self.log("MS rect", rect)
                    self.log("Out Queue put:", self.platform_file_path.get())
                    if rect[0] < 0 or rect[1] < 0:
                        showwarning(APP_TITLE, "Failed to get Maple Window location.\nMove MapleStory window so"
                                               "that the top left corner of the window is within the screen.")
                    else:
                        cap.capture()
                        self.macro_process_out_queue.put(("start", keymap, self.platform_file_path.get()))
                        self.macro_start_button.configure(state=DISABLED)
                        self.macro_end_button.configure(state=NORMAL)
                        self.platform_file_button.configure(state=DISABLED)

    def stop_macro(self):
        self.macro_process_out_queue.put(("stop",))
        self.log("Bot stop request completed. Please wait for a while.")
        self.macro_end_button.configure(state=DISABLED)
        self.macro_start_button.configure(state=NORMAL)
        self.platform_file_button.configure(state=NORMAL)

    def log(self, *args):
        res_txt = []
        for arg in args:
            res_txt.append(str(arg))
        self.log_text_area.insert(END, " ".join(res_txt)+"\n")
        self.log_text_area.see(END)

    def toggle_macro_process(self):
        if not self.macro_process:
            self.macro_process_toggle_button.configure(state=DISABLED)
            self.macro_pid_infotext.set("Running..")
            self.macro_process_label.configure(fg="orange")
            self.log("Bot process starting...")
            self.macro_process_out_queue = multiprocessing.Queue()
            self.macro_process_in_queue = multiprocessing.Queue()
            p = multiprocessing.Process(target=macro_loop, args=(self.macro_process_out_queue, self.macro_process_in_queue))
            p.daemon = True

            self.macro_process = p
            p.start()
            self.macro_pid = p.pid
            self.log("Process creation complete (pid: %d)"%(self.macro_pid))
            self.macro_pid_infotext.set("Executed (%d)"%(self.macro_pid))
            self.macro_process_label.configure(fg="green")
            self.macro_process_toggle_button.configure(state=NORMAL)
            self.macro_process_toggle_button.configure(text="Stop")

        else:
            self.stop_macro()
            self.macro_process_toggle_button.configure(state=DISABLED)
            self.macro_pid_infotext.set("Stopping..")
            self.macro_process_label.configure(fg="orange")

            self.log("SIGTERM %d"%(self.macro_pid))
            os.kill(self.macro_pid, signal.SIGTERM)
            self.log("Process terminated")
            self.macro_process = None
            self.macro_pid = 0
            self.macro_process_toggle_button.configure(state=NORMAL)
            self.macro_pid_infotext.set("Not executed")
            self.macro_process_label.configure(fg="red")
            self.macro_process_toggle_button.configure(text="Run")

    def on_platform_file_select(self):
        platform_file_path = askopenfilename(initialdir=os.getcwd(), title="Terrain file selection", filetypes=(("terrain file (*.platform)", "*.platform"),))
        if platform_file_path and os.path.exists(platform_file_path):
            self.set_platform_file(platform_file_path)
            get_config()['platform_file'] = platform_file_path

    def on_internal_platform_select(self):
        menu = tk.Menu(self.master, tearoff=0)
        for i in mapscripts.map_scripts:
            menu.add_command(label=i, command=lambda: self._on_preset_platform_set(i))

        menu.post(self.internal_platform_button.winfo_rootx(), self.internal_platform_button.winfo_rooty() + self.internal_platform_button.winfo_height())

    def _on_preset_platform_set(self, name):
        path = 'mapscripts/' + name + '.platform'
        self.set_platform_file(path)
        get_config()['platform_file'] = path

    def set_platform_file(self, path):
        with open(path, "rb") as f:
            try:
                data = pickle.load(f)
                platforms = data["platforms"]
                # minimap_coords = data["minimap"]
                self.log("Terrain file loaded (platforms: %s)" % len(platforms.keys()))
            except:
                showerror(APP_TITLE, "File verification error\n file: %s\nFile verification failed. Please check if it is a broken file." % path)
            else:
                self.platform_file_path.set(path)
                self.platform_file_name.set(os.path.basename(path).split('.')[0])

    def _on_edit_terrain(self):
        if not self.platform_file_path.get():
            showerror(APP_TITLE, 'No terrain file opened')
        else:
            PlatformDataCaptureWindow(self.master, self.platform_file_path.get())

    def _on_auto_solve_rune_check(self):
        get_config()['auto_solve_rune'] = self.auto_solve_rune.get()

    def _popup_about(self):
        tk.messagebox.showinfo('About', '''\
Version: v%s
Source code: https://github.com/krrr/MSV-Kanna-Ver

Please be known that using this bot may get your account banned. By using this software,
you acknowledge that the developers are not liable for any damages caused to you or your account.
''' % (VERSION,))


if __name__ == "__main__":
    ctypes.windll.user32.SetProcessDPIAware()

    multiprocessing.freeze_support()
    parser = argparse.ArgumentParser(description="MS-Visionify, a bot to play MapleStory")
    parser.add_argument("-title", dest="title", help="change main window title to designated value")
    args = vars(parser.parse_args())
    root = tk.Tk()

    root.title(args["title"] if args["title"] else APP_TITLE)
    try:
        root.iconbitmap('appicon.ico')
    except tk.TclError:
        pass
    root.wm_minsize(400, 600)

    MainScreen(root)

    geo = get_config().get('geometry')
    if geo:
        root.geometry(geo)
    root.mainloop()
