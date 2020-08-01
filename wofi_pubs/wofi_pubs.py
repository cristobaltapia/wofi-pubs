#!/usr/bin/env python3
import argparse
import configparser
import os
import subprocess
import sys
from itertools import chain
from os.path import expandvars

from pubs import content, endecoder, events, plugins, uis
from pubs.commands.add_cmd import command as add_cmd
from pubs.commands.edit_cmd import command as edit_cmd
from pubs.config import load_conf
from pubs.endecoder import EnDecoder
from pubs.events import ModifyEvent
from pubs.paper import Paper
from pubs.repo import Repository
from pubs.uis import InputUI, PrintUI, _ui, init_ui
from wofi import Wofi

from dialogs import choose_file, get_user_input

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

        wofi_options = [
            "--allow-markup",
            "--insensitive",
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
        self._wofi = conf_.get("WOFI")
        self._config_dir = expandvars(conf_.get("configs_dir"))
        self._default_lib = expandvars(conf_.get("default_lib"))
        self._cache_auth = expandvars(conf_.get("cache_auth"))
        self._cache_libs = expandvars(conf_.get("cache_libs"))
        self._terminal = conf_.get("TERMINAL_EDIT")
        self._editor = expandvars(conf_.get("editor"))

    def load_conf(self, library):
        """Load configuration file in pubs.

        Parameters
        ----------
        config : TODO

        Returns
        -------
        TODO

        """
        conf = load_conf(library)
        conf['main']['edit_cmd'] = self._editor
        conf.write()
        init_ui(conf)
        plugins.load_plugins(conf, uis._ui)

        return conf

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

        if library == "default":
            conf = self.load_conf(self._default_lib)
        else:
            conf = self.load_conf(library)

        repo = Repository(conf)

        menu_entries = self._gen_menu_entries(repo, tag)

        wofi_disp = chain(menu_str, menu_entries)

        keys = [p.citekey for p in repo.all_papers()]

        wofi = self._wofi
        wofi.width = 1200
        wofi.height = 700
        selected = wofi.select("Literature", wofi_disp, keep_newlines=True)

        if selected[0] >= len(menu_):
            citekey = keys[selected[0] - len(menu_)]
            self.menu_reference(repo, citekey, tag)
        elif selected[0] != -1 and selected[0] < len(menu_):
            option = menu_[selected[0]][1]
            if option == "Change library":
                self.menu_change_lib(library)
            elif option == "Add publication":
                self.menu_add(repo, library)
            elif option == "Search tags":
                self.menu_tags(repo, library)
            elif option == "Sync. repo(s)":
                pass
            elif option == "Show all":
                self.menu_main(library)

    def menu_reference(self, repo, citekey, tag):
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

        wofi = self._wofi_ref
        wofi.lines = 16

        selected = wofi.select("...", wofi_disp, keep_newlines=True)

        option = menu_[selected[0]][1]

        if option == "Open":
            self._open_doc(repo, citekey)
        elif option == "Back":
            self.menu_main(tag=tag)
        elif option == "Edit":
            self._edit_bib(repo, citekey)
        elif option == "Export":
            self._export_bib(repo, citekey)
        elif option == "Send to DPT-RP1":
            pass
        elif option == "Send in E-Mail":
            pass

    def menu_change_lib(self, library):
        """Present menu to change library.

        Parameters
        ----------
        library : str
            Current library

        Returns
        -------
        TODO

        """
        configs_dir = self._config_dir
        configs_files = os.listdir(configs_dir)

        wofi = self._wofi_misc
        wofi.lines = max([len(configs_files), 10])

        selected = wofi.select("...", configs_files, keep_newlines=False)

        sel_lib = self._config_dir + "/" + configs_files[selected[0]]

        # Call the main menu with the selected library
        self.menu_main(sel_lib)

    def menu_tags(self, repo, library):
        """Present menu with existing tags in the library.

        Parameters
        ----------
        repo : TODO

        Returns
        -------
        TODO

        """
        tags = list(repo.get_tags())

        wofi = self._wofi_misc
        wofi.lines = min([len(tags), 15])

        selected = wofi.select("Search tags...", tags)

        sel_tag = tags[selected[0]]

        self.menu_main(library, sel_tag)

    def menu_add(self, repo, library):
        """Menu to add a new reference.

        Parameters
        ----------
        repo : TODO

        Returns
        -------
        TODO

        """
        wofi = self._wofi_misc

        menu_ = [
            ("", "DOI"),
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

    def _gen_menu_entries(self, repo, tag):
        """Generate menu entries for the library items.

        Parameters
        ----------
        repo : TODO

        Returns
        -------
        TODO

        """

        for paper in repo.all_papers():
            if tag:
                if tag not in paper.tags:
                    continue

            bibdata = paper.bibdata
            if "author" in bibdata:
                au = "; ".join(bibdata["author"])
            elif "editor" in bibdata:
                au = "; ".join(bibdata["editor"])
            elif "key" in bibdata:
                au = bibdata["key"]
            elif "organization" in bibdata:
                au = bibdata["organization"]
            else:
                au = "N.N."

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
            entry = (f" <tt><b>{au:<11}</b></tt>\n{author}\0" +
                     f" <tt><b>{ti:<11}</b></tt>\n{title}\0" +
                     f" <tt><b>{ye:<11}</b></tt>\n{year}\0")
        else:
            entry = (f" <tt><b>{au:<11}</b></tt>\n{author}\0" +
                     f" <tt><b>{ti:<11}</b></tt>\n{title}\0" +
                     f" <tt><b>{su:<11}</b></tt>\n{sub}\0" +
                     f" <tt><b>{ye:<11}</b></tt>\n{year}\0")

        return entry

    def _add_doi(self, repo):
        """Add publication to library from DOI.

        Parameters
        ----------
        repo : `obj`:Repository


        """
        doi, doc = get_user_input("DOI:", description="Import reference by DOI")

        args = PubsArgs()
        args.doi = doi
        args.docfile = doc

        conf = repo.conf
        add_cmd(conf, args)
        events.PostCommandEvent().send()

    def _add_arxiv(self, repo):
        """Add publication to library from ArXiv.

        Parameters
        ----------
        repo : `obj`:Repository


        """
        arxiv, doc = get_user_input("ArXiv:", description="Import reference by Arxiv")

        args = PubsArgs()
        args.arxiv = arxiv
        args.docfile = doc

        conf = repo.conf
        add_cmd(conf, args)
        events.PostCommandEvent().send()

    def _add_isbn(self, repo):
        """Add publication to library from ISBN.

        Parameters
        ----------
        repo : `obj`:Repository


        """
        isbn, doc = get_user_input("ISBN:", description="Import reference by ISBN")

        args = PubsArgs()
        args.isbn = isbn
        args.docfile = doc

        conf = repo.conf
        add_cmd(conf, args)
        events.PostCommandEvent().send()

    def _add_bibfile(self, repo):
        """Add publication to library from bibfile.

        Parameters
        ----------
        repo : `obj`:Repository


        """
        bibfile, doc = choose_file(text="Bibfile:", description="Import reference from Bibfile",
                              filter="bib")

        args = PubsArgs()
        args.bibfile = bibfile
        args.docfile = doc

        conf = repo.conf
        add_cmd(conf, args)
        events.PostCommandEvent().send()

    def _add_bibfile_manual(self, repo):
        """Add publication to library by manual entry of bibfile.

        Parameters
        ----------
        repo : `obj`:Repository


        """
        tmp_bib_file = os.path.expandvars("${HOME}/.local/tmp/test.bib")
        uis._ui.edit_file(tmp_bib_file, False)

        args = PubsArgs()
        args.bibfile = tmp_bib_file

        conf = repo.conf
        add_cmd(conf, args)
        events.PostCommandEvent().send()

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
        conf = repo.conf
        args = PubsArgs()
        args.citekey = citekey
        edit_cmd(conf, args)
        events.PostCommandEvent().send()

        return 1

    def _export_bib(self, repo, citekey):
        """Export citation in bib format.

        Parameters
        ----------
        repo : TODO
        citekey : TODO

        Returns
        -------
        TODO

        """
        paper = repo.pull_paper(citekey)

        bib = dict()
        bib[citekey] = paper.bibdata

        exporter = EnDecoder()
        bibdata_raw = exporter.encode_bibdata(bib, ignore_fields=["file"])

        cmd = ["wl-copy", f"{bibdata_raw}"]
        subprocess.Popen(cmd)


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

    wofi_pubs = WofiPubs(config)
    wofi_pubs.menu_main()


if __name__ == "__main__":
    main()
