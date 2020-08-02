#!/usr/bin/env bash
TEMPFILE=tmp.pdf
# Get a list of files in current folder
declare -a folders=$(find -iname '*.pdf' | awk \
    ' {sub(/\.\//, ""); print $0 } ')

for f in ${folders} ; do
    encrypted=$(pdfinfo "${f}" | awk \
        ' /Encrypted/ { printf "%s\n", $2 } ')

    if [[ $encrypted == "yes" ]]; then
        qpdf --decrypt "${f}" $TEMPFILE
        mv $TEMPFILE "${f}"
    fi
done
