# Agent guidance

## Project purpose

This repository is intended to become a `bam-masterdata` parser for Sciex
WIFF-file uploads to the BAM openBIS data store. It was created from the
openBIS parser example template and currently contains placeholder behavior.
Do not assume the current `ExperimentalStep` objects are the final data model.

## Structured project context

```yaml
project:
  repository: janlisec/masterdata-parser-wiff
  source_template: openBIS parser example
  target: Sciex WIFF-file upload to BAM openBIS
  current_status: placeholder parser; WIFF requirements still need discovery

related_project:
  repository: janlisec/instruments_1.7-parser
  relevant_commit: 55e91a1
  relationship: similar bam-masterdata parser and upload workflow

known_parser_conventions:
  object_type_column: OBJECT_TYPE
  legacy_object_type_column: CODE
  object_identifier_column: OBJECT_CODE
  object_identifier_alias: $CODE
  existing_object_behavior: update by openBIS object code
  missing_object_behavior: create
  duplicate_detection: openBIS object code only

validation:
  tests: python -m pytest -q
  lint: ruff check .

workflow:
  inspect_before_editing: true
  add_tests_for_behavior_changes: true
  keep_changes_surgical: true
  avoid_credentials_in_repository: true
```

## Parser-authoring contract

The upstream parser-authoring guide
(`https://bamresearch.github.io/bam-masterdata/howtos/parsing/create_new_parsers/`)
defines the integration points that must remain valid while this repository is
customized:

- Implement a parser class inheriting from `bam_masterdata.parsing.AbstractParser`
  with the `parse(files, collection, logger)` signature.
- Keep source-file reading and normalization separate from construction of
  `bam-masterdata` objects where practical.
- Add objects with `collection.add(...)`, retain the returned IDs, and create
  relationships with the collection's relationship API.
- Expose an entry-point dictionary from the package `__init__.py`, including a
  user-facing name, description, and parser class.
- Register that dictionary under the `bam.parsers` entry-point group in
  `pyproject.toml`; this is how `openbis-upload-helper` discovers installed
  parsers.
- When renaming the template, update the package directory, imports, entry
  point variable, project metadata, URLs, setuptools-scm target, and tests
  together. Verify installation and entry-point discovery after the rename.
- Document installation, supported input, invocation, and release expectations
  in `README.md` once the WIFF behavior is defined.

Use the actual installed `bam-masterdata` API as the source of truth for
method names and object types. In particular, the current template uses
`collection.add_relationship(parent_id, child_id)`; do not copy inconsistent
method names from examples without checking the dependency version.

## BAM Masterdata model and parser workflow

The getting-started and parsing tutorials establish the following model and
runtime behavior:

- `bam-masterdata` models four related concepts: object types, collection
  types, dataset types, and vocabulary types. Object types represent physical
  or conceptual entities; collections group objects and relationships; datasets
  represent attached data files; vocabularies constrain standardized values.
- Object-type `defs` describe the schema, while assigned properties hold parsed
  values. Inspect the selected `bam-masterdata` version's object-type classes
  and `_property_metadata` before choosing a WIFF representation or assigning
  fields. Do not invent properties that are not present in the installed
  schema.
- Respect the declared openBIS/Python value types: for example, `DATE` maps to
  `datetime.date`, `TIMESTAMP` to `datetime.datetime`, `BOOLEAN` to `bool`,
  `INTEGER` to `int`, `REAL` to `float`, and `OBJECT` to an object instance or
  an openBIS path string. Invalid assignments should fail visibly and be
  covered by focused tests.
- Controlled-vocabulary properties must receive valid vocabulary term codes.
  Inspect the corresponding vocabulary type rather than accepting arbitrary
  source strings; define an explicit normalization or error path for unknown
  WIFF values.
- Distinguish semantic object-property references from structural
  parent-child relationships. Assign an `OBJECT` property when the schema says
  one object refers to another; use `collection.add_relationship(...)` for
  input/output or hierarchy links. An object instance used as a reference must
  have its `code` set. Existing objects can alternatively be referenced by a
  validated openBIS path with three or four path components.
- The local parser contract should be testable without an openBIS connection:
  instantiate a `CollectionType`, call `parse(...)`, and inspect
  `attached_objects` and `relationships`. Keep network upload tests separate
  from parser unit tests.
- `run_parser()` accepts a mapping of parser instances to file lists, invokes
  each parser, creates or retrieves the target space/project/collection,
  creates the parsed objects, uploads input files as datasets, and maps
  relationships. Never place credentials, tokens, or private instance URLs in
  source or tests.
- The documented default collection type is `"COLLECTION"`. Avoid introducing
  new dependencies on collection or dataset type development: the tutorials
  state that new types are currently discouraged and the collection concept
  may be deprecated in future openBIS releases.

## Current MS_WIFF implementation boundary

- The package identity and `bam.parsers` entry point are now MS_WIFF-specific.
- `MSWIFFParser` models each normalized measurement as one
  `ExperimentalStep`, allowing one WIFF file to produce one or many objects.
- The raw WIFF file remains an input to the host upload workflow and is not
  embedded in the `ExperimentalStep`.
- Accept only `.wiff` parser inputs. For each input, check for the exact
  companion path `<wiff_path>.scan` (for example,
  `LC_mult_sam.wiff.scan`), warn when it is missing, and do not silently
  treat a `.scan` file as a primary input.
- Do not attach datasets from the parser on repeated metadata updates. The
  parser preserves existing WIFF attachments and avoids creating duplicate
  datasets; dataset ingestion needs a separate first-upload workflow.
- The non-confidential WIFF fixtures in `tests/data/` are intentional repository
  test data. Preserve them and use them for reader integration and regression
  tests; do not add confidential or unsanitized customer data.
- WIFF binary extraction is intentionally injected through a measurement-reader
  callable for isolated tests, while the default reader currently uses the
  7-Zip-readable compound-container structure.
- The default reader enumerates `SampleSubtree\SampleN` and reads only
  `FileRec_Str`, `SampleDABE\CFR_INFO`, and `SampleDABE\DATA`. It decodes
  embedded UTF-16LE strings and writes the extracted metadata as valid XML.
  It assigns stable object codes from the original filename and sample number
  so repeated measurement names remain separate openBIS objects.
  The web-tool host must provide `7z` or `7za`.
- The interim structured metadata container is the
  `ExperimentalStep.notes` XML property. Do not write raw XML to
  `experimental_step_spreadsheet`; the host expects a separately encoded
  spreadsheet representation there.
- The spreadsheet representation uses the web-tool JSON grid structure with
  `headers`, `data`, `style`, `meta`, `width`, and `values`.

## Next implementation sequence

Before adding WIFF-specific code, follow this order:

1. Decide the WIFF-to-openBIS mapping: supported WIFF versions and metadata,
   object types, properties, object references, parent-child relationships,
   stable codes, and whether the raw WIFF is represented only as an uploaded
   dataset or also by metadata objects.
2. Rename the template package and parser identity to `ms_wiff`. Update the
   package directory, imports, entry-point variable, `pyproject.toml` metadata
   and URLs, setuptools-scm target, and tests together.
3. Implement a minimal real parser with the required
   `parse(files, collection, logger)` signature. Keep WIFF reading and
   normalization separate from `bam-masterdata` object construction, validate
   unsupported or malformed input explicitly, and avoid UI or openBIS
   authentication logic in the parser package.
4. Replace the placeholder tests with focused WIFF tests covering parsing,
   metadata, stable codes, object references, relationships, unsupported
   input, malformed files, and entry-point discovery.
5. Verify installation, entry-point discovery, targeted tests, and the full
   configured checks before publishing the package for use by the web tool.

## Installed object-type inventory

The project virtual environment currently resolves `bam-masterdata==0.13.1`.
The 75 concrete object types exposed by
`bam_masterdata.datamodel.object_types` are:

`Action`, `Aluminium`, `Amorphous`, `AuxiliaryMaterial`, `Bam`,
`BamGentechFacility`, `BamLaboratory`, `Calibration`, `Chemical`,
`ComputationalAnalysis`, `CondaEnvironment`, `Control`, `Crystal`,
`DeviceTraining`, `DeviceUsage`, `Document`, `Entry`,
`EnvironmentalConditions`, `ExperimentalStep`, `Fcg`, `Freezer1`, `GasBottle`,
`GeneralElnSettings`, `GeneralProtocol`, `GlassWare`, `Gmo`, `GmoDonor`,
`GmoRecipient`, `Hpc`, `Instrument`, `InstrumentAccessory`,
`InteratomicPotential`, `IrCameraAcquisition`, `JupyterNotebook`, `Lammps`,
`MatSimStructure`, `MaterialV1`, `MsCenter`, `Murnaghan`, `Named`, `Order`,
`Organism`, `Outdoor`, `ParameterSet`, `Person`, `Plasmid`, `Product`,
`Project`, `Pseudopotential`, `Publication`, `PyironJob`, `RawMaterialCode`,
`Request`, `Sample`, `SampleHolder`, `SampleNdt`, `SamplePretreatment`,
`SearchQuery`, `SoftwareCode`, `Sop`, `SpecificPersonInfo`, `Steel`, `Storage`,
`StorageConnector`, `StoragePosition`, `Supplier`, `Task`, `Technikum`, `Test`,
`TestObject`, `TestingMachine`, `ThermographyHeating`, `ThermographySetup`,
`Vasp`, and `WorkflowReference`.

This inventory is evidence for the current lockfile/environment, not a
guarantee for future dependency versions. Re-check it after dependency
upgrades. For WIFF, inspect the installed property metadata before deciding
among likely candidates such as `Instrument`, `Sample`, `ExperimentalStep`,
`Test`, `Document`, `SoftwareCode`, `ComputationalAnalysis`, and
`ParameterSet`; do not force all file metadata into one type if the domain
requires several linked objects.

## Implementation guidance

- Inspect the existing `bam-masterdata` version and its object types before
  selecting the WIFF representation.
- Determine whether WIFF input should produce objects, datasets, files,
  relationships, or a combination of these.
- Confirm the expected WIFF reader/library and its supported Python versions
  before adding dependencies.
- Keep source-file parsing separate from openBIS object construction so both
  can be tested independently.
- Preserve stable openBIS object codes when updating existing records.
- Surface malformed input and unsupported files explicitly; do not silently
  skip failures.
- Add focused tests for parsing, metadata mapping, object-code handling,
  relationships, unsupported input, and malformed WIFF files.

## Validation and Git practices

- Run the existing tests before and after implementation changes.
- Use the smallest relevant test or lint command while iterating, then run the
  full configured checks before committing.
- Keep commits focused and explain behavior changes in commit messages.
- Never commit openBIS credentials, tokens, private URLs, or unsanitized
  customer data.
- Do not modify unrelated user changes or generated lock files without a
  reason.

## Open questions to resolve before implementation

1. Which WIFF versions and Sciex metadata fields must be supported?
2. Which openBIS object or dataset types represent a WIFF file and its runs?
3. How should raw WIFF files be supplied to the parser and referenced after
   upload?
4. Which fields form stable object codes, and are codes supplied by Excel or
   generated by the parser?
5. Which relationships between experiments, runs, samples, and files must be
   created?
