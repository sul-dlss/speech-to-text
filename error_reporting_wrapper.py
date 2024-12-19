#!/usr/bin/env python3

import dotenv
import logging
import os
import sys

from honeybadger import honeybadger
from subprocess import run, CalledProcessError


# This must be invoked before the logger is invoked for the first time
def configure() -> None:
    dotenv.load_dotenv()

    # TODO: HB and logging config copied from speech_to_text.py, may eventually want
    # to centralize more and start organizing codebase as a package?
    honeybadger.configure(
        api_key=os.environ.get("HONEYBADGER_API_KEY", ""),
        environment=os.environ.get("HONEYBADGER_ENV", "stage"),
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s :: %(levelname)s :: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )


def run_with_error_reporting(cmd_with_args: list) -> int:
    returncode: int

    try:
        completed_process = run(cmd_with_args, capture_output=True, check=True)
        returncode = completed_process.returncode

        logging.info(completed_process)
    except CalledProcessError as e:
        returncode = e.returncode

        error_context = {
            "message": str(e),
            "cmd": e.cmd,
            "returncode": e.returncode,
            "stdout": e.stdout,
            "stderr": e.stderr,
        }
        logging.error(error_context)
        honeybadger.notify("unexpected error executing command", context=error_context)

    return returncode


if __name__ == "__main__":
    configure()

    cmd_with_args = sys.argv[1:]  # argv[0] is this script's name
    logging.info(f"command and args: {cmd_with_args}")

    # bubble up the exit code from the wrapped call
    sys.exit(run_with_error_reporting(cmd_with_args))
