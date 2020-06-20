#!/usr/bin/env python3
import argparse
import configparser
import sys
from os.path import expandvars
import os

from pubs import endecoder
from pubs.config import load_conf
from pubs.repo import Repository
from rofi import Wofi

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

    def _parse_config(self):
        """Parse the configuration file."""
        config_file = self._config

        with open(config_file, "r") as f:
            file_content = '[general]\n' + f.read()

        config_parser = configparser.RawConfigParser()
        config_parser.read_string(file_content)

        # Add default options
        config_parser["DEFAULT"] = {
            "PDFVIEWER": "zathura",
            "WOFI": "/usr/bin/wofi",
            "CONFIGS_DIR": "$HOME/.config/pubs",
            "DEFAULT_LIB": "$HOME/.config/pubs/main_lib.conf",
            "CACHE_AUTH": "$HOME/.local/tmp/pubs_wofi_auth",
            "CACHE_LIBS": "$HOME/.local/tmp/pubs_wofi_libs",
            "TERMINAL_EDIT": "termite",
        }

        conf_ = config_parser["general"]

        # Read the configuration file
        self._pdfviewer = conf_.get("PDFVIEWER")
        self._wofi = conf_.get("WOFI")
        self._config_dir = expandvars(conf_.get("CONFIGS_DIR"))
        self._default_lib = expandvars(conf_.get("DEFAULT_LIB"))
        self._cache_auth = expandvars(conf_.get("CACHE_AUTH"))
        self._cache_libs = expandvars(conf_.get("CACHE_LIBS"))
        self._terminal = conf_.get("TERMINAL_EDIT")

    def menu_main(self, library="default"):
        """Present the main menu for the given library.

        Parameters
        ----------
        library : str
            The default library.

        Returns
        -------
        TODO

        """
        if library == "default":
            conf = load_conf(self._default_lib)
        else:
            conf = load_conf(library)

        repo = Repository(conf)

        menu_entries = self._gen_menu_entries(repo)

        keys = [p.citekey for p in repo.all_papers()]

        for paper in repo.all_papers():
            bibdata = paper.bibdata

        wofi_options = [
            "--allow-markup",
            "--insensitive",
            r"-Ddmenu-separator=\\0"
        ]

        wofi = Wofi(width=1200, rofi_args=wofi_options)
        selected = wofi.select("Literature", menu_entries, keep_newlines=True)

        citekey = keys[selected[0]]

    def _gen_menu_entries(self, repo):
        """Generate menu entries for the library items.

        Parameters
        ----------
        repo : TODO

        Returns
        -------
        TODO

        """

        for paper in repo.all_papers():
            bibdata = paper.bibdata
            if "author" in bibdata:
                au = "; ".join(bibdata["author"])
            else:
                au = "; ".join(bibdata["editor"])

            title = bibdata["title"]
            year = bibdata["year"]
            key = paper.citekey

            metadata = paper.metadata
            if metadata["docfile"] is None:
                pdf = ""
            else:
                pdf = ""

            entry = (f"<tt>{pdf} </tt> ({year}) <b>{au}</b> \n" +
                     f"<tt>   </tt><i>{title}</i>\0")

            yield entry


if __name__ == "__main__":
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

    wofi_pubs = WofiPubs(config)
    wofi_pubs.menu_main()
