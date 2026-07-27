import pytest

from speech_to_text import SpeechToTextException, inspect_media


def test_duration():
    result = inspect_media("tests/data/en.wav")
    assert result["duration"] == 3.220000


def test_format():
    result = inspect_media("tests/data/en.wav")
    assert result["format"] == "wav"


def test_size():
    result = inspect_media("tests/data/en.wav")
    assert result["size"] == 618318


def test_invalid_media():
    with pytest.raises(SpeechToTextException):
        inspect_media("README.md")
