PREFIX = /usr/local
BINDIR = $(PREFIX)/bin
MANDIR = $(PREFIX)/share/man/man1
DOCDIR = $(PREFIX)/share/doc/nrrddate
BSHDIR = /etc/bash_completion.d

.PHONY: all install uninstall

all:

install:
	install -m755 -d $(BINDIR)
	install -m755 -d $(MANDIR)
	install -m755 -d $(DOCDIR)
	install -m755 -d $(BSHDIR)
	gzip -c doc/nrrddate.1 > nrrddate.1.gz
	install -m755 nrrddate/nrrddate.py $(BINDIR)/nrrddate
	install -m644 nrrddate.1.gz $(MANDIR)
	install -m644 README.md $(DOCDIR)
	install -m644 LICENSE $(DOCDIR)
	install -m644 CHANGES $(DOCDIR)
	install -m644 CONTRIBUTING.md $(DOCDIR)
	install -m644 auto-completion/bash/nrrddate-completion.bash $(BSHDIR)
	rm -f nrrddate.1.gz

uninstall:
	rm -f $(BINDIR)/nrrddate
	rm -f $(MANDIR)/nrrddate.1.gz
	rm -f $(BSHDIR)/nrrddate-completion.bash
	rm -rf $(DOCDIR)

