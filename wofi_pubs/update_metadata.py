import subprocess
from os.path import expanduser


def update_pdf_metadata(repo, citekey):
    """Update the metadata of pdf file.

    Parameters
    ----------
    repo : TODO
    citekey : TODO

    Returns
    -------
    TODO

    """
    bib = repo.databroker.pull_bibentry(citekey)[citekey]

    # Get the needed information
    if bib["type"] == "misc":
        author = bib["organization"]
        title = bib["title"]
    else:
        author = short_authors(bib)
        title = bib["title"]

    local_path = expanduser(repo.pull_docpath(citekey))

    exiftool_cmd = [
        'exiftool', f'-Title={title}', f'-Author={author}', '-Creator=',
        '-overwrite_original', local_path
    ]
    p2 = subprocess.run(exiftool_cmd, check=False)

    # p3 = subprocess.Popen(f"qpdf --linearize {local_path} tmp.pdf", shell=True)
    # p3.wait()

    # p4 = subprocess.Popen(f"mv tmp.pdf {local_path}", shell=True)
    # p4.wait()

    return 1


def short_authors(bibdata):
    try:
        authors = [p for p in bibdata["author"]]
        if len(authors) < 3:
            return "; ".join(authors)
        else:
            return authors[0] + (" et al." if len(authors) > 1 else "")
    except KeyError:  # When no author is defined
        return ""
