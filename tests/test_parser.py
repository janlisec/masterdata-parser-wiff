import base64
import json
from xml.etree import ElementTree

import pytest
from bam_masterdata.logger import logger
from bam_masterdata.metadata.entities import CollectionType

from ms_wiff.parser import MSWIFFMeasurement, MSWIFFParser, read_mswiff_measurements


class TestMSWIFFParser:
    def test_parse_creates_one_step_per_measurement(self, tmp_path):
        wiff_file = tmp_path / "example.wiff"
        wiff_file.write_bytes(b"test fixture")
        scan_file = tmp_path / "example.wiff.scan"
        scan_file.write_bytes(b"scan fixture")

        def read_measurements(path):
            assert path == wiff_file
            return [
                MSWIFFMeasurement(
                    name="MS_WIFF measurement 1",
                    spreadsheet_xml="<ms-wiff-metadata><scan>1</scan></ms-wiff-metadata>",
                ),
                MSWIFFMeasurement(
                    name="MS_WIFF measurement 2",
                    spreadsheet_xml="<ms-wiff-metadata><scan>2</scan></ms-wiff-metadata>",
                ),
            ]

        parser = MSWIFFParser(measurement_reader=read_measurements)
        collection = CollectionType()
        parser.parse([wiff_file], collection, logger)

        assert len(collection.attached_objects) == 2
        objects = list(collection.attached_objects.values())
        assert [obj.name for obj in objects] == [
            "MS_WIFF measurement 1",
            "MS_WIFF measurement 2",
        ]
        assert [obj.notes for obj in objects] == [
            "<ms-wiff-metadata><scan>1</scan></ms-wiff-metadata>",
            "<ms-wiff-metadata><scan>2</scan></ms-wiff-metadata>",
        ]
        assert [
            json.loads(
                base64.b64decode(
                    obj.experimental_step_spreadsheet.split("<DATA>")[1]
                    .split("</DATA>")[0]
                )
            )["values"]
            for obj in objects
        ] == [
            [["scan", "1"]],
            [["scan", "2"]],
        ]
        assert [obj.datasets for obj in objects] == [[], []]
        assert len(collection.relationships) == 0

    def test_parse_warns_when_companion_scan_is_missing(self, tmp_path):
        wiff_file = tmp_path / "example.wiff"
        wiff_file.write_bytes(b"test fixture")
        warnings = []

        class Logger:
            def info(self, message, **kwargs):
                pass

            def warning(self, message, **kwargs):
                warnings.append((message, kwargs))

        parser = MSWIFFParser(
            measurement_reader=lambda path: [
                MSWIFFMeasurement(name="MS_WIFF measurement")
            ]
        )
        collection = CollectionType()

        parser.parse([wiff_file], collection, Logger())

        assert warnings == [
            (
                "Companion WIFF scan file is missing.",
                {
                    "wiff_file": str(wiff_file),
                    "expected_scan_file": f"{wiff_file}.scan",
                },
            )
        ]
        assert collection.attached_objects
        assert next(iter(collection.attached_objects.values())).datasets == []

    def test_parse_rejects_non_wiff_input(self, parser, tmp_path):
        scan_file = tmp_path / "example.wiff.scan"
        collection = CollectionType()
        parser = MSWIFFParser(measurement_reader=lambda path: [])

        with pytest.raises(ValueError, match="accepts only .wiff files"):
            parser.parse([scan_file], collection, logger)

    def test_read_lc_mult_sam_fixture(self):
        measurements = list(
            read_mswiff_measurements("tests/data/LC_mult_sam.wiff")
        )

        assert len(measurements) == 7
        assert [measurement.name for measurement in measurements] == [
            "ACN_pos_Sample001",
            "ACN_pos_Sample009",
            "ACN_pos_Sample009",
            "ACN_pos_Sample009",
            "ACN_pos_Sample001",
            "ACN_pos_Sample002",
            "ACN_pos_Sample003",
        ]
        assert [
            measurement.code for measurement in measurements
        ] == [
            "MSW_ACN_POS_SAMPLE_001",
            "MSW_ACN_POS_SAMPLE_002",
            "MSW_ACN_POS_SAMPLE_003",
            "MSW_ACN_POS_SAMPLE_004",
            "MSW_ACN_POS_SAMPLE_005",
            "MSW_ACN_POS_SAMPLE_006",
            "MSW_ACN_POS_SAMPLE_007",
        ]
        metadata = ElementTree.fromstring(measurements[0].spreadsheet_xml)
        assert metadata.findtext("original-filename") == "ACN_pos.wiff"
        assert metadata.findtext("acquisition-method") == "Column_Wash_10min.dam"
        assert metadata.findtext("acquisition-batch") == "New Batch.dab"
        assert metadata.findtext("instrument") == "DW220001802"
