# Benchmark speech-to-text

If you make changes to speech-to-text's software dependencies, especially the base nvidia/cuda Docker image or the Whisper software, it's a good idea to see what divergence there might be in the transcripts that are generated. To do this properly we should send the media through the complete speech-to-text workflow in the SDR, since it has certain options configured for Whisper as well as pre and post-processing.

22 items have been deposited into the SDR development environment, and tagged so that they can be easily queued up for processing. See [the wiki](https://github.com/sul-dlss/speech-to-text/wiki/Load-testing-the-speech%E2%80%90to%E2%80%90text-workflow) for details on how to run them.

The VTT file output for these transcripts as of 2025-01-31 has been stored in the `baseline` directory. When you are making updates to the speech-to-text software and want to examine the differences in output you can:

1. Ensure your changes pass tests, either locally or in Github.
2. Deploy your changes to the SDR QA environment by tagging a new version, e.g. `git tag rel-2025-01-29`, and pushing it to Github (`git push --tags`) so that the release Github Action runs. If this succeeds your changes will be live in the QA and Stage environments. Alternatively you can run deploy.sh directly (note that the Docker images generated come to around 20 GB, and may be slow to upload from a home connection).
3. Use Argo's [bulk action](https://github.com/sul-dlss/speech-to-text/wiki/Load-testing-the-speech%E2%80%90to%E2%80%90text-workflow#running-text-extraction-as-a-bulk-action) to generate transcripts.
4. Wait for the processing to be done. One easy way to do this is to look at them in the AWS Batch dashboard in the AWS Console. Or you can simply watch the last item in the batch to see when it completes.
5. Run report.py: `python report.py`
6. Commit your new report directory as a record.

You should find a `index.md` Markdown file in a date stamped directory inside the `reports` directory.

The `baseline` directory contains Cocina JSON and VTT files to use as baseline data. You may want to update these over time as understanding of what to use as a baseline changes. In an ideal world these would be more like ground truth data, or transcripts that have been vetted and corrected by people.

## Reports

This list contains reports that have been generated previously:

- [2025-01-31](reports/2025-01-31/)
- [2025-02-04](reports/2025-02-04/)
