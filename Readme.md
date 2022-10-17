# Wofi-pubs

Wofi-pubs is a [wofi](https://hg.sr.ht/~scoopta/wofi) interface for the [pubs](https://github.com/pubs/pubs/) bibliography manager.
It allows to comfortably search for publications by filtering the entries as you type, and then apply different actions to a selected entry.

I mainly created this script to easily display the bibliographies managed by different `pubs` configuration files, since I wanted to keep different topics separated in different git repos.
This is possible with `pubs` by running `pubs` with the `-c` argument, in order to choose a different configuration file.
You could improve that with aliases I guess... or you could write a wofi interface to deal with it and add some other functionalities along the way :).
That is wofi-pubs!

![Wofi-pubs](imgs/screenshot_01.png)

Currently wofi-pubs has the following features:

* List references from different libraries
* Add references by different methods (DOI, bibfile, Arxiv, ISBN and manual entry)
* Open documents
* Edit references
* Edit metadata of the PDF-files after importing them
* Add tags
* Filter by tags
* Export reference in bibtex-format
* Send reference and document per E-mail
* Send the document to your Sony DPT-RP1

## Requirements

* [wofi](https://hg.sr.ht/~scoopta/wofi)
* [pubs](https://github.com/pubs/pubs/)
* [dpt-rp1-py](https://github.com/pierrecollignon/dpt-rp1-py) (Optional: to send files to Sony DPT-RP1)

## Installation

```bash
git clone https://github.com/cristobaltapia/wofi-pubs.git
cd wofi-pubs
make install
```

The default installation path for `wofi-pubs` is `~/.local/bin/wofi-pubs`, while the rest of the needed files is installed under `~/.local/lib/wofi-pubs/`.
These directories can be modified with the environmental variables `INSTALL_BIN` and `INSTALL_LIB`, respectively.

## Configuration

Wofi-pubs reads a configuration file in `$XDG_CONFIG_HOME/wofi-pubs/config` (normally defined as `~/.config/wofi-pubs/config`).
The configuration file has the following syntax and options:

```conf
pdfviewer=zathura
wofi=/path/to/wofi # default: /usr/bin/wofi
pubs=/path/to/pubs # default: /usr/bin/pubs
# Directory where to look for the pubs config files for different libraries
configs_dir=$HOME/.config/pubs
default_lib=$HOME/.config/pubs/main_library.conf
terminal_edit=termite
```

## Usage

Wofi-pubs is divided into a server and a client application.
This allows the presentation of the library much faster, as the server side has pre-cached all the information in the background.
To start the server run:

```sh
wofi-pubs-server
```

A systemd unit is also provided and can be started as:

```sh
systemctl --user enable wofi-pubs-server.service
systemctl --user start wofi-pubs-server.service
```

Once the server side is up and running the client can be started with

```sh
wofi-pubs
```

Map this command to whatever keyboard combination as you like.
In Sway I use `Ctrl+Shift+p` as

```
bindsym $mod+Shift+p exec wofi-pubs
```

### Configuration to send files to Sony DPT-RP1

A file has to be created under `~/.dappp/devices` listing different possible addresses to find the DPT-RP1, with the syntax `name: address` as:

```
WiFi: 192.168.1.101
Bluetooth: 172.25.47.1
```

Any number of entries are allowed here.
Wofi-pubs will ask where to send the file based on the entries in this list.
