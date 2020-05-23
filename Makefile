.PHONY: install uninstall

INSTALL_BIN?=${HOME}/.local/bin
INSTALL_LIB?=${HOME}/.local/lib/wofi-pubs

install:
	@echo "Installing wofi-pubs..."
	@echo "  -> Creating directories..."
	mkdir -p $(INSTALL_LIB)
	mkdir -p $(XDG_CONFIG_HOME)/wofi-pubs
	@echo "  -> Installing files..."
	install wofi-pubs $(INSTALL_BIN)/wofi-pubs
	install parse-bib-file $(INSTALL_LIB)/parse-bib-file
	install pubs_to_dptrp1 $(INSTALL_LIB)/pubs_to_dptrp1
	install make_writable $(INSTALL_LIB)/make_writable
	install update_pdf_meta $(INSTALL_LIB)/update_pdf_meta
	install pubs-utils $(INSTALL_LIB)/pubs-utils
	@echo "  -> Giving execution permission to the scripts..."
	chmod +x $(INSTALL_BIN)/wofi-pubs
	chmod +x $(INSTALL_LIB)/parse-bib-file
	chmod +x $(INSTALL_LIB)/pubs_to_dptrp1
	chmod +x $(INSTALL_LIB)/make_writable
	chmod +x $(INSTALL_LIB)/update_pdf_meta
	chmod +x $(INSTALL_LIB)/pubs-utils
	@echo "Configuring installation paths..."
	sed -i 's;^BIB_PARSE=.*$$;BIB_PARSE=$(INSTALL_LIB)/parse-bib-file;' $(INSTALL_BIN)/wofi-pubs
	sed -i 's;^PUBS_TO_DPT=.*$$;PUBS_TO_DPT=$(INSTALL_LIB)/pubs_to_dptrp1;' $(INSTALL_BIN)/wofi-pubs
	sed -i 's;^PUBS_UTILS=.*$$;PUBS_UTILS=$(INSTALL_LIB)/pubs-utils;' $(INSTALL_BIN)/wofi-pubs
	sed -i 's;^UPDATE_METADATA=.*$$;UPDATE_METADATA=$(INSTALL_LIB)/update_pdf_meta;' $(INSTALL_BIN)/wofi-pubs
	sed -i 's;^REMOVE_PROTECTION=.*$$;REMOVE_PROTECTION=$(INSTALL_LIB)/remove_write_protection;' $(INSTALL_BIN)/wofi-pubs
	@echo "Done!"

uninstall:
	rm $(INSTALL_BIN)/wofi-pubs
	rm $(INSTALL_LIB)/parse-bib-file
	rm $(INSTALL_LIB)/pubs_to_dptrp1
	rm $(INSTALL_LIB)/make_writable
	rm $(INSTALL_LIB)/update_pdf_meta
	rm -r $(INSTALL_LIB)

