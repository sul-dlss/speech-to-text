import error_reporting_wrapper
import pytest

from subprocess import run, CalledProcessError, CompletedProcess

from unittest.mock import patch


def test_error_reporting_wrapper_exit_zero():
    completed_process = run(["cat", "Dockerfile"], check=True)
    assert completed_process.returncode == 0, "return code for successful command is 0"


def test_error_reporting_wrapper_exit_nonzero():
    completed_process = run(["cat", "foooooo"])
    assert completed_process.returncode == 1, (
        "return code for unsuccessful command is bubbled up through wrapper"
    )


@patch("error_reporting_wrapper.honeybadger")
def test_run_with_error_reporting_on_error_honeybadger(mock_honeybadger):
    returncode = error_reporting_wrapper.run_with_error_reporting(["cat", "foooooo"])

    mock_honeybadger.notify.assert_called_once()
    args, kwargs = mock_honeybadger.notify.call_args
    context = kwargs["context"]
    assert isinstance(args[0], CalledProcessError)
    assert "returned non-zero exit status" in context["message"]
    assert context["cmd"] == ["cat", "foooooo"]
    assert context["returncode"] == 1
    assert returncode == 1


# ignore utcnow warning from within honeybadger
@pytest.mark.filterwarnings("ignore:datetime.datetime.utcnow")
@patch("error_reporting_wrapper.logging")
def test_run_with_error_reporting_on_error_logging(mock_logging):
    returncode = error_reporting_wrapper.run_with_error_reporting(["cat", "foooooo"])

    mock_logging.error.assert_called_once()
    args, kwargs = mock_logging.error.call_args
    assert "returned non-zero exit status" in args[0]["message"]
    assert args[0]["cmd"] == ["cat", "foooooo"]
    assert args[0]["returncode"] == 1
    assert returncode == 1


@patch("error_reporting_wrapper.logging")
@patch("error_reporting_wrapper.honeybadger")
def test_run_with_error_reporting_on_success(mock_honeybadger, mock_logging):
    returncode = error_reporting_wrapper.run_with_error_reporting(["cat", "Dockerfile"])

    mock_honeybadger.notify.assert_not_called()
    mock_logging.error.assert_not_called()
    mock_logging.info.assert_called_once()
    args = mock_logging.info.call_args.args
    assert isinstance(args[0], CompletedProcess)
    assert returncode == 0
