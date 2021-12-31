from enum import Enum


class MimeType(Enum):
    FOLDER = "application/vnd.google-apps.folder"
    SHORTCUT = "application/vnd.google-apps.shortcut"
    DOCUMENT = "application/vnd.google-apps.document"
    SPREADSHEET = "application/vnd.google-apps.spreadsheet"
    PRESENTATION = ""
    DRAWING = ""


class ExportType(Enum):
    """
    Reference: https://developers.google.com/drive/api/v3/ref-export-formats
    """

    PDF = {
        MimeType.DOCUMENT.value: "application/pdf",
        MimeType.SPREADSHEET.value: "application/pdf",
        MimeType.PRESENTATION.value: "application/pdf",
        MimeType.DRAWING.value: "application/pdf",
    }
    MS_OFFICE = {
        MimeType.DOCUMENT.value: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        MimeType.SPREADSHEET.value: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        MimeType.PRESENTATION.value: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    OPEN_OFFICE = {
        MimeType.DOCUMENT.value: "application/vnd.oasis.opendocument.text",
        MimeType.SPREADSHEET.value: "application/x-vnd.oasis.opendocument.spreadsheet",
        MimeType.PRESENTATION.value: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    PLAIN_TEXT = {
        MimeType.DOCUMENT.value: "text/plain",
        MimeType.PRESENTATION.value: "text/plain",
    }
    HTML_ZIPPED = {
        MimeType.DOCUMENT.value: "application/zip",
        MimeType.SPREADSHEET.value: "application/zip",
    }
    HTML = {MimeType.DOCUMENT.value: "text/html"}
    RICH_TEXT = {
        MimeType.DOCUMENT.value: "application/rtf",
    }
    EPUB = {MimeType.DOCUMENT.value: "application/epub+zip"}
    CSV = {MimeType.SPREADSHEET.value: "text/csv"}
    JPEG = {MimeType.DRAWING.value: "image/jpeg"}
    PNG = {MimeType.DRAWING.value: "image/png"}
    SVG = {MimeType.DRAWING.value: "image/svg+xml"}
