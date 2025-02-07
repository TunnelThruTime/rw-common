
from rich.console import Console
from rich.spinner import Spinner
import time
import os, sys, re, configparser, click
import rich, pretty_errors
import subprocess
from subprocess import Popen, PIPE
import urwid
import datetime
import signal
import keyboard
import select
from typing import Union
from modules.core import utils
from modules.vu_meter import audio_utils 
basic_config = """
[dirs]
recording_dir = 
lyrics_bin =
lilypond_dir = 
[submenu_config]
use_less = yes
[setlist]
static =
"""
main_config_path = utils.assure_config_files(None, 'rw-common', basic_config)

current_script_path = os.path.abspath(__file__)
git_root = os.path.dirname(current_script_path)
global config_file_path
config_file_path = os.path.join(git_root, 'lib', 'config.ini')
global config
config = configparser.ConfigParser()
config.read(os.path.abspath(config_file_path))
config.read(main_config_path)

def call_error_if_config_missing_values():
    """TODO: Docstring for call_error_if_config_missing_values.
    :returns: TODO

    """
    dire_sections = ['dirs', 'setlist']
    for section in config.sections():
        for option in config.options(section):
            value = config.get(section, option)
            if not value.strip():  # Check if the value is empty or only whitespace
                print(f"Section '{section}', Option '{option}' is empty.")
                if section in dire_sections:
                    print('configuration requisite for rw functionality ...')
                    sys.exit(1)


def verify_dirs_exist():
    for section in config.sections():
        if section == 'dirs':
            for option in config.options(section):
                dir_path = config.get(section, option)
                if not os.path.exists(dir_path):
                    response = input(f"The directory '{dir_path}' does not exist. Create it? (y/n): ")
                    if response.lower() == 'y':
                        os.makedirs(dir_path)
                    else:
                        print(f"Directory '{dir_path}' was not created.")

call_error_if_config_missing_values()
verify_dirs_exist()

global title, ordinal
menu_options = [
    ("Key", "Usage"),
    ("-----", "--------------------------------------------------"),
    ("Ss", "Skip Item/Next Item"),
    ("Qq", "Quit"),
    ("Yy", "Yes start recording"),
    ("Pp", "Print lyrics"),
    ("Ee", "Create/edit lyrics"),
    ("Tt", "Open a tracklisting player loop (plays with mpv)"),
    ("Ll", "Listen to previous recording"),
    ("Uu", "Update setlist menu"),
    ("Mm", "Manual page viewer"),
    ("Oo", "Open associated reaper project"),
    ("Vv", "View associated lilypond notation"),
    ("Ww", "Popup window"),
    ("Aa", "Alternate record function"),
]

update_setlist_menu = [
    ("Key", "Usage"),
    ("-----", "--------------------------------------------------"),
    ("Aa", "Append Song from text input"),
    ("Cc", "Choose Song from lyrics_bin"),
    ("Pp", "Print lyrics"),
    ("Ee", "Create/edit lyrics"),
    ("Oo", "Open associated reaper project"),
    ("Ww", "Show config settings"),
    ("Qq", "Quit"),
]

lilypond_menu = [
    ("Key", "Usage"),
    ("-----", "--------------------------------------------------"),
    ("Aa", "Append Song from text input"),
    ("Cc", "Choose Song from lyrics_bin"),
    # ("Pp", "Print lyrics"),
    ("Ee", "Create/edit lilypond file"),
    ("Oo", "Open associated reaper project"),
    ("Ww", "Show config settings"),
    ("Qq", "Quit"),
]


class RWizard():

    """ """

    def __init__(self, setlist=None):

        """  """
        self.rec_dest = config.get('dirs', 'recording_dir')
        self.lyrics_bin = config.get('dirs', 'lyrics_bin')
        if config.has_option('dirs', 'lilypond_dir'):
            self.lilypond_dir = config.get('dirs', 'lilypond_dir')
        if not setlist:
            values = str(config.get('setlist', 'static')).split(', ')
            self.setlist = [ str(x).strip() for x in values ]
        else:
            self.setlist = setlist
            assert isinstance(self.setlist, [list, tuple]), 'RWizard: setlist error: not a list or tuple'
        self.index = 0
        self.title = self.setlist[self.index]
        self.process = None
        self.text_box = urwid.ListBox(urwid.SimpleListWalker([]))
        self.console = Console()
        self.spinner = Spinner('dots', text="Recording...")
        self.recording_counter_update_function = False
        self.alarm_handle = None
        self.timer_text = ""
    def __iter__(self):
        return self

    def __next__(self):
        """ returns current value, and rindex
            while moving the self[value, rindex] up by
            one
        """
        # this function makes sense for the record functions
        # but in the functions that perpare the recording it does not
        #
        # the function when called will dump the current position out
        # while internally setting up the next position in the list
        if self.index < len(self.setlist):
            value = self.setlist[self.index]
            rindex = self.index
            self.index += 1
            return value, rindex
        else:
            raise StopIteration

    def refresh(self):
        """ refreshes init vars
        """
        self.title = self.setlist[self.index]

    def append_setlist(item):
        assert isinstance(item, list), 'TypeError: item is not list type'
        if len(item) > 1:
            self.setlist.extend(item)
        else:
            self.setlist.append(item)

    def get_microphone_levels(self):
       for level in audio_utils.get_microphone_level():
           yield level

    def update_text(self, loop=None, data=None):
        """
        this responds to the get_microphone_levels in fetching levels from
        ALSA 
        TODO: currently needs work in setup
        """
        mic_levels = self.get_microphone_levels()
        for level in mic_levels:
           line = f'Microphone Level: {level}'
           self.text_box.body.insert(0, urwid.Text(line))

    def signal_handler(self, signal, frame):
        print("Stopping recording...")
        sys.exit(0)

    # show_update_setlist_menu {{{ #
    def show_update_setlist_menu(self, footer_text=None):
        """TODO: Docstring for show_update_setlist_menu.

        :footer_text: TODO
        :returns: TODO

        """
        listbox_content = []
        header_title = self.setlist[self.index]
        header_text = f"Preparing session for: {header_title}"
        if not footer_text:
            footer_text = f"Clean: ' - ', Index:{self.index}"
        for option in update_setlist_menu:
            columns = urwid.Columns([urwid.Text(str(text)) for text in option], dividechars=2)
            listbox_content.append(urwid.AttrMap(columns, None, focus_map='reversed'))
    
    
        header = urwid.Text(header_text) if header_text else None
        banner = urwid.LineBox(header)
        tail_note = urwid.Text(footer_text) if footer_text else None
        tail = urwid.LineBox(tail_note)


        listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
        pile = urwid.Pile([(4, banner), listbox, (3, tail)])
        padding = urwid.Padding(pile, left=2, right=2)
        loop = urwid.MainLoop(padding, unhandled_input=self.setlist_menu_keymap)
        loop.run()
    # }}} show_update_setlist_menu #
    # append section of update menu {{{ #
    
    def append_text_editable_linebox(self):
        """
        Create and display a text editable linebox widget.
        The function appends the entered text to self.setlist after the user presses enter.

        Returns:
        None
        """
        edit_text = urwid.Edit()
        self.text_box.body.append(edit_text)
        
        def handle_input(key):
            if key == "enter":
                entered_text = edit_text.get_edit_text()
                self.setlist.append(entered_text)
                raise urwid.ExitMainLoop()
        header_widget = urwid.Text('Input song title: ')
        bundled_boxes = [header_widget, edit_text]
        container_widget = urwid.ListBox(urwid.SimpleListWalker(bundled_boxes))

        loop = urwid.MainLoop(container_widget, unhandled_input=handle_input)
        loop.run()
    # }}} append section of update menu #
    # show_update_setlist_menu keymap {{{ #
    def setlist_menu_keymap(self, key):
        """TODO: Docstring for setlist_menu_keymap.

        :key: TODO
        :returns: TODO

        """
        key = key.lower()
        if key == "a":
            self.append_text_editable_linebox()
        elif key == "c":
            dict_of_lyric_files = self.make_lyricfilelisting(return_type='dictionary_data')
            self.show_lyricfilelisting_display(dict_of_lyric_files)
        elif key == "e":
            pass
        elif key == "p":
            pass
        elif key == "o":
            pass
        elif key == "w":
            pass
        elif key == "q":
            self.return_to_main_menu()
    # }}} show_update_setlist_menu keymap #

    # show_update_setlist_menu keymap {{{ #
    def lilypond_menu_keymap(self, key):
        """TODO: Docstring for setlist_menu_keymap.

        :key: TODO
        :returns: TODO

        """
        key = key.lower()
        if key == "a":
            self.append_text_editable_linebox()
        elif key == "c":
            dict_of_lyric_files = self.make_lyricfilelisting(return_type='dictionary_data')
            self.show_lyricfilelisting_display(dict_of_lyric_files)
        elif key == "e":
            self.edit_setlist_item_file(self.title, ftype='ly')
        elif key == "p":
            pass
        elif key == "o":
            pass
        elif key == "w":
            pass
        elif key == "q":
            self.return_to_main_menu()
    # }}} show_update_setlist_menu keymap #
    # show_view_lilypond__menu {{{ #
    def show_view_lilypond_menu(self, footer_text=None):
        """ show the lilypond associated file menu

        :footer_text: TODO
        :returns: TODO

        """
        listbox_content = []
        header_title = self.setlist[self.index]
        header_text = f"Preparing session for: {header_title}"
        if not footer_text:
            footer_text = f"Clean: ' - ', Index:{self.index}"
        for option in lilypond_menu:
            columns = urwid.Columns([urwid.Text(str(text)) for text in option], dividechars=2)
            listbox_content.append(urwid.AttrMap(columns, None, focus_map='reversed'))
    
    
        header = urwid.Text(header_text) if header_text else None
        banner = urwid.LineBox(header)
        tail_note = urwid.Text(footer_text) if footer_text else None
        tail = urwid.LineBox(tail_note)


        listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
        pile = urwid.Pile([(4, banner), listbox, (3, tail)])
        padding = urwid.Padding(pile, left=2, right=2)
        loop = urwid.MainLoop(padding, unhandled_input=self.lilypond_menu_keymap)
        loop.run()
    # }}} show_update_setlist_menu #
    # append section of update menu {{{ #

    # show_main_menu {{{ #
    def show_main_menu(self, footer_text=None):
        # Code to display the main menu
        global pile, loop, header_title
        # if not setlist:
            # values = str(config.get('setlist', 'static')).split(', ')
            # setlist = [ str(x).strip() for x in values ] 
        listbox_content = []
        header_title = self.setlist[self.index]
        header_text = f"Preparing session for: {header_title}"
        if not footer_text:
            footer_text = f"Clean: ' - ', Index:{self.index}"
        for option in menu_options:
            columns = urwid.Columns([urwid.Text(str(text)) for text in option], dividechars=2)
            listbox_content.append(urwid.AttrMap(columns, None, focus_map='reversed'))
    
    
        header = urwid.Text(header_text) if header_text else None
        banner = urwid.LineBox(header)
        tail_note = urwid.Text(footer_text) if footer_text else None
        tail = urwid.LineBox(tail_note)


        listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
        pile = urwid.Pile([(4, banner), listbox, (3, tail)])
        padding = urwid.Padding(pile, left=2, right=2)
        loop = urwid.MainLoop(padding, unhandled_input=self.on_keypress)
        loop.run()
    
    # }}} show_main_menu #
    # main_menu on keypress function {{{ #
    
    def on_keypress(self, key):
        key = key.lower()
        if key in ['q', 'Q']:
            raise urwid.ExitMainLoop()
            # sys.exit(0)
        elif key in ['Y', 'y']:
            print("Start recording")


            urwid_timer(10)
            title, ordinal = next(iter(r))
            # r.title, r.index = title, ordinal
            self.make_demo(ordinal)
        elif key == 'p':
            print("Print lyrics")
            self.show_lyrics_screen()
        elif key == 'e':
            print("Create/edit lyrics")
            self.edit_setlist_item_file(self.title, ftype='md')


        elif key == 'l':
            print("Listen to previous recording")
        elif key == 'm':
            print("Manual page viewer")
        elif key == 'o':
            print("Open associated reaper project")
        elif key == 's':
            title, ordinal = next(iter(self))
            self.refresh()
            # self.title, self.index = title, ordinal
            self.show_main_menu()
        elif key == 't':
            print("Open a tracklisting player loop")
            list_of_tracks = self.make_tracklisting()
            self.show_tracklist_display(list_of_tracks)
        elif key == 'u':
            self.show_update_setlist_menu()
        elif key == 'w':
            self.add_linebox_to_main_menu_pile()
        elif key == 'v':
            self.show_view_lilypond_menu()
        elif key == 'a':
            urwid_timer(2)
            title, ordinal = next(iter(self)) 
            self.alternative_make_demo(ordinal)

# Here is a writeup on the usage for the first menu
#
# | key | usage                  | functionality  |
# | --- | ---                    | -------------- |
# | A   |                        |                |
# | B   |                        |                |
# | C   |                        |                |
# | D   |                        |                |
# | E   | Edit lyrics            | ✔              |
# | F   |                        |                |
# | G   |                        |                |
# | H   |                        |                |
# | I   |                        |                |
# | J   |                        |                |
# | K   |                        |                |
# | L   |                        |                |
# | M   |                        |                |
# | N   |                        |                |
# | O   | X                      |                |
# | P   | Print Lyrics           | ✔              |
# | Q   | Quit                   | ✔              |
# | R   |                        |                |
# | S   | Skip Item              | ✔              |
# | T   | Tracklistings          | ✔              |
# | U   | Update Setlist         | ✔              |
# | V   | View lilypond notation |                |
# | W   |                        |                |
# | X   |                        |                |
# | Y   | Record                 | ✔              |
    # }}} main_menu on keypress function #

    def return_to_main_menu(self, log_message=None):
        self.show_main_menu(footer_text=log_message)

    # ls process box {{{1 #

    def open_process_in_textbox(self, command):
        text_box = urwid.Text("")
        
        def update_text(loop=None, data=None):
            if self.process:
                lines = self.process.stdout.readlines()
                for line in lines:
                    line = line.decode().strip()
                    if line:
                        self.text_box.body.insert(0, urwid.Text(line))
        # def update_text():
            # if self.process:
                # line = self.process.stdout.readline().decode().strip()
                # if line:
                    # text = text_box.get_text()[0] + "\n" + line
                    # text_box.set_text(text)
        
        self.process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
        
        loop = urwid.MainLoop(text_box, unhandled_input=self.handle_input)
        urwid.set_alarm_in(0.1, update_text)  # Update text every 0.1 seconds
        loop.run()
    # 1}}} #

    def alternative_make_demo(self, v):
        """ adds linebox to main menu pile that working on 04:24
        """
        # make)demo essentials

        x = self.setlist[v]
        self.current_setlist_item_name = x
        # print(x)



        self.start_time = datetime.datetime.now()
        self.spinner = urwid.Text("Recording...")

        def update_text(loop=None, data=None):
            elapsed_time = datetime.datetime.now() - self.start_time
            hours, remainder = divmod(elapsed_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            timer_text = f"Time Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}"

            # spinner_text = self.spinner.set_text(f"{timer_text}        ")

            # Replace the existing text with the updated timer text
            if self.timer_text:
                self.text_box.body.pop(0)  # Remove the existing line
            self.text_box.body.insert(0, urwid.Text(timer_text))
            self.timer_text = timer_text
            
            self.alarm_handle = loop.set_alarm_in(1, update_text)  # Update text every 0.1 seconds

            



        directory_path = os.path.join(self.rec_dest, 
            f"recordings/demos/sessions/{datetime.datetime.now().strftime('%F')}/{x} - Takes Directory")
        os.makedirs(directory_path, exist_ok=True)

        proxy_file = os.path.join(directory_path, f"{x} {subprocess.run(['openssl', 'rand', '-hex', '5'], capture_output=True, text=True).stdout.strip()}.ogg")
        self.current_setlist_item_filepath = proxy_file
        assert len(proxy_file) > 0, 'proxy_file var not set'
        
        # self.process Popen rec seems to only work under specific conditions:
        # | condition   | result                                  |
        # |-------------+-----------------------------------------|
        # | shell=True  | long error message                      |
        # | shell=False | records audio with blank text displayed |
        # 
        #
        self.process = Popen(['rec', '-d', '-V4', proxy_file], shell=False, stdout=PIPE, stderr=PIPE)
        # self.process = subprocess.Popen(f'rec {proxy_file}', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        self.recording_counter_update_function = True
        linebox = urwid.LineBox(self.text_box)

        pile.contents.append((linebox, pile.options()))  # Append LineBox to Pile

        padding = urwid.Padding(pile, left=2, right=2)
        loop = urwid.MainLoop(padding, unhandled_input=self.handle_input)
        loop.set_alarm_in(0.1, update_text)  # Update text every 0.1 seconds
        loop.run()



    def show_link_maker_menu(self):
        """TODO: Docstring for show_link_maker_menu.
        :returns: TODO

        """
        # currently only called from alternative_make_demo function
        loop.draw_screen()
        options = [['Y: Create demo link', 'N: No', 'A: Replace all links', 'M: Replace main and session link']]
        screen = ScreenOptions(loop, menu_type='link_maker')
        screen.set_linkpage_metadata(self.current_setlist_item_filepath, self.current_setlist_item_name, self.rec_dest)
        screen.set_callback(self.return_to_main_menu)
        screen.display_screen(options)

    # add_linebox_to_main_menu_pile {{{ #
    def add_linebox_to_main_menu_pile(self, command='ls'):
        """ adds linebox to main menu pile that working on 04:24
        """
        # text_box = urwid.Text("")
    
        def update_text(loop, user_data=None):
            if self.process:
                line = self.process.stdout.readline().decode().strip()
                if line:
                    # text = self.text_box.get_text()[0] + "\n" + line
                    # text_box.set_text(text)
                    #
                    text = self.text_box.body
                    text.insert(0, urwid.Text(line))
    
        self.process = Popen(command, shell=True, stdout=PIPE, stderr=PIPE)
    
        # urwid.connect_signal(self.text_box, 'change', update_text)  # Call update_text when text box changes
    
        linebox = urwid.LineBox(self.text_box)
    
        pile.contents.append((linebox, pile.options()))  # Append LineBox to Pile
    
        padding = urwid.Padding(pile, left=2, right=2)
        loop = urwid.MainLoop(padding, unhandled_input=self.handle_input)
        loop.set_alarm_in(0.1, update_text)  # Update text every 0.1 seconds
        loop.run()
    # }}} add_linebox_to_main_menu_pile #

    def handle_input(self, key):
        if key in ['q', 'Q']:
            if self.process:
                self.process.terminate()

            # Stop the ongoing update loop
            if self.alarm_handle is not None:
                loop.remove_alarm(self.alarm_handle)
                self.alarm_handle = None
            # raise urwid.ExitMainLoop()
            self.recording_counter_update_function = False
            # loop.stop()
            # raise urwid.ExitMainLoop()
            r.show_link_maker_menu()
            r.return_to_main_menu(log_message=f"Alarm: {self.alarm_handle}, " + \
                    f"RCUF: {self.recording_counter_update_function}"

                    )

    # 1}}} #



    def lyrics_display_on_keypress(self, key):
        k = key.lower()
        if k == 'q':
            raise urwid.ExitMainLoop()
        elif k == 'r':
            self.return_to_main_menu()
        elif k == 'y':
            self.make_demo(self.index)
        elif key == 'a':
            vapor_timer(2)
            title, ordinal = next(iter(self)) 
            self.inline_printlyricscreen_make_demo(ordinal)


    def show_lyrics_screen(self):
        # loop = None
        self.refresh()
        lyrics_filename = os.path.join(self.lyrics_bin + f"{self.title}.md")
        if os.path.isfile(lyrics_filename): 
            with open(lyrics_filename, 'r') as file:
                text = file.read()
        else:
            text = "file not found ..."

        text_widget = urwid.Text(text)
        listbox = urwid.ListBox(urwid.SimpleListWalker([text_widget]))

        # Add a border, header, and footer
        header_text = urwid.Text(f"Lyrics Header: {self.title}\nFile: {lyrics_filename}")
        footer_text = urwid.Text("Q: Quit Application, R: Return to Main Menu, Y: Record, A: AltRecord")
        
        header = urwid.LineBox(header_text)
        footer = urwid.LineBox(footer_text)
        
        # pile = urwid.Pile([(4, header), listbox, (3, footer)])
        #
        # header.rows((3, 3))
        pile.contents[0] = (header, pile.options(height_type='pack', height_amount=3))  # Update header
        pile.contents[1] = (urwid.ListBox(urwid.SimpleListWalker([text_widget])), pile.options())  # Update listbox
        pile.contents[2] = (footer, pile.options(height_type='pack', height_amount=3))  # Update footer
        padding = urwid.Padding(pile, left=2, right=2)

        loop = urwid.MainLoop(padding, unhandled_input=self.lyrics_display_on_keypress)
        loop.run()
        # filler = urwid.Filler(listbox)
        # loop = urwid.MainLoop(filler)
        # loop.run()

    def inline_printlyricscreen_make_demo(self, v):
        """ adds linebox to print lyric screen
        """
        # make)demo essentials

        x = self.setlist[v]
        self.current_setlist_item_name = x
        # print(x)



        self.start_time = datetime.datetime.now()
        self.spinner = urwid.Text("Recording...")

        def update_text(loop=None, data=None):
            elapsed_time = datetime.datetime.now() - self.start_time
            hours, remainder = divmod(elapsed_time.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            timer_text = f"Time Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}"

            # spinner_text = self.spinner.set_text(f"{timer_text}        ")

            # Replace the existing text with the updated timer text
            if self.timer_text:
                self.text_box.body.pop(0)  # Remove the existing line
            self.text_box.body.insert(0, urwid.Text(timer_text))
            self.timer_text = timer_text
            
            self.alarm_handle = loop.set_alarm_in(1, update_text)  # Update text every 0.1 seconds

            



        directory_path = os.path.join(self.rec_dest, 
            f"recordings/demos/sessions/{datetime.datetime.now().strftime('%F')}/{x} - Takes Directory")
        os.makedirs(directory_path, exist_ok=True)

        proxy_file = os.path.join(directory_path, f"{x} {subprocess.run(['openssl', 'rand', '-hex', '5'], capture_output=True, text=True).stdout.strip()}.ogg")
        self.current_setlist_item_filepath = proxy_file
        assert len(proxy_file) > 0, 'proxy_file var not set'
        
        # self.process Popen rec seems to only work under specific conditions:
        # | condition   | result                                  |
        # |-------------+-----------------------------------------|
        # | shell=True  | long error message                      |
        # | shell=False | records audio with blank text displayed |
        # 
        #
        self.process = Popen(['rec', '-d', '-V4', proxy_file], shell=False, stdout=PIPE, stderr=PIPE)
        # self.process = subprocess.Popen(f'rec {proxy_file}', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        self.recording_counter_update_function = True
        linebox = urwid.LineBox(self.text_box)
        pile.contents.insert(len(pile.contents) - 1, (linebox, 
                                                      pile.options(height_type='given',
                                                                   height_amount=3)))
        # pile.contents.append((linebox, pile.options()))  # Append LineBox to Pile

        padding = urwid.Padding(pile, left=2, right=2)
        loop = urwid.MainLoop(padding, unhandled_input=self.handle_input)
        loop.set_alarm_in(0.1, update_text)  # Update text every 0.1 seconds
        loop.run()


    def make_lyricfilelisting(self, return_type: Union['list_data', 'dictionary_data']):
        """ Make the tracklistings for the show_tracklist_display menu

        :returns: 
            list if return_type == list_data, dict if return_type == dictionary_data

        """
        array_arch = [os.path.join(root, file) for root, dirs, files in os.walk(self.lyrics_bin) for file in files if file.endswith('.md')]
        if return_type == 'list_data':
            return array_arch
        elif return_type == 'dictionary_data':
            result = {os.path.basename(path): path for path in array_arch}
            return result
    def make_tracklisting(self):
        """ Make the tracklistings for the show_tracklist_display menu

        :returns: 
            list

        """
        directory = os.path.join(self.rec_dest, 'recordings', 'demos', 'sessions')
        array_arch = [os.path.join(root, file) for root, dirs, files in os.walk(directory) for file in files if file.endswith('.ogg')]
        return array_arch

    def exit_program_mpv(self, filepath):
        """TODO: Docstring for exit_program_mpv.

        :filepath: TODO
        :returns: TODO

        """
        # how do we make the exit_program_mpv append to the listbox in
        # our show_tracklist_dispaly
        selected_file = filepath
        os.system(f"mpv '{selected_file}'")

    def tracklist_on_keypress(self, key):
        k = key.lower()
        if k == 'q':
            raise urwid.ExitMainLoop()
        elif k == 'r':
            self.return_to_main_menu()


    def show_lyricfilelisting_display(self, lyriclistings):
        assert isinstance(lyriclistings, dict), 'Bad DataType: lyriclistings not dict'
        def on_select_change(button, choice):
            self.selected_track = choice
            self.setlist.append(self.selected_track)
            header_text.set_text(f"Setlist: {', '.join(self.setlist)}")  # Update header_text
            # response = urwid.Text(["You chose ", choice, ""])
            # done = urwid.Button("Ok")
            # urwid.connect_signal(done, 'click', self.exit_program_mpv)
            # loop.original_widget = urwid.Filler(urwid.Pile([response, urwid.AttrMap(done, None, focus_map="reversed")]))
        
        body = [urwid.Text("LyricListings:"), urwid.Divider()]
        # lyriclistings comes as a dictionary and needs to be parsed down to a list
        # of plain text headers
        plainlistings = [ os.path.splitext(x)[0] for x in lyriclistings.keys() ]
        for track in plainlistings:
            button = urwid.Button(track)
            urwid.connect_signal(button, 'click', on_select_change, track)
            body.append(urwid.AttrMap(button, None, focus_map="reversed"))
        
        # Define header and footer text widgets
        header_text = urwid.Text(f"Setlist: {', '.join(self.setlist)}")
        footer_text = urwid.Text("Q: Quit App | R: Return to Main Menu | Use arrow keys to select a track | Press Enter to confirm selection")
        header = urwid.LineBox(header_text)
        listbox = urwid.ListBox(urwid.SimpleFocusListWalker(body))
        footer = urwid.LineBox(footer_text)
        
        # Create a frame with header, listbox, and footer
        frame = urwid.Frame(listbox, header=header, footer=footer)


        loop = urwid.MainLoop(frame, unhandled_input=self.tracklist_on_keypress)
        loop.run()
        # main = urwid.MainLoop(listbox)
        # main.run()

    def show_tracklist_display(self, tracklistings):
        def on_select_change(button, choice):
            self.selected_track = choice
            self.exit_program_mpv(self.selected_track)
            # response = urwid.Text(["You chose ", choice, ""])
            # done = urwid.Button("Ok")
            # urwid.connect_signal(done, 'click', self.exit_program_mpv)
            # loop.original_widget = urwid.Filler(urwid.Pile([response, urwid.AttrMap(done, None, focus_map="reversed")]))
        
        body = [urwid.Text("Tracklist"), urwid.Divider()]
        for track in tracklistings:
            button = urwid.Button(track)
            urwid.connect_signal(button, 'click', on_select_change, track)
            body.append(urwid.AttrMap(button, None, focus_map="reversed"))
        
        # Define header and footer text widgets
        header_text = urwid.Text("Tracklist")
        footer_text = urwid.Text("Q: Quit App | R: Return to Main Menu | Use arrow keys to select a track | Press Enter to confirm selection")
        header = urwid.LineBox(header_text)
        listbox = urwid.ListBox(urwid.SimpleFocusListWalker(body))
        footer = urwid.LineBox(footer_text)
        
        # Create a frame with header, listbox, and footer
        frame = urwid.Frame(listbox, header=header, footer=footer)


        loop = urwid.MainLoop(frame, unhandled_input=self.tracklist_on_keypress)
        loop.run()
        # main = urwid.MainLoop(listbox)
        # main.run()


    # def show_tracklist_display(self, tracklistings):
        # body = [urwid.Text(track) for track in tracklistings]

        # # Define header and footer text widgets
        # header_text = urwid.Text("Tracklist")
        # footer_text = urwid.Text("Q: Quit App | R: Return to Main Menu | Use arrow keys to select a track | Press Enter to confirm selection")

        # # Create header, listbox, and footer widgets
        # header = urwid.LineBox(header_text)
        # listbox = urwid.ListBox(urwid.SimpleListWalker(body))
        # footer = urwid.LineBox(footer_text)

        # # Create a frame with header, listbox, and footer
        # frame = urwid.Frame(listbox, header=header, footer=footer)

        # def on_select_change(key):
            # position = listbox.get_focus()[1]  # Get the position of the selected track
            # self.selected_track = tracklistings[position]  # Update selected_track variable

        # # Attach the on_select_change function to on_change event for listbox to track selection changes
        # key = urwid.connect_signal(listbox, 'change', on_select_change)

        # loop = urwid.MainLoop(frame, unhandled_input=self.tracklist_on_keypress)
        # loop.run()
    def edit_setlist_item_file(self, track, ftype: Union['md', 'ly'] = 'md'):
        """ Opens Popen for vim or gives urwid window to create 
            file before opening
        track:
            str() <- current RWizard title
        """
        if ftype == 'md':
            txt_file = os.path.join(self.lyrics_bin, f"{track}.{ftype}")
        elif ftype == 'ly':
            txt_file = os.path.join(self.lilypond_dir, f"{track}.{ftype}")
        if os.path.exists(txt_file):
            os.system(f"vim '{txt_file}'")
            r.return_to_main_menu()
        else:
            options = [[f'Y: Create and edit {ftype} file', 'N: No']]
            screen = ScreenOptions(loop, menu_type='mdfilemake')
            screen.set_text_file(txt_file)
            screen.display_screen(options)


    def make_demo(self, v):
        """
        takes v where it is the slice of setlist array and starts subprocess
        after creating dirs.

        """
        # this function cannot loop like the old version of rwizard because
        # it isn't a zsh function...
        #
        # instead it will take the integar value from the

        
        x = self.setlist[v]
        # print(x)
        directory_path = os.path.join(self.rec_dest, 
            f"recordings/demos/sessions/{datetime.datetime.now().strftime('%F')}/{x} - Takes Directory")
        os.makedirs(directory_path, exist_ok=True)

        proxy_file = os.path.join(directory_path, f"{x} {subprocess.run(['openssl', 'rand', '-hex', '5'], capture_output=True, text=True).stdout.strip()}.ogg")
        # | processes               | changes | Success                   |
        # | run                     |         |                           |
        # | popen                   |         |                           |
        # | popen w/ signal and try |         |                           |
        # | w/ keyboard             |         | requires registery & sudo |
        # | w/ select               |         | ✔                         |
        # subprocess.run(['rec', proxy_file])
        # subprocess.Popen(['rec', proxy_file], stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)

        # signal.signal(signal.SIGINT, self.signal_handler)
        p = subprocess.Popen(['rec', proxy_file])


        try:
            while p.poll() is None:
                i, o, e = select.select([sys.stdin], [], [], 1)
                if i:
                    # If there is keyboard input, stop the recording process
                    userInput = sys.stdin.read(1)
                    if userInput.lower() == 'q':
                        p.terminate()
                        break
        except KeyboardInterrupt:
            pass
        # # Wait for a specific keypress before stopping recording
        # print("Press 'Q' to stop the recording...")
        # keyboard.wait('Q')

        # p.terminate()

        # try:
            # p.wait()
        # except KeyboardInterrupt:
            # print("Recording stopped by user")
            # p.kill()

        # recording is finished ... 
        # above are lines that have been commented out in the process of elimination

        # Usage after the Popen process ends
        loop.draw_screen()
        options = [['Y: Create demo link', 'N: No', 'A: Replace all links', 'M: Replace main and session link']]
        screen = ScreenOptions(loop, menu_type='link_maker')
        screen.set_linkpage_metadata(proxy_file, x, self.rec_dest)
        screen.set_callback(self.return_to_main_menu)
        screen.display_screen(options)

        
# beginning of classes functions definde for modifying the urwid loop
#

class ScreenOptions:
    def __init__(self, urwid_loop, menu_type: Union['link_maker', 'basic', 'mdfilemake']):
        self.urwid_loop = urwid_loop
        self.menu_type = menu_type

    def set_linkpage_metadata(self, proxy_file, x, rec_dest):
        # breakpoint()
        self.proxy_file = proxy_file
        self.x = x
        self.rec_dest = rec_dest
    def set_text_file(self, textfile):
        self.textfile = textfile

    def set_callback(self, callback):
        self.return_to_main = callback

    def display_screen(self, options):
        listbox_content = []
        for option in options:
            columns = urwid.Columns([urwid.Text(str(text)) for text in option], dividechars=2)
            listbox_content.append(urwid.AttrMap(columns, None, focus_map='reversed'))
        
        listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
        
        # Create the pile with the banner and listbox
        header = urwid.Text("Menu Options")
        banner = urwid.Filler(header)
        pile = urwid.Pile([(2, banner), listbox])
        
        # Create padding and run the new screen
        padding = urwid.Padding(pile, left=4, right=4)
        if self.menu_type == 'basic':
            new_loop = urwid.MainLoop(padding, unhandled_input=self.on_keypress_base)
        elif self.menu_type == 'mdfilemake':
            new_loop = urwid.MainLoop(padding, unhandled_input=self.on_keypress_mdfile_make)
        elif self.menu_type == 'link_maker':
            new_loop = urwid.MainLoop(padding, unhandled_input=self.on_keypress_link_menu)
        new_loop.run()

    def on_keypress_base(self, key):
        if key in ['q', 'Q']:
            raise urwid.ExitMainLoop()
    def on_keypress_mdfile_make(self, key):
        k = key.lower()
        if k in 'y':
            if self.textfile:
                with open(self.textfile, 'w') as x:
                    pass
                
            else:
                pass
            if os.path.exists(self.textfile):
                os.system(f"vim '{self.textfile}'")
            r.return_to_main_menu()
        elif k in 'n':
            r.return_to_main_menu()

    def on_keypress_link_menu(self, key):
        rest = key.lower()

        if rest == 'y':
            print("Entered Y - Creating/Updating link ...")
            ln_cmd = f"ln -svf '{self.proxy_file}' '{self.rec_dest}/recordings/demos/sessions/{datetime.datetime.now().strftime('%F')}/{self.x}.ogg'"
            os.system(ln_cmd)
            loop.draw_screen()
        elif rest == 'a':
            print("Entered A - Creating/Updating link ...")
            ln_cmd_1 = f"ln -svf '{self.proxy_file}' '{self.rec_dest}/recordings/demos/sessions/{datetime.datetime.now().strftime('%F')}/{self.x}.ogg'"
            ln_cmd_2 = f"ln -svf '{self.proxy_file}' '{self.rec_dest}/recordings/demos/{self.x}.ogg'"
            ln_cmd_3 = f"ln -svf '{self.proxy_file}' '{self.rec_dest}/demos/{self.x}.ogg'"
            os.system(ln_cmd_1)
            os.system(ln_cmd_2)
            os.system(ln_cmd_3)
            loop.draw_screen()
        elif rest == 'm':
            print("Entered M - Creating/Updating link ...")
            ln_cmd_1 = f"ln -svf '{self.proxy_file}' '{self.rec_dest}/recordings/demos/sessions/{datetime.datetime.now().strftime('%F')}/{self.x}.ogg'"
            ln_cmd_2 = f"ln -svf '{self.proxy_file}' '{self.rec_dest}/recordings/demos/{self.x}.ogg'"
            os.system(ln_cmd_1)
            os.system(ln_cmd_2)
            loop.draw_screen()
        elif rest == 'n':
            print("Entered N - Returning to the main menu")
            self.return_to_main()
        elif rest == 'q':
            raise urwid.ExitMainLoop()






# beginning the main block of click, urwid code logic
#
#
r = RWizard()
# calling the wizard
# because it contains an iterator that can cycle only if its instanciazed outside of main loops
@click.group()
def cli():
    pass




def countdown_timer(seconds):
    for i in range(seconds, -1, -1):
        print(i, end=' ', flush=True)
        time.sleep(1)

# def urwid_timer(seconds):
    # for i in range(seconds, -1, -1):
        # pile.contents[0] = (urwid.Text(str(i)), pile.options())
        # loop.draw_screen()
        # time.sleep(1)

def vapor_timer(seconds, style_of_countdown: Union['top', 'tail'] = 'origin'):
    for i in range(seconds, -1, -1):
        header_text = f"Preparing session for: {header_title} - Countdown: {i}"
        new_header = urwid.Text(header_text, align='center')


        if style_of_countdown == 'top':
            pass
        elif style_of_countdown == 'tail':
            pass
        elif style_of_countdown == 'origin':
            pile.contents[0] = (urwid.Filler(urwid.Text(header_text, align='center')), 
                                pile.options(height_type='pack', 
                                             height_amount=3))
        loop.draw_screen()
        time.sleep(1)

# def vapor_timer(seconds):
    # for i in range(seconds, -1, -1):
        # header_text = f"Preparing session for: {header_title} - Countdown: {i}"
        # new_header = urwid.Text(header_text, align='center')


        # pile.contents[0] = (urwid.Filler(urwid.Text(header_text, align='center')), pile.options())
        # loop.draw_screen()
        # time.sleep(1)
def urwid_timer(seconds):
    for i in range(seconds, -1, -1):
        header_text = f"Preparing session for: {header_title} - Countdown: {i}"


        # size = urwid.Text.pack((loop.screen.get_cols_rows()[0],), focus=False)
        # size = urwid.Text.pack((loop.screen.get_cols_rows()[0],), focus=False)
        new_header = urwid.Text(header_text, align='center')
        pile.contents[0] = (urwid.Filler(new_header), pile.options())
        loop.draw_screen()
        time.sleep(1)

def update_countdown(seconds):
    global countdown
    for i in range(seconds, -1, -1):
        countdown.set_text(str(i))
        loop.draw_screen()
        time.sleep(1)

def on_keypress(key):
    key = key.lower()
    if key in ['q', 'Q']:
        raise urwid.ExitMainLoop()
        sys.exit(1)
    elif key in ['Y', 'y']:
        print("Start recording")


        urwid_timer(10)
        title, ordinal = next(iter(r))
        # r.title, r.index = title, ordinal
        r.make_demo(ordinal)
    elif key == 'p':
        print("Print lyrics")
        r.show_lyrics_screen()
    elif key == 'e':
        print("Create/edit lyrics")
        r.edit_setlist_item_file(r.title)


    elif key == 't':
        print("Open a tracklisting player loop")
        list_of_tracks = r.make_tracklisting()
        r.show_tracklist_display(list_of_tracks)
    elif key == 'l':
        print("Listen to previous recording")
    elif key == 'm':
        print("Manual page viewer")
    elif key == 'o':
        print("Open associated reaper project")
    elif key == 's':
        title, ordinal = next(iter(r)) 
        # r.title, r.index = title, ordinal
        r.show_main_menu()
    elif key == 'w':
        r.add_linebox_to_main_menu_pile()
    elif key == 'a':
        urwid_timer(2)
        title, ordinal = next(iter(r)) 
        r.alternative_make_demo(ordinal)

# Here is a writeup on the usage for the first menu
#
# | key | usage          | functionality  |
# | --- | ---            | -------------- |
# | A   |                |                |
# | B   |                |                |
# | C   |                |                |
# | D   |                |                |
# | E   | Edit lyrics    | ✔              |
# | F   |                |                |
# | G   |                |                |
# | H   |                |                |
# | I   |                |                |
# | J   |                |                |
# | K   |                |                |
# | L   |                |                |
# | M   |                |                |
# | N   |                |                |
# | O   | X              |                |
# | P   | Print Lyrics   | ✔              |
# | Q   | Quit           | ✔              |
# | R   |                |                |
# | S   | Skip Item      | ✔              |
# | T   | Tracklistings  | ✔              |
# | U   | Update Setlist |                |
# | V   |                |                |
# | W   |                |                |
# | X   |                |                |
# | Y   | Record         | ✔              |


@cli.command()
@click.argument('setlist', nargs=-1, required=False)
def start(setlist):
    """
    main menu
    """
    # breakpoint()
    global pile, loop, header_title
    if not setlist:
        values = str(config.get('setlist', 'static')).split(', ')
        setlist = [ str(x).strip() for x in values ] 
    r.show_main_menu()
    # listbox_content = []
    # header_title = setlist[0] if setlist else None 
    # header_text = f"Preparing session for: {header_title}"
    # for option in menu_options:
        # columns = urwid.Columns([urwid.Text(str(text)) for text in option], dividechars=2)
        # listbox_content.append(urwid.AttrMap(columns, None, focus_map='reversed'))
    

    # header = urwid.Text(header_text) if header_text else None
    # banner = urwid.LineBox(header)
    # listbox = urwid.ListBox(urwid.SimpleListWalker(listbox_content))
    # pile = urwid.Pile([(4, banner), listbox])
    # padding = urwid.Padding(pile, left=2, right=2)
    # loop = urwid.MainLoop(padding, unhandled_input=on_keypress)
    # loop.run()

@cli.command()
def defunct_menu():
    """ in start
    """
    
    pile_content = []
    for option in menu_options:
        columns = urwid.Columns([urwid.Text(str(text)) for text in option], dividechars=2)
        pile_content.append(urwid.AttrMap(columns, None, focus_map='reversed'))

    pile = urwid.Pile(pile_content)
    loop = urwid.MainLoop(pile, unhandled_input=on_keypress)
    loop.run()

@cli.command()
def frame_widget():
    """ frame widget
    

    """
    

    header = urwid.Text("Countdown: ")
    countdown = urwid.Text("")

    frame = urwid.Frame(body=urwid.Filler(urwid.Text("Main content")), header=header)
    loop = urwid.MainLoop(frame)

    
    # Update the header widget contents directly
    header_widget = frame.header
    header_widget.contents.clear()
    header_widget.contents.append((header, frame.options()))
    header_widget.contents.append((countdown, frame.options()))
    
    # header_widget = frame.header
    # header_widget.base_widget = urwid.Columns([(10, header), countdown])
    loop.widget = frame



@cli.command()
@click.argument('args', nargs=-1)
def csv(args):
    """ make csv from setlist1 shell var
    :returns: TODO

    """
    print(type(args))
    print(', '.join(str(i) for i in args))
 


@cli.command()
def csvm():
    """ make csv from setlist1 shell var
    :returns: TODO

    """
 

    # Execute Zsh command to convert Zsh array into CSV
    process = subprocess.Popen(["zsh", "-c", "echo $setlist1[@] | tr ' ' ',' > /dev/tty "], stdout=subprocess.PIPE)
    output, _ = process.communicate()

    csv_values = output.decode('utf-8').strip()
    print(csv_values)   





if __name__ == "__main__":
    cli()





