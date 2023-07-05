#!/usr/bin/env python3

import argparse
import configparser
import json
import os
import re
import shlex
import subprocess
import sys
from itertools import chain
from multiprocessing.connection import Client
from os.path import expandvars

import bibtexparser
# from pubs import content, events, plugins, uis
# from pubs.bibstruct import extract_citekey
# from pubs.commands.add_cmd import bibentry_from_api
# from pubs.commands.add_cmd import command as add_cmd
# from pubs.commands.edit_cmd import command as edit_cmd
# from pubs.config import load_conf
# from pubs.endecoder import EnDecoder
# from pubs.repo import Repository
# from pubs.uis import init_ui
from wofi import Wofi

from .dialogs import choose_file, choose_two_files, get_user_input

# from .email import send_doc_per_mail

DEFAULT_CONFIG = expandvars("${XDG_CONFIG_HOME}/wofi-pubs/config")


class WofiPubs:
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
        self._conn = Client(('localhost', 6000))

        wofi_options = [
            "--allow-markup",
            "--insensitive",
            "--matching=fuzzy",
            r"-Ddmenu-separator=\\0",
        ]
        wofi_options_ref = [
            "--allow-markup",
            "--insensitive",
            r"-Ddmenu-separator=\\0",
            "--define=line_wrap=word",
        ]
        wofi_options_misc = [
            "--allow-markup",
            "--insensitive",
        ]

        self._wofi = Wofi(width=1200, wofi_args=wofi_options)
        self._wofi_ref = Wofi(width=800, wofi_args=wofi_options_ref)
        self._wofi_misc = Wofi(width=600, wofi_args=wofi_options_misc)

        self._wofi.wofi_exe = self._wofi_exe
        self._wofi_ref.wofi_exe = self._wofi_exe
        self._wofi_misc.wofi_exe = self._wofi_exe

    def _parse_config(self):
        """Parse the configuration file."""
        config_file = self._config

        with open(config_file, "r") as f:
            file_content = '[general]\n' + f.read()

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

    def menu_main(self, library="default", tag=None):
        """Present the main menu for the given library.

        Parameters
        ----------
        library : str
            The default library.
        tag : str
            Present only documents with the given tag.

        Returns
        -------
        TODO

        """
        if library == "default":
            library = self._default_lib

        if tag:
            tag_post = f"(<i>{tag}</i>)"
        else:
            tag_post = ""

        menu_ = [
            ("", "Change library", ""),
            ("", "Add publication", ""),
            ("", "Search tags", f"{tag_post}"),
            ("", "Sync. repo(s)", ""),
        ]

        if tag:
            menu_.insert(0, ("", "Show all", ""))

        menu_str = (f"{ico}\t <b>{opt}</b> {inf}\0" for ico, opt, inf in menu_)

        # Get publication list from server
        self._conn.send({"cmd": "get-publication-list", "library": library, "tag": tag})
        menu_entries, keys = self._conn.recv()

        wofi_disp = chain(menu_str, menu_entries)

        wofi = self._wofi
        wofi.width = 1200
        wofi.height = 700
        selected = wofi.select("Literature", wofi_disp, keep_newlines=True)

        # Check wchich publication was selected
        if selected[0] >= len(menu_):
            citekey = keys[selected[0] - len(menu_)]
            self.menu_reference(library, citekey, tag)
        elif selected[0] != -1 and selected[0] < len(menu_):
            option = menu_[selected[0]][1]
            if option == "Change library":
                self.menu_change_lib(library)
            elif option == "Add publication":
                self.menu_add(library)
            elif option == "Search tags":
                self.menu_tags(library)
            elif option == "Sync. repo(s)":
                pass
            elif option == "Show all":
                self.menu_main(library)

    def menu_reference(self, library, citekey, tag):
        """Menu to show the information of a given reference.

        Parameters
        ----------
        repo : TODO
        citekey : TODO

        Returns
        -------
        TODO

        """
        menu_ = [
            ("", "Open"),
            ("", "Export"),
            ("", "Send to DPT-RP1"),
            ("", "From same author(s)"),
            ("", "Edit"),
            ("", "Add tag"),
            ("", "Back"),
            ("", "Send per E-Mail"),
            ("", "Update PDF metadata"),
            ("", "More actions"),
        ]

        menu_str = "".join(f"{ico}\t <b>{opt}</b>\0" for ico, opt in menu_)
        menu_str += "\0"

        self._conn.send({
            "cmd": "get-publication-info",
            "library": library,
            "citekey": citekey
        })
        paper_info = self._conn.recv()

        wofi_disp = menu_str + paper_info

        wofi = self._wofi_ref
        wofi.lines = 16

        selected = wofi.select("...", wofi_disp, keep_newlines=True)

        option = menu_[selected[0]][1]

        if option == "Open":
            self._conn.send({
                "cmd": "open-document",
                "library": library,
                "citekey": citekey
            })
        elif option == "Back":
            self.menu_main(library=library, tag=tag)
        elif option == "Edit":
            self._conn.send({
                "cmd": "edit-reference",
                "library": library,
                "citekey": citekey
            })
        elif option == "Export":
            self._conn.send({
                "cmd": "export-reference",
                "library": library,
                "citekey": citekey
            })
        elif option == "Add tag":
            self._add_tag(library, citekey)
        elif option == "Send to DPT-RP1":
            self._send_to_dptrp1(library, citekey)
        elif option == "Send per E-Mail":
            self._conn.send({
                "cmd": "send-per-email",
                "library": library,
                "citekey": citekey
            })
        elif option == "Update PDF metadata":
            self._conn.send({
                "cmd": "update-pdf-metadata",
                "library": library,
                "citekey": citekey
            })
        # elif option == "More actions":
        #     self._ref_menu_more(repo, citekey)
        else:
            pass

    def menu_change_lib(self, library):
        """Present menu to change library.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.

        Returns
        -------
        TODO

        """
        configs_dir = self._config_dir
        configs_files = os.listdir(configs_dir)

        wofi = self._wofi_misc
        wofi.lines = max([len(configs_files), 10])

        selected = wofi.select("...", configs_files, keep_newlines=False)
        selected_lib = self._config_dir + "/" + configs_files[selected[0]]

        self.menu_main(selected_lib)

    def menu_tags(self, library):
        """Present menu with existing tags in the library.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.

        """
        # Get tag list from server
        self._conn.send({"cmd": "get-tags", "library": library})
        tags = self._conn.recv()

        wofi = self._wofi_misc
        wofi.lines = min([len(tags), 15])

        selected = wofi.select("Search tags...", tags)

        sel_tag = tags[selected[0]]

        self.menu_main(library, sel_tag)

    def menu_add(self, library):
        """Menu to add a new reference.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.

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
        wofi.lines = 7

        selected = wofi.select("...", menu_str, keep_newlines=True)

        option = menu_[selected[0]][1]

        if option == "DOI":
            self._add_doi(library)
        elif option == "arXiv":
            self._add_arxiv(library)
        elif option == "ISBN":
            self._add_isbn(library)
        elif option == "Bibfile":
            self._add_bibfile(library)
        elif option == "Manual Bibfile":
            self._add_bibfile_manual(library)
        elif option == "Back":
            self.menu_main(library)

    def _add_doi(self, library):
        """Add publication to library from DOI.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.


        """
        doi, doc = get_user_input("DOI:", description="Import reference by DOI")

        args = PubsArgs()
        args.doi = doi
        args.docfile = doc
        self._conn.send({"cmd": "add-reference", "library": library, "args": args})

    def _add_arxiv(self, library):
        """Add publication to library from ArXiv.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.

        """
        arxiv, doc = get_user_input("ArXiv:", description="Import reference by Arxiv")

        args = PubsArgs()
        args.arxiv = arxiv
        args.docfile = doc

        self._conn.send({"cmd": "add-reference", "library": library, "args": args})

    def _add_isbn(self, library):
        """Add publication to library from ISBN.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.

        """
        isbn, doc = get_user_input("ISBN:", description="Import reference by ISBN")

        args = PubsArgs()
        args.isbn = isbn
        args.docfile = doc
        self._conn.send({"cmd": "add-reference", "library": library, "args": args})

    def _add_bibfile(self, library):
        """Add publication to library from bibfile.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.

        """
        bibfile, doc = choose_two_files(
            text="Bibfile:",
            description="Import reference from Bibfile",
        )

        args = PubsArgs()
        args.bibfile = bibfile
        args.docfile = doc
        # Read bibfile
        if doc is not None:
            with open(bibfile) as bibtex_file:
                bibtex_str = bibtex_file.read()
                bib_database = bibtexparser.loads(bibtex_str)
                base_key = bib_database.entries[0]["ID"]

        self._conn.send({"cmd": "add-reference", "library": library, "args": args})

    def _add_bibfile_manual(self, library):
        """Add publication to library by manual entry of bibfile.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.

        """
        tmp_bib_file = os.path.expandvars("${HOME}/.local/tmp/test.bib")
        cmd = self._editor + f" {tmp_bib_file}"
        cmd_args = shlex.split(cmd)
        p = subprocess.Popen(cmd_args)
        p.wait()

        doc = choose_file("PDF:", "Choose a PDF file", filter="pdf")

        args = PubsArgs()
        args.bibfile = tmp_bib_file
        args.docfile = doc

        self._conn.send({"cmd": "add-reference", "library": library, "args": args})

    def _add_tag(self, library, citekey):
        """Add tag to reference.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.
        citekey : str
            Citekey for the publication.

        """
        # Get all tags
        self._conn.send({"cmd": "get-tags", "library": library})
        tags = self._conn.recv()

        # Present in wofi
        wofi = self._wofi_misc
        wofi.lines = min([len(tags), 15])

        new_tag = wofi.select_or_new("New tag...", tags)

        if new_tag != "":
            self._conn.send({
                "cmd": "add-tag",
                "tag": new_tag,
                "library": library,
                "citekey": citekey
            })

        self._conn.recv()
        self.menu_reference(library, citekey, None)

    def _open_doc(self, repo, citekey):
        """Open pdf file.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.
        citekey : str
            Citekey for the publication.

        """
        paper = repo.pull_paper(citekey)

        docpath = content.system_path(repo.databroker.real_docpath(paper.docpath))
        cmd = self._pdfviewer.split()
        cmd.append(docpath)
        subprocess.Popen(cmd)

        return 1

    def _send_to_dptrp1(self, library, citekey):
        """Send document to Sony DPT-RP1

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.
        citekey : str
            Citekey for the publication.

        """
        # Read ip addresses from config file
        devices_addr = self._dpt_devices
        with open(devices_addr, "r") as dev:
            devices = json.load(dev)

        menu_ = [(k, val) for k, val in devices.items()]

        menu_str = "".join(f"{ico}\t\t <b>{opt}</b>\0" for ico, opt in menu_)
        menu_str += "\0"

        wofi_disp = menu_str

        wofi = self._wofi_ref
        wofi.lines = 6

        selected_addr = wofi.select("...", wofi_disp, keep_newlines=True)

        addr = menu_[selected_addr[0]][1]

        self._conn.send({
            "cmd": "send-to-device",
            "addr": addr,
            "library": library,
            "citekey": citekey
        })

        self.menu_reference(library, citekey, tag=None)


class PubsArgs:
    """Dummy class to store arguments needed for the pubs commands."""

    def __init__(self):
        self.meta = None
        self.citekey = None
        self.doi = None
        self.arxiv = None
        self.isbn = None
        self.docfile = None
        self.citekey = None
        self.bibfile = None
        self.tags = None
        self.doc_copy = "copy"


def name_library(config_file):
    """Get the name of the library based on the config filename.

    Parameters
    ----------
    config_file : str
        Path to the configuration file.

    Returns
    -------
    str: name of the library

    """
    m = re.match(r"^.*/([a-zA-Z\._-]+)\.conf$", config_file)
    print(config_file)
    print(m)

    return m.group(1)


def main():
    pars = argparse.ArgumentParser(description="Manage your pubs bibliography with wofi")
    pars.add_argument(
        "config",
        type=str,
        nargs="?",
        help="Configuration file for wofi-pubs",
        default=DEFAULT_CONFIG,
    )

    arguments = pars.parse_args()
    config = arguments.config

    # loop = GLib.MainLoop()
    wofi_pubs = WofiPubs(config)
    wofi_pubs.menu_main()
    # pr.disable()
    # pr.print_stats()
    # loop.run()


if __name__ == "__main__":
    main()
