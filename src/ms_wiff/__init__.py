from .parser import MSWIFFMeasurement, MSWIFFParser

ms_wiff_entry_point = {
    "name": "MS_WIFF",
    "description": (
        "Parse Sciex MS_WIFF files into one ExperimentalStep per measurement."
    ),
    "parser_class": MSWIFFParser,
}

__all__ = ["MSWIFFMeasurement", "MSWIFFParser", "ms_wiff_entry_point"]
