# By ubuntu@allefant.com October 2011. Do with it what you want.
#
# Ubuntu Oneiric with Nautilus 3 was a very sad day for me - any means
# to modify my emblems were gone.
#
# This script is a bit of a stop-gap measure - it adds a menu entry with
# the same functionality as the removed side pane from the old Nautilus.
#
# Drop this file into /usr/share/nautilus-python/extensions/ and
# Nautilus should now have that extra menu item in the context menu of
# any file or folder.
#
# If someone knows any of the following:
#
# 1) How to retrieve the list of all available emblems from Nautilus.
# 2) How to retrieve the icon picture for an emblem from Nautilus.
# 3) How to add a custom picture to a Nautilus menu item.
# 4) How to set/clear emblems with the Nautilus API instead of GVFS.
#
# Please mail to ubuntu@allefant.com.
#

import gi
try:
    gi.require_version('Gtk', '3.0')
    gi.require_version('Nautilus', '3.0')
except Exception as e:
    print(e)
    exit(-1)
import os
import subprocess
import shlex
from threading import Thread
from urllib import unquote_plus, quote_plus
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Nautilus as FileManager

APP = '$APP$'
VERSION = '$VERSION$'
_ = str

free_desktop_emblems = [
    "emblem-default",
    "emblem-documents",
    "emblem-downloads",
    "emblem-favorite",
    "emblem-important",
    "emblem-mail",
    "emblem-photos",
    "emblem-readonly",
    "emblem-shared",
    "emblem-symbolic-link",
    "emblem-synchronized",
    "emblem-system",
    "emblem-unreadable"]

USER_EMBLEMS_PATH = "~/.icons/hicolor/48x48/emblems"


class IdleObject(GObject.GObject):
    """
    Override GObject.GObject to always emit signals in the main thread
    by emmitting on an idle handler
    """
    def __init__(self):
        GObject.GObject.__init__(self)

    def emit(self, *args):
        GLib.idle_add(GObject.GObject.emit, self, *args)


class DoItInBackground(IdleObject, Thread):
    __gsignals__ = {
        'started': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (int,)),
        'ended': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (bool,)),
        'start_one': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (str,)),
        'end_one': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, (float,)),
    }

    def __init__(self, files, emblem=None):
        IdleObject.__init__(self)
        Thread.__init__(self)
        self.elements = files
        self.emblem = emblem
        self.stopit = False
        self.ok = False
        self.daemon = True

    def stop(self, *args):
        self.stopit = True

    def emblemize(self, file_in):
        if self.emblem is None:  # Remove emblem
            remove_emblem(file_in)
        else:
            add_emblem(file_in, self.emblem)

    def run(self):
        total = len(self.elements)
        self.emit('started', total)
        try:
            self.ok = True
            for element in self.elements:
                if self.stopit is True:
                    self.ok = False
                    break
                self.emit('start_one', element)
                self.emblemize(element)
                self.emit('end_one', 1)
        except Exception as e:
            self.ok = False
        self.emit('ended', self.ok)


class Progreso(Gtk.Dialog, IdleObject):
    __gsignals__ = {
        'i-want-stop': (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, title, parent, max_value):
        Gtk.Dialog.__init__(self, title, parent,
                            Gtk.DialogFlags.MODAL |
                            Gtk.DialogFlags.DESTROY_WITH_PARENT)
        IdleObject.__init__(self)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_size_request(330, 30)
        self.set_resizable(False)
        self.connect('destroy', self.close)
        self.set_modal(True)
        vbox = Gtk.VBox(spacing=5)
        vbox.set_border_width(5)
        self.get_content_area().add(vbox)
        #
        frame1 = Gtk.Frame()
        vbox.pack_start(frame1, True, True, 0)
        table = Gtk.Table(2, 2, False)
        frame1.add(table)
        #
        self.label = Gtk.Label()
        table.attach(self.label, 0, 2, 0, 1,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK,
                     yoptions=Gtk.AttachOptions.EXPAND)
        #
        self.progressbar = Gtk.ProgressBar()
        self.progressbar.set_size_request(300, 0)
        table.attach(self.progressbar, 0, 1, 1, 2,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK,
                     yoptions=Gtk.AttachOptions.EXPAND)
        button_stop = Gtk.Button()
        button_stop.set_size_request(40, 40)
        button_stop.set_image(
            Gtk.Image.new_from_stock(Gtk.STOCK_STOP, Gtk.IconSize.BUTTON))
        button_stop.connect('clicked', self.on_button_stop_clicked)
        table.attach(button_stop, 1, 2, 1, 2,
                     xpadding=5,
                     ypadding=5,
                     xoptions=Gtk.AttachOptions.SHRINK)
        self.stop = False
        self.show_all()
        self.max_value = float(max_value)
        self.value = 0.0

    def set_max_value(self, anobject, max_value):
        self.max_value = float(max_value)

    def get_stop(self):
        return self.stop

    def on_button_stop_clicked(self, widget):
        self.stop = True
        self.emit('i-want-stop')

    def close(self, *args):
        self.destroy()

    def increase(self, anobject, value):
        self.value += float(value)
        fraction = self.value/self.max_value
        self.progressbar.set_fraction(fraction)
        if self.value >= self.max_value:
            self.hide()

    def set_element(self, anobject, element):
        self.label.set_text(_('Sending: %s') % element)


def add_emblem(path, emblem):
    p = subprocess.Popen(["gvfs-info", "-a", "metadata::emblems", path],
                         stdout=subprocess.PIPE)
    out, err = p.communicate()
    emblems = []
    for row in out.splitlines()[1:]:
        row = row.strip()
        if row.startswith("metadata::emblems:"):
            row = row[len("metadata::emblems:"):].strip("[ ]")
            emblems.extend([x.strip() for x in row.split(",")])
    emblems.append(emblem[len("emblem-"):])
    p = subprocess.Popen(["gvfs-set-attribute", "-t", "stringv", path,
                          "metadata::emblems"] + emblems)
    p.communicate()
    os.system("xte 'keydown Control_L' 'key R' 'keyup Control_L'")


def remove_emblem(path):
    p = subprocess.Popen(["gvfs-set-attribute", "-t", "unset", path,
                          "metadata::emblems"])
    p.communicate()
    os.system("xte 'keydown Control_L' 'key R' 'keyup Control_L'")


class EmblemsMenu(GObject.GObject, FileManager.MenuProvider):
    extra_emblems = None
    emblem_names = {}
    def __init__(self):

        # TODO: Is there a way to ask Nautilus for the list of all
        # possible emblems?
        if EmblemsMenu.extra_emblems is None:
            EmblemsMenu.extra_emblems = []
            usericons = os.path.expanduser(USER_EMBLEMS_PATH)
            for f in glob.glob(usericons + "/*.icon"):
                for row in open(f):
                    if row.startswith("DisplayName="):
                        name = row[len("DisplayName="):].strip()
                        n = os.path.basename(f)
                        n = os.path.splitext(n)[0]
                        EmblemsMenu.emblem_names[n] = name
                        EmblemsMenu.extra_emblems.append(n)
            EmblemsMenu.extra_emblems.sort()

    def get_file_items(self, window, files):
        top_menuitem = FileManager.MenuItem(
            name='EmblemsMenu::Gtk-emblems-top',
            label=_('Emblems'),
            tip=_('Set and unset emblems'))
        submenu = FileManager.Menu()
        top_menuitem.set_submenu(submenu)

        for sub, emblems in [("Standard", free_desktop_emblems),
                             ("User", EmblemsMenu.extra_emblems)]:
            if not emblems:
                continue
            sub_menuitem = FileManager.MenuItem(
                name='EmblemsMenu::Gtk-emblems-' + sub,
                label=sub,
                tip=sub)
            emblems_menu = FileManager.Menu()
            sub_menuitem.set_submenu(emblems_menu)
            submenu.append_item(sub_item)
            for e in emblems:
                display_name = EmblemsMenu.emblem_names.get(
                    e, e[len("emblem-"):])
                # TODO: How do we get the emblem icon image, and how
                # do we attach it to the menu as item?
                emblem_item = FileManager.MenuItem(
                    name='EmblemsMenu::Gtk-emblems-sub-' + sub + '-' + e,
                    label=display_name,
                    tip=desplay_name)
                emblem_item.connect('activate',
                                    self.emblemize,
                                    files,
                                    emblem,
                                    window)
                emblems_menu.append_item(emblem_item)

        sub_menuitem_clear = FileManager.MenuItem(
            name='EmblemsMenu::Gtk-emblems-clear',
            label='Clear',
            tip='Remove the emblem')
        sub_menuitem_clear.connect('activate',
                                   self.emblemize,
                                   files,
                                   None,
                                   window)
        submenu.append_item(sub_menuitem_clear)
        sub_menuitem_about = FileManager.MenuItem(
            name='EmblemsMenu::Gtk-emblems-about',
            label=_('About'),
            tip=_('About'))
        sub_menuitem_about.connect('activate', self.about, window)
        submenu.append_item(sub_menuitem_about)

        return menu_item,

    def emblemize(self, menu, files, emblem, window):
        diib = DoItInBackground(files, emblem)
        progreso = Progreso(_('Set emblems'),
                            window,
                            len(files))
        diib.connect('started', progreso.set_max_value)
        diib.connect('start_one', progreso.set_element)
        diib.connect('end_one', progreso.increase)
        diib.connect('ended', progreso.close)
        progreso.connect('i-want-stop', diib.stop)
        diib.start()
        progreso.run()

    def about(self, widget, window):
        ad = Gtk.AboutDialog(parent=window)
        ad.set_name(APP)
        ad.set_version(VERSION)
        ad.set_copyright('Copyrignt (c) 2011 allefant\nCopyrignt (c) 2016')
        ad.set_comments(APP)
        ad.set_license('''
This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
''')
        ad.set_website('https://www.atareao.es')
        ad.set_website_label('https://www.atareao.es')
        ad.set_authors([
            'allefant <https://github.com/allefant>',
            'Lorenzo Carbonell <lorenzo.carbonell.cerezo@gmail.com>'])
        ad.set_documenters([
            'Lorenzo Carbonell <lorenzo.carbonell.cerezo@gmail.com>'])
        ad.set_icon_name(APP)
        ad.set_logo_icon_name(APP)
        ad.run()
        ad.destroy()
