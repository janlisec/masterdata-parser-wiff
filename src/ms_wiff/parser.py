import base64
import ntpath
import re
import shutil
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from bam_masterdata.datamodel.object_types import ExperimentalStep
from bam_masterdata.parsing import AbstractParser
from pybis.pybis import Spreadsheet


@dataclass(frozen=True)
class MSWIFFMeasurement:
    """Normalized metadata for one measurement contained in a WIFF file."""

    name: str
    spreadsheet_xml: str = "<ms-wiff-metadata />"
    code: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    operator: str | None = None


MeasurementReader = Callable[[Path], Iterable[MSWIFFMeasurement]]


def _seven_zip_executable() -> str:
    executable = shutil.which("7z") or shutil.which("7za")
    if executable is None:
        for candidate in (
            Path(r"C:\Program Files\7-Zip\7z.exe"),
            Path(r"C:\Program Files (x86)\7-Zip\7z.exe"),
        ):
            if candidate.is_file():
                return str(candidate)
        raise RuntimeError("7-Zip is required to read MS_WIFF files but was not found.")
    return executable


def _read_wiff_member(wiff_path: Path, member: str) -> bytes:
    result = subprocess.run(
        [_seven_zip_executable(), "e", "-so", str(wiff_path), member],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError(
            f"Could not read {member!r} from WIFF file {wiff_path}: "
            f"{result.stderr.decode(errors='replace').strip()}"
        )
    return result.stdout


def _readable_strings(data: bytes) -> list[str]:
    decoded = data.decode("utf-16le", errors="ignore")
    return re.findall(r"[ -~]{3,}", decoded)


def _sample_numbers(wiff_path: Path) -> list[int]:
    result = subprocess.run(
        [_seven_zip_executable(), "l", "-slt", str(wiff_path)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise ValueError(
            f"Could not list WIFF file {wiff_path}: {result.stderr.strip()}"
        )
    pattern = re.compile(r"^Path = SampleSubtree\\Sample(\d+)$", re.MULTILINE)
    return sorted({int(match.group(1)) for match in pattern.finditer(result.stdout)})


def _metadata_xml(
    *,
    original_filename: str,
    measurement_name: str,
    acquisition_method: str | None,
    acquisition_batch: str | None,
    instrument: str | None,
    workstation: str | None,
) -> str:
    root = ElementTree.Element("ms-wiff-metadata")
    values = {
        "original-filename": original_filename,
        "measurement-name": measurement_name,
        "acquisition-method": acquisition_method,
        "acquisition-batch": acquisition_batch,
        "instrument": instrument,
        "workstation": workstation,
    }
    for tag, value in values.items():
        if value:
            ElementTree.SubElement(root, tag).text = value
    return ElementTree.tostring(root, encoding="unicode")


def _metadata_spreadsheet(metadata_xml: str) -> Spreadsheet:
    metadata = ElementTree.fromstring(metadata_xml)

    rows = 10
    cols = 10
    data = [["" for _ in range(cols)] for _ in range(rows)]

    for i, child in enumerate(metadata[:rows]):
        data[i][0] = child.tag
        data[i][1] = child.text or ""

    spreadsheet = Spreadsheet(columns=cols, rows=rows)
    spreadsheet.data = data
    spreadsheet.values = data
    spreadsheet.style = {
        f"{col}{row}": "text-align: center;"
        for row in range(1, rows + 1)
        for col in spreadsheet.headers
    }
    spreadsheet.meta = None
    spreadsheet.width = [50] * cols

    return spreadsheet


def _object_code(filename_stem: str, sample_number: int) -> str:
    normalized_stem = re.sub(r"[^A-Za-z0-9]+", "_", filename_stem).strip("_")
    return f"MSW_{normalized_stem.upper()}_SAMPLE_{sample_number:03d}"


def read_mswiff_measurements(wiff_path: Path) -> Iterable[MSWIFFMeasurement]:
    """Extract one normalized measurement from each WIFF sample subtree."""

    wiff_path = Path(wiff_path)
    file_strings = _readable_strings(_read_wiff_member(wiff_path, "FileRec_Str"))
    original_path = next(
        (value for value in file_strings if re.search(r"(?i)\.wiff$", value)),
        None,
    )
    if original_path is None:
        raise ValueError(f"Original WIFF filename not found in {wiff_path}.")
    original_filename = ntpath.basename(original_path)
    filename_stem = ntpath.splitext(original_filename)[0]

    for sample_number in _sample_numbers(wiff_path):
        prefix = f"SampleSubtree\\Sample{sample_number}\\SampleDABE"
        cfr_strings = _readable_strings(
            _read_wiff_member(wiff_path, f"{prefix}\\CFR_INFO")
        )
        data_strings = _readable_strings(
            _read_wiff_member(wiff_path, f"{prefix}\\DATA")
        )
        if not data_strings:
            raise ValueError(
                f"Measurement name not found for Sample{sample_number} "
                f"in WIFF file {wiff_path}."
            )

        paths = [
            path
            for value in cfr_strings
            for path in re.findall(
                r"[A-Za-z]:\\.*?\\([^\\]+?\.(?:dam|dab|bat))",
                value,
                re.IGNORECASE,
            )
        ]
        method = next(
            (ntpath.basename(path) for path in paths if path.lower().endswith(".dam")),
            None,
        )
        batch = next(
            (
                ntpath.basename(path)
                for path in paths
                if path.lower().endswith((".dab", ".bat"))
            ),
            None,
        )
        device_match = next(
            (re.search(r"\$([^\\$]+)\\(DW\d+)", value) for value in cfr_strings),
            None,
        )
        instrument = device_match.group(2) if device_match else None
        workstation = device_match.group(1) if device_match else None
        measurement_name = data_strings[0]
        full_name = f"{filename_stem}_{measurement_name}"
        yield MSWIFFMeasurement(
            name=full_name,
            spreadsheet_xml=_metadata_xml(
                original_filename=original_filename,
                measurement_name=measurement_name,
                acquisition_method=method,
                acquisition_batch=batch,
                instrument=instrument,
                workstation=workstation,
            ),
            code=_object_code(filename_stem, sample_number),
        )


class MSWIFFParser(AbstractParser):
    """Create one ExperimentalStep for each measurement in a WIFF file.

    The source WIFF and its optional ``.wiff.scan`` companion are attached as
    object-level datasets. Until the host supports sharing one dataset between
    several objects, a multi-measurement WIFF attaches the pair to each step.
    """

    def __init__(self, measurement_reader: MeasurementReader | None = None):
        self._measurement_reader = measurement_reader or read_mswiff_measurements

    def parse(self, files, collection, logger):
        for file_path in files:
            path = Path(file_path)
            if path.suffix.lower() != ".wiff":
                raise ValueError(
                    f"MSWIFFParser accepts only .wiff files, got {path.name!r}"
                )

            scan_path = Path(f"{path}.scan")
            if not scan_path.is_file():
                logger.warning(
                    "Companion WIFF scan file is missing.",
                    wiff_file=str(path),
                    expected_scan_file=str(scan_path),
                )

            measurements = list(self._measurement_reader(path))
            logger.info(
                "Parsed WIFF file.",
                file_path=str(path),
                measurement_count=len(measurements),
            )

            for measurement in measurements:
                properties = {
                    "name": measurement.name,
                    "notes": measurement.spreadsheet_xml,
                    "experimental_step_spreadsheet": _metadata_spreadsheet(
                        measurement.spreadsheet_xml
                    ),
                }
                if measurement.code is not None:
                    properties["code"] = measurement.code
                if measurement.start_date is not None:
                    properties["start_date"] = measurement.start_date
                if measurement.end_date is not None:
                    properties["end_date"] = measurement.end_date
                if measurement.operator is not None:
                    properties["operator"] = measurement.operator
                collection.add(ExperimentalStep(**properties))
