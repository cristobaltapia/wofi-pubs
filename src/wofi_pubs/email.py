import subprocess
from os.path import expanduser

from pubs import endecoder


class Document(object):
    """A class describing a document in the pubs library.

    Arguments
    ----------
    key : TODO
    repo : TODO

    """
    def __init__(self, key, repo):
        self._key = key
        self._repo = repo
        self._dpt_dir: str  # Remote directory
        self._bib = repo.databroker.pull_bibentry(self._key)

    def send_mail(self):
        """Send the reference per E-mail"""
        repo = self._repo
        key = self._key
        local_path = expanduser(repo.pull_docpath(key))

        bib_file = repo.databroker.pull_bibentry(key)
        #  content = pprint.pformat(bib_file[key])

        exporter = endecoder.EnDecoder()
        content = exporter.encode_bibdata(bib_file, [])

        # List of reserved characters in RFC 2396
        reserved = {
            " ": "%20",
            "&": "%26",
            ";": "%3B",
            "@": "%40",
            "/": "%2F",
            "?": "%3F",
            ":": "%3A",
            "=": "%3D",
            "+": "%2B",
            "$": "%24",
            ",": "%2C",
        }

        for k, v in reserved.items():
            content = content.replace(k, v)

        subprocess.run([
            "evolution",
            (f"mailto:?subject=Reference for {key}&body=" + content + "&attach=" +
             local_path),
            "--name='Send Pubs reference'",
        ])


def send_doc_per_mail(repo, citekey):
    # Create document
    doc = Document(key=citekey, repo=repo)
    doc.send_mail()
