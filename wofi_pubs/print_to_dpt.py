import re
import subprocess
import sys
import unicodedata
from pathlib import Path, PurePath
from os.path import expanduser

from dptrp1.dptrp1 import DigitalPaper

HOME = Path.home()

# Default paths for the deviceid and privatekey files
DPT_ID = HOME / ".dpapp/deviceid.dat"
DPT_KEY = HOME / ".dpapp/privatekey.dat"

# Define folder structure for each type of document
OUT_DEF = {
    "article": {
        "out_folder": "Articles",
        "out_name": [["year", "title", "subtitle"], ["year", "title"]],
    },
    "report": {
        "out_folder": "Reports",
        "out_name": [["year", "title"]]
    },
    "techreport": {
        "out_folder": "Reports",
        "out_name": [["year", "title"]]
    },
    "inproceedings": {
        "out_folder": "Proceedings",
        "out_name": [["year", "title"]]
    },
    "book": {
        "out_folder": "Books",
        "out_name": [["year", "title"]]
    },
    "inbook": {
        "out_folder": "Articles",
        "out_name": [["year", "title", "subtitle"], ["year", "title"]],
    },
    "conference": {
        "out_folder": "Proceedings",
        "out_name": [["year", "title"]]
    },
    "standard": {
        "out_folder": "Standards",
        "out_name": [["year", "key", "title"]]
    },
    "misc": {
        "out_folder": "Standards",
        "out_name": [["year", "key", "title"]]
    },
    "phdthesis": {
        "out_folder": "Thesis",
        "out_name": [["year", "author", "title"]]
    },
    "mastersthesis": {
        "out_folder": "Thesis",
        "out_name": [["year", "author", "title"]],
    },
}


class Document(object):
    """A class describing a document in the pubs library.

    It is used to upload the file to the DPT-RP1, as well as for downloading
    notes and annotations to the original file.

    Arguments
    ----------
    key : TODO
    repo : TODO

    """
    def __init__(self, key, repo, lib_name):
        self._key = key
        self._repo = repo
        self._dpt_dir: str  # Remote directory
        self._bib = repo.databroker.pull_bibentry(self._key)
        self._lib_name = lib_name

    def to_dptrp1(self, dpt):
        """Send the document to the DPT-RP1

        A specific file structure is respected.

        Parameters
        ----------
        dpt : `obj`:DigitalPaper


        """
        repo = self._repo
        key = self._key

        docpath = repo.pull_docpath(key)
        if docpath is not None:
            local_path = expanduser(repo.pull_docpath(key))
        else:
            print("No document!")
            return 1

        target_folder = self._get_target_folder()
        name_file = self._gen_file_name()
        remote_path = target_folder / name_file

        dpt.new_folder(target_folder)

        with open(local_path, "rb") as fh:
            dpt.upload(fh, str(remote_path))

        return remote_path

    def get_annotations(self, dpt):
        """Get pdf file with the annotations.

        If such a file has been previously downloaded, see whether there
        are any changes first.

        Parameters
        ----------
        dpt : TODO


        """
        pass

    def get_notes(self, dpt):
        """Get notes associated with the document.

        If such a file has been previously downloaded, see whether there
        are any changes first.

        Parameters
        ----------
        dpt : DPTRP1 object

        """
        pass

    def _is_annotated(self):
        """TODO: Docstring for _is_annotated.
        Returns
        -------
        TODO

        """
        pass

    def _exist_note(self):
        """TODO: Docstring for _exist_note.
        Returns
        -------
        TODO

        """
        pass

    def _get_target_folder(self):
        """Get the forlder where to save the document

        Returns
        -------
        Path :
            Target directory in DPT-RP1

        """
        key = self._key
        d_type = self._bib[key]["ENTRYTYPE"]

        # Define name of the target folder
        if self._lib_name in [None, "main_library"]:
            t_folder = "Document/" + OUT_DEF[d_type]["out_folder"]
        else:
            t_folder = "Document/" + self._lib_name.capitalize()

        return PurePath(t_folder)

    def _gen_file_name(self):
        """TODO: Docstring for gen_file_name.

        Returns
        -------
        Path :
            Generate a name for the file to be sent to the DPT-RP1

        """
        key = self._key
        d_type = self._bib[key]["ENTRYTYPE"]

        # Define name of the target file
        name_format = OUT_DEF[d_type]["out_name"]

        entry = self._bib[key]

        # Define out folder
        for struct in name_format:
            try:
                out_name = "".join(slugify(entry[ix]) + "_" for ix in struct)
                break
            except:
                pass

        return PurePath(out_name + ".pdf")


def connect_to_dpt(addr, dev_id=DPT_ID, dev_key=DPT_KEY):
    """Load the key and client ID to authenticate with the DPT-RP1."""

    with open(dev_id) as f:
        client_id = f.readline().strip()

    with open(dev_key) as f:
        key = f.read()

    dpt = DigitalPaper(addr)
    dpt.authenticate(client_id, key)

    return dpt


def slugify(value):
    """
    Normalizes string, converts to lowercase and converts spaces to hyphens.
    """
    # value = (unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii"))
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def to_dpt(repo, citekey, addr):
    # Get the DPT IP address
    try:
        dpt_obj = connect_to_dpt(addr)
    except OSError:
        print("Unable to reach device, verify it is connected to the same network segment.")
        sys.exit(1)

    # FIXME
    lib_path = repo.conf["main"]["pubsdir"]
    m = re.search("(?<=/)[^/]+$", lib_path)
    lib_name = m.group(0)

    # Create document
    doc = Document(key=citekey, repo=repo, lib_name=lib_name)

    remote_path = doc.to_dptrp1(dpt_obj)

    return remote_path

def show_sent_file(notification: str, action_name, data):
    """Show document in device.

    Parameters
    ----------
    notification :
    action_name : str
        Action on the notification
    data :
        Data passed to the notification.

    """
    addr = data[0]
    remote_path = data[1]

    try:
        dpt_obj = connect_to_dpt(addr)
    except OSError:
        print("Unable to reach device, verify it is connected to the same network segment.")
        sys.exit(1)

    info = dpt_obj.list_document_info(remote_path.__bytes__())
    dpt_obj.display_document(info["entry_id"], 1)


def sync_annotated_docs(args):
    # Get the DPT IP address
    addr = args.addr

    try:
        dpt_obj = connect_to_dpt(addr)
    except OSError:
        print("Unable to reach device, verify it is connected to the same network segment.")
        sys.exit(1)


def get_dptrp1_addr():
    sp = subprocess.run(["avahi-resolve", "-4", "-n", "digitalpaper.local"],
                        stdout=subprocess.PIPE)
    stdout = sp.stdout.decode("UTF-8")
    m = re.search("\\t[0-9\.]+\\n", stdout)
    try:
        addr = m.group()[1:-1]
    except:
        addr = None

    return addr
