import argparse
import configparser
import json
import os
import subprocess
import threading
from multiprocessing.connection import Listener
from os.path import expandvars

import bibtexparser
import gi
from pubs import content, events, plugins, uis
from pubs.bibstruct import extract_citekey
from pubs.commands.add_cmd import bibentry_from_api
from pubs.commands.add_cmd import command as add_cmd
from pubs.commands.edit_cmd import command as edit_cmd
from pubs.config import load_conf
from pubs.content import get_content
from pubs.endecoder import EnDecoder
from pubs.repo import Paper, Repository
from pubs.uis import init_ui

from .email import send_doc_per_mail
from .print_to_dpt import show_sent_file, to_dpt
from .update_metadata import update_pdf_metadata

gi.require_version("Notify", "0.7")
from gi.repository import GLib, Notify

DEFAULT_CONFIG = expandvars("${XDG_CONFIG_HOME}/wofi-pubs/config")


class PubsArgs:
    """Dummy class to store arguments needed for the pubs commands."""

    def __init__(self):
        self.meta = None
        self.citekey: str | None = None
        self.doi: str | None = None
        self.arxiv: str | None = None
        self.isbn: str | None = None
        self.docfile: str | None = None
        self.citekey: str | None = None
        self.bibfile: str | None = None
        self.tags: str | None = None
        self.doc_copy = "copy"


class PubsServer:
    """Docstring for WofiPubs.

    Parameters
    ----------
    config : TODO


    """

    def __init__(self, config):
        self._config = config
        self._parse_config()
        self._libs_entries = dict()
        self.notification = None
        self.entries: dict[str, list[str]] = dict()
        self.keys: dict[str, list[str]] = dict()
        self.repos: dict[str, Repository] = dict()
        # Initialize notifications
        Notify.init("Wofi-pubs")
        self.notification = None
        self.last_key_idx: dict[str, int] = {}

        self._load_publications()

    def _parse_config(self):
        """Parse the configuration file."""
        config_file = self._config

        with open(config_file, "r") as f:
            file_content = "[general]\n" + f.read()

        config_parser = configparser.RawConfigParser()
        config_parser.read_string(file_content)

        # Add default options
        config_parser["DEFAULT"] = {
            "pdfviewer": "zathura",
            "wofi": "/usr/bin/wofi",
            "configs_dir": "$HOME/.config/pubs",
            "default_lib": "$HOME/.config/pubs/main_lib.conf",
            "cache_auth": "$HOME/.local/tmp/pubs_wofi_auth",
            "cache_libs": "$HOME/.local/tmp/pubs_wofi_libs",
            "terminal_edit": "$TERM -e nvim",
            "editor": "$TERM -e nvim",
            "picker": "wofi",
        }

        conf_ = config_parser["general"]

        # Read the configuration file
        self._pdfviewer = conf_.get("PDFVIEWER")
        self._wofi_exe = expandvars(conf_.get("WOFI"))
        self._config_dir = expandvars(conf_.get("configs_dir"))
        self._default_lib = expandvars(conf_.get("default_lib"))
        self._cache_auth = expandvars(conf_.get("cache_auth"))
        self._cache_libs = expandvars(conf_.get("cache_libs"))
        self._terminal = conf_.get("TERMINAL_EDIT")
        self._editor = expandvars(conf_.get("editor"))
        self._dpt_devices = expandvars("${HOME}/.dpapp/devices.json")
        self._picker = conf_.get("picker")

    def load_conf(self, library: str):
        """Load configuration file in pubs.

        Parameters
        ----------
        library : TODO

        Returns
        -------
        conf :
            Configuration of the library.

        """
        conf = load_conf(library)
        conf["main"]["edit_cmd"] = self._editor
        conf.write()
        init_ui(conf)
        plugins.load_plugins(conf, uis._ui)

        return conf

    def _load_publications(self, tag: str = None):
        """Present the main menu for the given library.

        Parameters
        ----------
        library : str
            The default library.
        tag : str
            Present only documents with the given tag.

        """
        if tag:
            tag_post = f"(<i>{tag}</i>)"
        else:
            tag_post = ""

        # Get names of all libraries
        configs_dir = self._config_dir
        libraries = os.listdir(configs_dir)

        # Iterate over all configuration files
        for lib_i in libraries:
            config_path = configs_dir + "/" + lib_i
            conf = self.load_conf(config_path)

            repo = Repository(conf)
            entries = self._gen_menu_entries(repo, tag)
            menu_entries, keys = zip(*entries)

            self.entries[config_path] = [p for p in menu_entries]
            self.keys[config_path] = [k for k in keys]
            self.repos[config_path] = repo
            # Set last entry item
            self.last_key_idx[config_path] = 0

    def start_listening(self):
        """Start the listening loop of the server.

        It listens for requests from the client and executes the needed functions.

        """
        while True:
            listener = Listener(("localhost", 6000))
            running = True
            # conn = listener.accept()
            print(f"connection accepted from {listener.last_accepted}")
            try:
                while running:
                    conn = listener.accept()
                    print(f"connection accepted from {listener.last_accepted}")
                    while True:
                        # while conn.poll():
                        msg = conn.recv()
                        print(msg)
                        if msg["cmd"] == "get-publication-list":
                            library = msg["library"]
                            tag = msg["tag"]
                            if tag:
                                repo = self.repos[library]
                                entries = self._gen_menu_entries(repo, tag)
                                menu_entries, keys = zip(*entries)
                                conn.send((menu_entries, keys))
                            else:
                                conn.send((self.entries[library], self.keys[library]))
                            # Update the ui to point to the right library
                            self.load_conf(library)
                        elif msg["cmd"] == "get-publication-info":
                            library = msg["library"]
                            citekey = msg["citekey"]
                            info = self._get_reference_info(library, citekey)
                            conn.send(info)
                        elif msg["cmd"] == "add-reference":
                            library = msg["library"]
                            args = msg["args"]
                            self._add_reference(library, args)
                        elif msg["cmd"] == "open-document":
                            library = msg["library"]
                            citekey = msg["citekey"]
                            self._open_doc(library, citekey)
                        elif msg["cmd"] == "edit-reference":
                            library = msg["library"]
                            citekey = msg["citekey"]
                            self._edit_bib(library, citekey)
                        elif msg["cmd"] == "export-reference":
                            library = msg["library"]
                            citekey = msg["citekey"]
                            self._export_bib(library, citekey)
                        elif msg["cmd"] == "get-tags":
                            library = msg["library"]
                            tags = list(self.repos[library].get_tags())
                            conn.send(tags)
                        elif msg["cmd"] == "add-tag":
                            library = msg["library"]
                            citekey = msg["citekey"]
                            tag = msg["tag"]
                            self._add_tag(tag, library, citekey)
                            conn.send("Done")
                        elif msg["cmd"] == "send-to-device":
                            library = msg["library"]
                            citekey = msg["citekey"]
                            addr = msg["addr"]
                            self._send_to_dptrp1(library, citekey, addr)
                        elif msg["cmd"] == "send-per-email":
                            library = msg["library"]
                            citekey = msg["citekey"]
                            send_doc_per_mail(self.repos[library], citekey)
                        elif msg["cmd"] == "update-pdf-metadata":
                            library = msg["library"]
                            citekey = msg["citekey"]
                            self._update_pdf_metadata(library, citekey)
                        elif msg["cmd"] == "update-list-order":
                            library = msg["library"]
                            index = msg["index"]
                            print(f"Library: {library}; index: {index}")
                            self.update_entries_order(index, library)
                        elif msg["cmd"] == "restart-server":
                            raise SystemExit
                        else:
                            running = False
                            break

            except ConnectionResetError:
                listener.close()
                continue
            except EOFError:
                print("Wofi-pubs client closed")
                listener.close()
                continue

    def menu_tags(self, repo: Repository, library: str):
        """Present menu with existing tags in the library.

        Parameters
        ----------
        repo : :obj:`Repository`
            Repository containing all the papers.
        library : str
            Path to the library configuration file.

        """
        tags = list(repo.get_tags())

        wofi = self._wofi_misc
        wofi.lines = min([len(tags), 15])

        selected = wofi.select("Search tags...", tags)

        sel_tag = tags[selected[0]]

        self.menu_main(library, sel_tag)

    def menu_add(self, repo: Repository, library: str):
        """Show menu to add a new reference to the library.

        Parameters
        ----------
        repo : :obj:`Repository`
            Repository containing all the papers.
        library : str
            Path to the library configuration file.

        """
        wofi = self._wofi_misc

        menu_ = [
            ("", "DOI"),
            ("", "arXiv"),
            ("", "ISBN"),
            ("", "Bibfile"),
            ("", "Manual Bibfile"),
            ("", "Back"),
        ]

        menu_str = "".join(f"{ico}\t <b>{opt}</b>\0" for ico, opt in menu_)

        wofi = self._wofi_ref
        wofi.lines = 6

        selected = wofi.select("...", menu_str, keep_newlines=True)

        option = menu_[selected[0]][1]

        if option == "DOI":
            self._add_doi(repo)
        elif option == "arXiv":
            self._add_arxiv(repo)
        elif option == "ISBN":
            self._add_isbn(repo)
        elif option == "Bibfile":
            self._add_bibfile(repo)
        elif option == "Manual Bibfile":
            self._add_bibfile_manual(repo)
        elif option == "Back":
            self.menu_main(library)

    def _gen_menu_entries(self, repo: Repository, tag: str):
        """Generate menu entries for the library items.

        Parameters
        ----------
        repo : :obj:`Repository`
            The repository object containing the papers from which the
            entries should be generated.

        Yields
        ------
        entry : str
            Formatted text representing the information of each paper.
        key : str
            Key corresponding to the paper.

        """
        for paper in repo.all_papers():
            if tag:
                if tag not in paper.tags:
                    continue

            entry, key = self._gen_paper_entry(paper)

            yield entry, key

    def _gen_paper_entry(self, paper: Paper):
        """Generate the paper description for the main menu.

        Parameters
        ----------
        paper : :obj:`Paper`
            The paper object from which the entry is generated.

        Returns
        -------
        entry : str
            The text that will be displayed.
        key : str
            The key of the corresponding paper.

        """
        bibdata = paper.bibdata
        if "author" in bibdata:
            author = "; ".join(bibdata["author"])
        elif "editor" in bibdata:
            author = "; ".join(bibdata["editor"])
        elif "key" in bibdata:
            author = bibdata["key"]
        elif "organization" in bibdata:
            author = bibdata["organization"]
        else:
            author = "N.N."

        title = bibdata["title"]
        year = bibdata["year"]
        key = paper.citekey
        _tags = paper.tags
        if len(_tags) == 0:
            tags = ""
        else:
            tags = "(" + ";".join(list(_tags)) + ")"

        metadata = paper.metadata
        if metadata["docfile"] is None:
            pdf = ""
        else:
            pdf = '<span foreground="#ebcb8b"></span>'

        entry = (
            f"<b>{title}</b>\n"
            + f"      <i>{author}</i>\n"
            + f'      <span foreground="#bf616a"><b>{year}</b></span> '
            + f' {pdf} <span foreground="#a3be8c"><i>{tags}</i></span> '
        )
        if self._picker == "rofi":
            entry += "\0"

        return entry, key

    def _get_reference_info(self, library, citekey):
        """Generate content of the reference menu.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.
        citekey : str
            Citekey of the paper.

        Returns
        -------
        str :
            The detailed information of a given paper.

        """
        paper = self.repos[library].pull_paper(citekey)
        bibdata = paper.bibdata

        if "author" in bibdata:
            author = "; ".join(bibdata["author"])
        elif "editor" in bibdata:
            author = "; ".join(bibdata["editor"])
        elif "key" in bibdata:
            author = bibdata["key"]
        elif "organization" in bibdata:
            author = bibdata["organization"]
        else:
            author = "N.N."

        title = bibdata["title"]
        year = bibdata["year"]

        metadata = paper.metadata

        if metadata["docfile"] is None:
            pdf = False
        else:
            pdf = True

        if "subtitle" in bibdata:
            sub = bibdata["subtitle"]
        else:
            sub = None

        au = "Author(s):"
        ti = "Title:"
        su = "Subtitle:"
        ye = "Year:"

        if sub is None:
            entry = (
                f" <tt><b>{au:<11}</b></tt>\n{author}\0"
                + f" <tt><b>{ti:<11}</b></tt>\n{title}\0"
                + f" <tt><b>{ye:<11}</b></tt>\n{year}\0"
            )
        else:
            entry = (
                f" <tt><b>{au:<11}</b></tt>\n{author}\0"
                + f" <tt><b>{ti:<11}</b></tt>\n{title}\0"
                + f" <tt><b>{su:<11}</b></tt>\n{sub}\0"
                + f" <tt><b>{ye:<11}</b></tt>\n{year}\0"
            )

        return entry

    def _add_reference(self, library: str, args: PubsArgs):
        """Add a new paper to the selected 'library'.

        After the paper is added to the library, the paper is added to the
        main menu too.

        Parameters
        ----------
        library : str
            Path to the library.
        args : :obj:`PubsArgs`
            Metadata corresponding to the paper.

        """
        repo = self.repos[library]
        args.citekey = gen_citekey(repo, args)
        add_cmd(repo.conf, args)

        if args.docfile is not None:
            doc = update_pdf_metadata(repo, args.citekey)

        events.PostCommandEvent().send()

        # Update main menu entries
        paper = repo.pull_paper(args.citekey)

        entry, key = self._gen_paper_entry(paper)
        self.entries[library].append(entry)
        self.keys[library].append(key)

    def _add_tag(self, tag: str, library: str, citekey: str):
        """Add tag to reference.

        Parameters
        ----------
        tag : str
            Tag to be added to the reference.
        library : str
            Path to the configuration file of the library.
        citekey : str
            Citekey of the paper.

        """
        repo = self.repos[library]
        paper = repo.pull_paper(citekey)
        paper.add_tag(tag)
        repo.push_paper(paper, overwrite=True, event=False)
        events.PostCommandEvent().send()

    def _open_doc(self, library: str, citekey: str):
        """Open pdf file with default pdf reader.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.
        citekey : str
            Citekey of the paper.

        """
        repo = self.repos[library]
        paper = repo.pull_paper(citekey)

        docpath = content.system_path(repo.databroker.real_docpath(paper.docpath))
        cmd = self._pdfviewer.split()
        cmd.append(docpath)
        subprocess.Popen(cmd)

        return 1

    def _edit_bib(self, library: str, citekey: str):
        """Edit bibfile corresponding to the citekey.

        Parameters
        ----------
        library : str
            Path to the config file of the library.
        citekey : str
            Citekey of the paper to be edited.

        """
        repo = self.repos[library]
        conf = repo.conf
        args = PubsArgs()
        args.citekey = citekey
        edit_cmd(conf, args)
        events.PostCommandEvent().send()

        return 1

    def _export_bib(self, library: str, citekey: str):
        """Export citation of paper defined by `citekey` in bib format.

        The citation will be added to the clipboard by means of `wl-copy`.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.
        citekey : str
            Citekey for the paper.

        """
        repo = self.repos[library]
        paper = repo.pull_paper(citekey)

        bib = dict()
        bib[citekey] = paper.bibdata

        exporter = EnDecoder()
        bibdata_raw = exporter.encode_bibdata(bib, ignore_fields=["file"])

        cmd = ["wl-copy", f"{bibdata_raw}"]
        subprocess.Popen(cmd)

    def _send_to_dptrp1(self, library: str, citekey: str, addr: str):
        """Send document to Sony DPT-RP1 or compatible device.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.
        citekey : str
            Citekey of the paper.
        addr: str
            IP-address of device.

        """
        repo = self.repos[library]
        remote_path = to_dpt(repo, citekey, addr)

        self.notification = Notify.Notification.new(
            "Wofi-pubs", f"{citekey} sent to DPT-RP1"
        )
        self.notification.add_action(
            "clicked", "Display file in device", show_sent_file, (addr, remote_path)
        )
        self.notification.show()

    def _update_pdf_metadata(self, library: str, citekey: str):
        """Update the PDF's metadata to include author and title of paper.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.
        citekey : str
            Citekey of the paper.

        """
        repo = self.repos[library]
        paper = repo.pull_paper(citekey)

        docpath = content.system_path(repo.databroker.real_docpath(paper.docpath))
        doc = update_pdf_metadata(repo, citekey)
        events.PostCommandEvent().send()

    def update_entries_order(self, idx: int, library: str):
        """Reorder the list of entries and key to place the last selected element at the top.

        Parameters
        ----------
        idx : int
            The selected item.
        library : str
            The used library.

        """
        self.entries[library].insert(0, self.entries[library].pop(idx))
        self.keys[library].insert(0, self.keys[library].pop(idx))


def gen_citekey(repo: Repository, args: PubsArgs):
    """Generate the citekey when importing new references.

    Parameters
    ----------
    repo : Repository
        Contains the references.
    args : TODO

    Returns
    -------
    TODO

    """
    decoder = EnDecoder()
    if args.bibfile:
        bibentry_raw = get_content(args.bibfile, uis._ui)
        bibentry = decoder.decode_bibdata(bibentry_raw)
    else:
        bibentry = bibentry_from_api(args, uis._ui)

    base_key = extract_citekey(bibentry)
    citekey = repo.unique_citekey(base_key, uis._ui)
    return citekey


def main():
    pars = argparse.ArgumentParser(
        description="Manage your pubs bibliography with wofi"
    )
    pars.add_argument(
        "config",
        type=str,
        nargs="?",
        help="Configuration file for wofi-pubs",
        default=DEFAULT_CONFIG,
    )

    arguments = pars.parse_args()
    config = arguments.config

    loop = GLib.MainLoop()
    pubs_server = PubsServer(config)
    # Run the GLib main loop in a separate thread
    threading.Thread(target=loop.run, daemon=True).start()

    pubs_server.start_listening()


if __name__ == "__main__":
    main()
