# MS_WIFF parser

Parser plugin for Sciex mass-spectrometry WIFF files using the
`bam-masterdata` parser interface.

## Current behavior

The parser represents each measurement contained in a WIFF file as one
`ExperimentalStep` object. A single WIFF file may therefore produce one or
many objects. The normalized measurement metadata is stored in the object's
`notes` property as XML and in the spreadsheet property using openBIS's
`<SPREADSHEET><DATA>base64(JSON)</DATA></SPREADSHEET>` representation.

The parser accepts only `.wiff` inputs. For every selected WIFF file it checks
for a companion scan file with the exact name `<file>.wiff.scan` (for example,
`LC_mult_sam.wiff.scan`) and warns if it is missing. The parser does not attach
files during metadata updates, preventing repeated runs from creating duplicate
datasets; existing attachments are left unchanged.

Existing file attachments are preserved, but the parser does not attach files
during repeated metadata updates. Initial dataset ingestion needs a separate
upload workflow.

The current reader treats a WIFF as a 7-Zip-readable compound container. It
enumerates `SampleSubtree\SampleN` entries and reads only the small
`SampleDABE\CFR_INFO` and `SampleDABE\DATA` records, plus the root
`FileRec_Str`. Embedded UTF-16LE strings provide the original filename,
measurement name, acquisition method, acquisition batch, instrument, and
workstation. The generated object name is
`<original-file-stem>_<measurement-name>`, and the extracted values are stored
in valid XML in `notes`, and as the web-tool spreadsheet structure in
`experimental_step_spreadsheet`. Each generated object also
gets a stable code based on the original filename and sample number, such as
`MSW_ACN_POS_SAMPLE_001`; this keeps repeated measurement names distinct.

7-Zip must be installed and available as `7z`/`7za` on the host running the
web tool. `MSWIFFParser` still accepts an injected measurement reader for
isolated tests and future reader replacement.

## Development

Create the project environment and install development dependencies:

```powershell
uv venv .venv --python 3.13
uv sync --extra dev --active --python .venv\Scripts\python.exe
```

Run the tests and lint:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
```

The package registers the `ms_wiff` entry point in the `bam.parsers` group.
The host web tool discovers installed parser plugins through this entry point.

## Example WIFF files

The repository includes non-confidential WIFF fixtures in `tests/data/` for
parser development and regression tests:

- `LC_one_sam.wiff` - liquid-chromatography WIFF with one sample.
- `LC_mult_sam.wiff` - liquid-chromatography WIFF with multiple samples.
- `DI_mult_sam.wiff` - direct-injection WIFF with multiple samples.
- Companion `.wiff.scan` files are intentionally not included because they
  exceed the repository size limit; tests must cover both present and missing
  companions.

These binary fixtures are intentionally kept in the repository because the
parser must support files that contain one or many measurements. Add tests
against them when the WIFF reader and metadata mapping are implemented.
