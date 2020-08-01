import gi

gi.require_version("Gtk", "3.0")  # isort: skip
from gi.repository import Gtk  # isort: skip


class AddReferenceDialog(Gtk.Window):
    def __init__(self, text, description):
        Gtk.Window.__init__(self, title="Wofi-pubs")

        self.input = ""
        self.doc_path = None
        self.text = text
        self.box = Gtk.Grid(orientation=Gtk.Orientation.HORIZONTAL, column_spacing=10,
                row_spacing=10)

        self.description = Gtk.Label(label=description)
        self.description.set_justify(Gtk.Justification.LEFT)
        self.box.attach(self.description, 0, 0, 2, 1)
        self.add(self.box)

        self.box.attach(Gtk.Label(label=""), 0, 3, 3, 1)

        # User input
        self.label = Gtk.Label(label=self.text)
        self.box.attach(self.label, 0, 1, 1, 1)

        self.entry = Gtk.Entry()
        self.entry.set_width_chars(25)
        self.entry.set_placeholder_text(text + "...")
        self.entry.connect("activate", self.on_button_clicked)
        self.box.attach(self.entry, 1, 1, 1, 1)

        self.button2 = Gtk.Button(label="Add")
        self.button2.connect("clicked", self.on_button_clicked)
        self.box.attach(self.button2, 2, 1, 1, 1)

        # File chooser
        image = Gtk.Image(stock=Gtk.STOCK_OPEN)
        self.button_choose = Gtk.Button(image=image)
        self.box.attach(self.button_choose, 0, 2, 1, 1)
        self.button_choose.connect("clicked", self.choose_file)

        self.file_path = Gtk.Label("Select a file (optional)")
        self.file_path.set_width_chars(30)
        self.file_path.set_ellipsize(mode=1)
        self.box.attach(self.file_path, 1, 2, 1, 1)

        self.set_default_size(400, 30)

    def on_button_clicked(self, widget):
        self.close()
        self.input = self.entry.get_text()
        if self.file_path != "":
            self.doc_path = self.file_path.get_text()

        return 1

    def choose_file(self, widget):
        dialog = Gtk.FileChooserDialog(title="Please choose a file", parent=self,
                                       action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,
            Gtk.ResponseType.OK,
        )

        self.add_filters(dialog)

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            self.file_path.set_text(dialog.get_filename())
        elif response == Gtk.ResponseType.CANCEL:
            self.file_path.set_text("")

        dialog.destroy()

    def add_filters(self, dialog):
        """TODO: Docstring for add_filters.
        Returns
        -------
        TODO

        """
        filter_text = Gtk.FileFilter()
        filter_text.set_name("PDF files")
        filter_text.add_mime_type("application/pdf")
        dialog.add_filter(filter_text)

        filter_any = Gtk.FileFilter()
        filter_any.set_name("Any files")
        filter_any.add_pattern("*")
        dialog.add_filter(filter_any)



class ChooseFile(Gtk.Window):
    def __init__(self, text, description, filter):
        Gtk.Window.__init__(self, title="Wofi-pubs")

        self.input = ""
        self.filter = filter
        self.text = text
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.subbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(self.box)

        self.description = Gtk.Label(label=description)
        self.description.set_justify(Gtk.Justification.LEFT)
        self.box.pack_start(self.description, True, True, padding=10)

        self.box.pack_start(self.subbox, True, True, 0)
        self.box.pack_start(Gtk.Label(label=""), True, True, 0)

        image = Gtk.Image(stock=Gtk.STOCK_OPEN)
        self.button_choose = Gtk.Button(image=image)
        self.subbox.pack_start(self.button_choose, False, True, padding=10)
        self.button_choose.connect("clicked", self.choose_file)

        self.entry = Gtk.Entry()
        self.entry.set_width_chars(30)
        self.entry.connect("activate", self.on_button_clicked)
        self.entry.set_placeholder_text("path to file...")
        self.subbox.pack_start(self.entry, False, False, padding=0)

        self.button2 = Gtk.Button(label="OK")
        self.button2.connect("clicked", self.on_button_clicked)
        self.subbox.pack_start(self.button2, False, False, padding=10)

        self.set_default_size(400, 30)

    def on_button_clicked(self, widget):
        self.close()
        self.input = self.entry.get_text()

        return 1

    def choose_file(self, widget):
        dialog = Gtk.FileChooserDialog(title="Please choose a file", parent=self,
                                       action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OPEN,
            Gtk.ResponseType.OK,
        )

        self.add_filters(dialog)

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            self.entry.set_text(dialog.get_filename())
        elif response == Gtk.ResponseType.CANCEL:
            self.entry.set_text("")

        dialog.destroy()

    def add_filters(self, dialog):
        """TODO: Docstring for add_filters.
        Returns
        -------
        TODO

        """
        if self.filter == "pdf":
            filter_text = Gtk.FileFilter()
            filter_text.set_name("PDF files")
            filter_text.add_mime_type("application/pdf")
            dialog.add_filter(filter_text)
        elif self.filter == "bib":
            filter_text = Gtk.FileFilter()
            filter_text.set_name("Bibfiles")
            filter_text.add_mime_type("text/x-bibtex")
            dialog.add_filter(filter_text)

        filter_any = Gtk.FileFilter()
        filter_any.set_name("Any files")
        filter_any.add_pattern("*")
        dialog.add_filter(filter_any)


def get_user_input(text, description):
    """Get a text input from the user.

    Parameters
    ----------
    text : TODO
    description : TODO

    Returns
    -------
    str : user input

    """
    dialog = AddReferenceDialog(text=text, description=description)
    dialog.connect("destroy", Gtk.main_quit)
    dialog.show_all()
    Gtk.main()

    return dialog.input, dialog.doc_path


def choose_file(text, description, filter):
    """Get a text input from the user.

    Parameters
    ----------
    text : TODO
    description : TODO

    Returns
    -------
    str : user input

    """
    dialog = ChooseFile(text=text, description=description, filter=filter)
    dialog.connect("destroy", Gtk.main_quit)
    dialog.show_all()
    Gtk.main()

    return dialog.input


