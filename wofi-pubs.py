#!/usr/bin/env python3
import argparse
import configparser
import os
import subprocess
import sys
from os.path import expandvars
from pubs.endecoder import EnDecoder

from pubs.paper import Paper
from pubs.uis import PrintUI, InputUI
from pubs import content, endecoder
from pubs.config import load_conf
from pubs.repo import Repository
from pubs.events import ModifyEvent

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

        wofi_options = ["--allow-markup", "--insensitive", r"-Ddmenu-separator=\\0"]

        self._wofi = Wofi(width=1200, rofi_args=wofi_options)

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

        wofi = self._wofi
        selected = wofi.select("Literature", menu_entries, keep_newlines=True)

        if selected[0] != -1:
            citekey = keys[selected[0]]
            self.menu_reference(repo, citekey)

    def menu_reference(self, repo, citekey):
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
            ("", "Back"),
            ("", "More actions"),
        ]

        menu_str = "".join(f"{ico}\t <b>{opt}</b>\0" for ico, opt in menu_)
        menu_str += "\0"

        paper_info = self._get_reference_info(repo, citekey)

        wofi_disp = menu_str + paper_info

        wofi = self._wofi
        wofi.width = 800

        selected = wofi.select("...", wofi_disp, keep_newlines=True)

        option = menu_[selected[0]][1]

        if option == "Open":
            self._open_doc(repo, citekey)
        elif option == "Back":
            self.menu_main()
        elif option == "Edit":
            self._edit_bib(repo, citekey)
        elif option == "Export":
            pass
        elif option == "Send to DPT-RP1":
            pass

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

    def _get_reference_info(self, repo, citekey):
        """Generate content of the reference menu.

        Parameters
        ----------
        repo : TODO
        citekey : TODO

        Returns
        -------
        TODO

        """
        paper = repo.pull_paper(citekey)
        bibdata = paper.bibdata

        if "author" in bibdata:
            author = "; ".join(bibdata["author"])
        else:
            author = "; ".join(bibdata["editor"])

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
            entry = (f" <tt><b>{au:<11}</b></tt>\t {author}\0" +
                     f" <tt><b>{ti:<11}</b></tt>\t {title}\0" +
                     f" <tt><b>{ye:<11}</b></tt>\t {year}\0")
        else:
            entry = (f" <tt><b>{au:<11}</b></tt>\t {author}\0" +
                     f" <tt><b>{ti:<11}</b></tt>\t {title}\0" +
                     f" <tt><b>{su:<11}</b></tt>\t {sub}\0" +
                     f" <tt><b>{ye:<11}</b></tt>\t {year}\0")

        return entry

    def _open_doc(self, repo, citekey):
        """Open pdf file.

        Parameters
        ----------
        repo : TODO
        citekey : TODO

        Returns
        -------
        TODO

        """
        paper = repo.pull_paper(citekey)

        docpath = content.system_path(repo.databroker.real_docpath(paper.docpath))
        cmd = self._pdfviewer.split()
        cmd.append(docpath)
        subprocess.Popen(cmd)

        return 1

    def _edit_bib(self, repo, citekey):
        """Edit bibfile corresponding to the citekey.

        Parameters
        ----------
        repo : TODO
        citekey : TODO

        Returns
        -------
        TODO

        """
        paper = repo.pull_paper(citekey)
        coder = EnDecoder()
        encode = coder.encode_bibdata
        decode = coder.decode_bibdata
        suffix = '.bib'
        raw_content = encode(paper.bibentry)

        ui = InputUI(repo.conf)
        ui.editor = self._terminal + " -vv -t 'Pubs edit' -e nvim"

        while True:
            # Get new content from user
            raw_content = ui.editor_input(initial=raw_content, suffix=suffix)
            # Parse new content
            try:
                content = decode(raw_content)

                new_paper = Paper.from_bibentry(content,
                                                metadata=paper.metadata)
                if repo.rename_paper(new_paper, old_citekey=paper.citekey):
                    ui.info(('Paper `{}` was successfully edited and renamed '
                             'as `{}`.'.format(citekey, new_paper.citekey)))
                else:
                    ui.info(('Paper `{}` was successfully edited.'.format(
                        citekey)))
                break

            except coder.BibDecodingError:
                if not ui.input_yn(question="Error parsing bibdata. Edit again?"):
                    ui.error("Aborting, paper not updated.")
                    ui.exit()

            except repo.CiteKeyCollision:
                options = ['overwrite', 'edit again', 'abort']
                choice = options[ui.input_choice(
                    options, ['o', 'e', 'a'],
                    question='A paper already exists with this citekey.'
                )]

                if choice == 'abort':
                    break
                elif choice == 'overwrite':
                    paper = repo.push_paper(paper, overwrite=True)
                    ui.info(('Paper `{}` was overwritten.'.format(citekey)))
                    break
                # else edit again
            # Also handle malformed bibtex and metadata

        ModifyEvent(citekey, "bibtex").send()
        repo.close()


class EditArgs:
    citekey: str
    meta: str = None

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
