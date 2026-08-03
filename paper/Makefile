# Q2D technical report build pipeline.
#
# Draft 0.2.1 was produced on another system and shipped no build tooling. This
# reconstructs it: pandoc for the DOCX, LibreOffice for the tagged PDF, then the
# deposit checks the 0.2.1 release notes asserted by hand.
#
#   make            build docx + pdf and verify
#   make dist       assemble a checksummed source package
#   make figures    regenerate query_sequence.png from its script
#   make repro      rebuild 0.2.1 and diff against the shipped artifacts
#
# Override any variable on the command line, e.g. `make DRAFT=0.3`.

DRAFT      ?= 0.2.2
PROTOCOL   ?= 0.1
CSL        ?= chicago-author-date-17th-edition.csl
PAGES      ?=

SRC        := src
BUILD      := build
DIST       := dist
TOOLS      := tools
VENV       := .venv
PY         := $(VENV)/bin/python

STEM       := Q2D_Query-to-Data_Technical_Report_Draft_v$(DRAFT)
DOCX       := $(BUILD)/$(STEM).docx
PDF        := $(BUILD)/$(STEM).pdf
REF        := $(BUILD)/reference-v$(DRAFT).docx

MANUSCRIPT := $(SRC)/manuscript.md
BIB        := $(SRC)/references.bib
FIGURES    := $(wildcard $(SRC)/figures/*.png)
DEPS       := $(MANUSCRIPT) $(BIB) $(SRC)/$(CSL) $(SRC)/reference.docx $(FIGURES)

PKG        := $(DIST)/Q2D_Technical_Report_Draft_v$(DRAFT)_Source_Package

# LibreOffice needs an isolated profile so a running desktop instance does not
# hijack the conversion; without it --convert-to silently no-ops.
LO_PROFILE := file:///tmp/lo_q2d_profile
LO_FILTER  := pdf:writer_pdf_Export:{\
"UseTaggedPDF":{"type":"boolean","value":"true"},\
"UseLosslessCompression":{"type":"boolean","value":"true"},\
"ReduceImageResolution":{"type":"boolean","value":"false"}}

.PHONY: all docx pdf figures verify dist repro clean distclean venv tools-check

all: verify

tools-check:
	@command -v pandoc  >/dev/null || { echo "pandoc not found"; exit 1; }
	@command -v soffice >/dev/null || { echo "soffice (LibreOffice) not found"; exit 1; }

$(VENV)/bin/python:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q --upgrade pip
	$(VENV)/bin/pip install -q -r requirements.txt

venv: $(VENV)/bin/python

# ---- figures -------------------------------------------------------------
# Only query_sequence.png is generated; the other two are source assets.
figures: venv
	$(PY) $(SRC)/figures/make_sequence_figure.py

# ---- docx ----------------------------------------------------------------
$(REF): $(SRC)/reference.docx $(TOOLS)/stamp_reference.py
	@mkdir -p $(BUILD)
	python3 $(TOOLS)/stamp_reference.py $(SRC)/reference.docx $@ $(DRAFT)

$(DOCX): $(DEPS) $(REF) | tools-check
	@mkdir -p $(BUILD)
	cd $(SRC) && pandoc manuscript.md \
	  --from=markdown \
	  --to=docx \
	  --citeproc \
	  --bibliography=references.bib \
	  --csl=$(CSL) \
	  --reference-doc=../$(REF) \
	  --resource-path=. \
	  --output=../$@

docx: $(DOCX)

# ---- pdf -----------------------------------------------------------------
# LibreOffice names its output after the input stem, so the DOCX name carries.
$(PDF): $(DOCX) | tools-check
	soffice --headless --norestore -env:UserInstallation=$(LO_PROFILE) \
	  --convert-to '$(LO_FILTER)' --outdir $(BUILD) $(DOCX) >/dev/null
	@test -f $@ || { echo "PDF export produced no $@"; exit 1; }

pdf: $(PDF)

# ---- verify --------------------------------------------------------------
verify: $(DOCX) $(PDF) venv
	$(PY) $(TOOLS)/verify.py --draft $(DRAFT) --build $(BUILD) --src $(SRC) \
	  $(if $(PAGES),--pages $(PAGES),)

# ---- dist ----------------------------------------------------------------
# SHA256SUMS.txt is generated last, after every other file is in place -- the
# ordering the 0.2.1 release notes called out.
dist: verify
	rm -rf $(PKG)
	mkdir -p $(PKG)/figures
	cp $(DOCX) $(PKG)/$(STEM).docx
	cp $(PDF)  $(PKG)/$(STEM).pdf
	cp $(MANUSCRIPT) $(PKG)/$(STEM).md
	cp $(BIB) $(PKG)/Q2D_Query-to-Data_References_v$(DRAFT).bib
	cp $(SRC)/figures/*.png $(SRC)/figures/make_sequence_figure.py $(PKG)/figures/
	cp $(SRC)/package/README.txt $(PKG)/README.txt
	cp $(SRC)/package/release-notes.md $(PKG)/Q2D_Technical_Report_v$(DRAFT)_Release_Notes.md
	cd $(PKG) && find . -type f ! -name SHA256SUMS.txt | sort | xargs shasum -a 256 > SHA256SUMS.txt
	$(PY) $(TOOLS)/verify.py --draft $(DRAFT) --package $(PKG) $(if $(PAGES),--pages $(PAGES),)
	cd $(DIST) && zip -qr $(notdir $(PKG)).zip $(notdir $(PKG)) && unzip -tq $(notdir $(PKG)).zip
	@echo "package: $(PKG)"

# ---- reproducibility gate ------------------------------------------------
# Rebuilds the published draft from source and reports any drift. Body text is
# expected to match exactly; see README for the known bibliography variance.
repro: venv
	$(MAKE) DRAFT=0.2.1 PAGES=43 docx pdf
	$(PY) $(TOOLS)/compare.py \
	  Q2D_Technical_Report_Draft_v0.2.1_Source_Package/Q2D_Query-to-Data_Technical_Report_Draft_v0.2.1.docx \
	  $(BUILD)/Q2D_Query-to-Data_Technical_Report_Draft_v0.2.1.docx

clean:
	rm -rf $(BUILD)

distclean: clean
	rm -rf $(DIST) $(VENV)
