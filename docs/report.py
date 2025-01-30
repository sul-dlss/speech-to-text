#!/usr/bin/env python3

import datetime
import difflib
import json
import re
from io import StringIO
from pathlib import Path
from typing import Iterator, Tuple, List

import requests

# These are media items set up in SDR's QA environment to use for testing.

druids = [
    "bz245jm8076",
    "cf157rm7757",
    "cv116wv5355",
    "cz258mq3842",
    "dn434hf2144",
    "fk250vc8974",
    "gj376pv2367",
    "hv054kd4261",
    "jr745nr3367",
    "jv560nw0036",
    "jz734cm7143",
    "kb425fq6029",
    "kg363hp7075",
    "mc135dt6327",
    "qx203gt3137",
    "rr765bw2466",
    "tg491zk0596",
    "vr271pc9432",
    "wg332kt9945",
    "xs708yc4548",
    "yr465hd3700",
    "yy014cj2840",
]


def main() -> None:
    date = datetime.datetime.now().strftime("%Y-%m-%d")
    baseline_dir = Path("baseline")
    current_dir = Path("reports") / date

    # if there are no files to compare go get them
    if not current_dir.is_dir():
        current_dir.mkdir()
        for druid in druids:
            print(f"fetching files for {druid}")
            get_files(druid, current_dir)

    write_report(date, baseline_dir, current_dir)
    print(f"wrote report to reports/{date}/index.md")


def get_files(druid: str, output_dir: Path) -> None:
    """
    Fetch the VTT and Cocina JSON files for a specific SDR item using the DRUID.
    """

    # Note: The SDR items corresponding to these Druids are in the QA
    # environment, but both the QA and Staging SDR environment publish to PURL
    # and Stacks in the Staging environment. Confusing? Yes. At least this is
    # the case when this was written in 2025-01-01.

    # fetch the Cocina and write it out
    cocina = requests.get(f"https://sul-purl-stage.stanford.edu/{druid}.json").json()
    cocina_file = output_dir / f"{druid}.json"
    json.dump(cocina, cocina_file.open("w"), indent=2)

    # look in the Cocina for VTT files to download
    for filename in vtt_files(cocina):
        url = f"https://stacks-stage.stanford.edu/file/druid:{druid}/{filename}"
        data = requests.get(url).content
        output_file = output_dir / filename.name
        output_file.open("wb").write(data)


def vtt_files(cocina: dict) -> Iterator[Path]:
    """
    Return an iterator for all the VTT files in the item.
    """
    for resource in cocina["structural"]["contains"]:
        for file in resource["structural"]["contains"]:
            filename = Path(file["filename"])
            if filename.suffix == ".vtt":
                yield filename


def write_report(date: str, baseline_dir: Path, current_dir: Path) -> None:
    """
    Writes a index.md file to current_dir summarizing the differences between
    it and the baseline.
    """

    output_file = current_dir / "index.md"
    output = output_file.open("w")
    output.write(f"# Benchmark Comparison {date}\n")

    for druid in druids:
        output.write(f"\n## {druid}\n\n")

        for test_name, result in compare_item(date, druid, baseline_dir, current_dir):
            checkbox = "- [X]" if result else "- [ ]"
            output.write(f"{checkbox} {test_name}\n")


def compare_item(
    date: str, druid: str, baseline_dir: Path, current_dir: Path
) -> List[Tuple[str, bool]]:
    """
    Compare the transcripts in the baseline directory with the ones found in the
    current_dir. The druid is passed in for reference in messages. A list of
    tuples of a test message and whether the test passed is returned.
    """
    checks = []

    cocina_baseline = json.load((baseline_dir / f"{druid}.json").open())
    cocina_current = json.load((current_dir / f"{druid}.json").open())

    checks.append(
        ("version is greater", cocina_current["version"] > cocina_baseline["version"])
    )

    vtts_b = list(vtt_files(cocina_baseline))
    vtts_c = list(vtt_files(cocina_current))

    checks.append(
        (f"has correct number of VTT files ({len(vtts_b)})", len(vtts_b) == len(vtts_c))
    )

    for vtt in vtts_b:
        vtt_b = baseline_dir / vtt
        vtt_c = current_dir / vtt

        msg = f"{vtt} size ({vtt_b.stat().st_size} == {vtt_c.stat().st_size})"
        same_size = vtt_b.stat().st_size == vtt_c.stat().st_size

        # if the file sizes aren't the same generate a diff HTML file and link it
        if not same_size:
            diff_filename = f"{vtt_b.name}-diff.html"
            write_diff(druid, vtt_b, vtt_c, current_dir / diff_filename)
            msg += f" [diff](https://sul-dlss.github.io/speech-to-text/reports/{date}/{diff_filename})"

        checks.append((msg, same_size))

    return checks


def write_diff(druid: str, vtt1: Path, vtt2: Path, output_file: Path) -> None:
    """
    Writes an HTML diff for two given VTT files. The HTML is written to the
    output_path location. The druid is passed in for use in the report.
    """
    lines1 = split_sentences(lines(vtt1))
    lines2 = split_sentences(lines(vtt2))

    diff = difflib.HtmlDiff(wrapcolumn=80).make_file(
        lines1, lines2, "reference", "transcript"
    )

    output = StringIO()
    output.writelines(diff)
    html = output.getvalue()

    # embed the media player for this item
    html = html.replace(
        "<body>",
        f'<body style="margin: 0px;">\n\n    <div style="height: 200px;"><iframe style="position: fixed;" src="https://embed-stage.stanford.edu/iframe?url=https://purl-stage.stanford.edu/{druid}" height="200px" width="100%" title="Media viewer" frameborder="0" marginwidth="0" marginheight="0" scrolling="no" allowfullscreen="allowfullscreen" allow="clipboard-write"></iframe></div>',
    )

    output_file.open("w").write(html)


def lines(vtt_file: Path) -> List[str]:
    """
    Returns a list of just the text lines from the VTT file.
    """
    results = []
    for line in vtt_file.open():
        line = line.strip()
        if line and line != "WEBVTT" and " --> " not in line:
            results.append(line)

    return results


sentence_endings = re.compile(r"(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s")


def split_sentences(lines) -> List[str]:
    """
    Split lines with multiple sentences into multiple lines. So,

        To be or not to be. That is the question.

    will become:

        To be or not to be.
        That is the question.
    """
    text = " ".join(lines)
    text = text.replace("\n", " ")
    text = re.sub(r" +", " ", text)
    sentences = sentence_endings.split(text.strip())
    sentences = [sentence.strip() for sentence in sentences]

    return sentences


if __name__ == "__main__":
    main()
