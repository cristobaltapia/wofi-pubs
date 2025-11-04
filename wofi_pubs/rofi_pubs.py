#!/usr/bin/env python3

import argparse
import configparser
import json
import os
import re
import shlex
import subprocess
from multiprocessing.connection import Client
from os.path import expandvars

import bibtexparser

from wofi_pubs.rofi import Rofi

from .dialogs import choose_file, choose_two_files, get_user_input

DEFAULT_CONFIG = expandvars("${XDG_CONFIG_HOME}/wofi-pubs/config")


class RofiPubs:
    """Docstring for RofiPubs.

    Parameters
    ----------
    config : TODO


    """

    esc_key = -1
    open_key = 0
    quit_key = 1
    edit_key = 2
    change_lib_key = 3
    help_key = 4
    send_dpt_key = 5
    add_key = 6
    export_key = 7
    send_mail_key = 8
    refresh_key = 9
    update_meta_key = 10

    def __init__(self, config: str):
        self._config = config
        self._default_lib: str | None = None
        self._parse_config()
        self._libs_entries: dict[str, str] = dict()
        self._conn = Client(("localhost", 6000))
        self.keys = self.get_keys()

        self._rofi: Rofi = Rofi()

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

    def get_keys(self):
        return {
            f"key{self.open_key}": ("Enter", " Open"),
            f"key{self.edit_key}": ("Control-e", " Edit"),
            f"key{self.add_key}": ("Control-a", " Add"),
            f"key{self.send_dpt_key}": ("Control-t", " Send to DPT"),
            f"key{self.export_key}": ("Control-n", " Export"),
            f"key{self.send_mail_key}": ("Alt-m", " Send Email"),
            f"key{self.change_lib_key}": ("Alt-l", "Change lib"),
            f"key{self.refresh_key}": ("Alt-r", "Refresh"),
            f"key{self.update_meta_key}": ("Alt-a", "Update metadata"),
        }

    def menu_main(self, library="default", tag=None):
        """Present the main menu for the given library.

        Parameters
        ----------
        library : str
            The default library.
        tag : str
            Present only documents with the given tag.

        """
        key = None
        indices = None

        options = {
            "eh": 3,
            "sep": "|",
            "markup_rows": True,
            "multi_select": True,
            "case_sensitive": False,
        }

        if library == "default":
            library = self._default_lib

        if tag:
            tag_post = f"(<i>{tag}</i>)"
        else:
            tag_post = ""

        # Get publication list from server
        self._conn.send({"cmd": "get-publication-list", "library": library, "tag": tag})
        menu_entries, keys = self._conn.recv()

        options.update(self.keys)

        while not (key == self.quit_key or key == self.esc_key):
            indices, key = self._rofi.select(
                "Filter: ",
                # [header_filter(d) for d in menu_entries],
                menu_entries,
                select=indices,
                **options,
            )
            citekey = keys[indices[0]]
            if indices == [-1]:
                indices = []
                key = -1
            if not isinstance(indices, list):
                indices = [indices]
            if key == self.edit_key:
                self._conn.send(
                    {"cmd": "edit-reference", "library": library, "citekey": citekey}
                )
                self._conn.send(
                    {
                        "cmd": "update-list-order",
                        "library": library,
                        "index": indices[0],
                    }
                )
                key = -1
            if key == self.add_key:
                self.menu_add(library)
                key = -1
            if key == self.open_key:
                for k in indices:
                    key_i = keys[k]
                    self._conn.send(
                        {"cmd": "open-document", "library": library, "citekey": key_i}
                    )
                    self._conn.send(
                        {"cmd": "update-list-order", "library": library, "index": k}
                    )
                key = -1
            elif key == self.send_dpt_key:
                self._send_to_dptrp1(library, citekey)
                key = -1
            elif key == self.send_mail_key:
                self._conn.send(
                    {"cmd": "send-per-email", "library": library, "citekey": citekey}
                )
                key = -1
            elif key == self.export_key:
                self._conn.send(
                    {"cmd": "export-reference", "library": library, "citekey": citekey}
                )
            elif key == self.update_meta_key:
                self._conn.send(
                    {
                        "cmd": "update-pdf-metadata",
                        "library": library,
                        "citekey": citekey,
                    }
                )
            elif key == self.change_lib_key:
                self.menu_change_lib()
                key = -1
            elif key == self.refresh_key:
                self.refresh()

    def menu_change_lib(self):
        """Present menu to change library."""
        configs_dir = self._config_dir
        configs_files = os.listdir(configs_dir)

        key = None
        indices = None
        options = {
            "eh": 1,
            "sep": "|",
            "markup_rows": True,
            "multi_select": False,
            "case_sensitive": False,
        }

        indices, key = self._rofi.select(
            "Filter: ",
            # [header_filter(d) for d in menu_entries],
            configs_files,
            select=indices,
            **options,
        )

        selected_lib = self._config_dir + "/" + configs_files[indices[0]]

        self.menu_main(selected_lib)

    def menu_add(self, library: str):
        """Menu to add a new reference.

        Parameters
        ----------
        library : str
            Path to the configuration file of the library.

        """
        menu_ = [
            ('<span foreground="#ebcb8b"></span>', "DOI"),
            ('<span foreground="#ebcb8b"></span>', "arXiv"),
            ('<span foreground="#ebcb8b"></span>', "ISBN"),
            ('<span foreground="#ebcb8b"></span>', "Bibfile"),
            ('<span foreground="#ebcb8b"></span>', "Manual Bibfile"),
        ]

        menu_str = [f"{ico} <b>{opt}</b>\n" for ico, opt in menu_]

        key: int | None = None
        indices: list | None = None
        options = {
            "eh": 1,
            "sep": "|",
            "markup_rows": True,
            "multi_select": False,
            "case_sensitive": False,
        }

        while not (key == self.quit_key or key == self.esc_key):
            indices, key = self._rofi.select(
                "Filter: ",
                # [header_filter(d) for d in menu_entries],
                menu_str,
                select=indices,
                **options,
            )

            option = menu_[indices[0]][1]

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
            break

    def _add_doi(self, library: str):
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

    def _add_arxiv(self, library: str):
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

    def _add_isbn(self, library: str):
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

    def _add_bibfile(self, library: str):
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

    def _add_bibfile_manual(self, library: str):
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

        menu_str = [f"{ico}\t\t <b>{opt}</b>" for ico, opt in menu_]

        options = {
            "markup_rows": True,
            "multi_select": False,
            "case_sensitive": False,
            "width": 200,
        }
        key = None

        while not (key == self.quit_key or key == self.esc_key):
            indices, key = self._rofi.select(
                "Select device: ",
                menu_str,
                **options,
            )
            if len(indices) == 0:
                key = -1
            else:
                addr = menu_[indices[0]][1]
                self._conn.send(
                    {
                        "cmd": "send-to-device",
                        "addr": addr,
                        "library": library,
                        "citekey": citekey,
                    }
                )
            break

        # Bach to the main manu
        # self.menu_main(library, tag=None)


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

    # loop = GLib.MainLoop()
    wofi_pubs = RofiPubs(config)
    wofi_pubs.menu_main()
    # pr.disable()
    # pr.print_stats()
    # loop.run()


if __name__ == "__main__":
    main()
