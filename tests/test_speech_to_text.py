import json
from pathlib import Path

import dotenv
import pytest
import speech_to_text

# set AWS_PROFILE from .env in the environment
dotenv.load_dotenv()


# ignore utcnow warning until https://github.com/boto/boto3/issues/3889 is resolved
@pytest.mark.filterwarnings("ignore:datetime.datetime.utcnow")
def test_speech_to_text():
    clean()

    job_id = speech_to_text.create_job(Path("tests/data/en.wav"))

    speech_to_text.main(daemon=False)

    # check that the vtt file is present
    test_bucket = speech_to_text.get_bucket()
    vtt_file = test_bucket.Object(f"out/{job_id}/en.vtt").get()
    assert vtt_file, "vtt file created"
    assert "This is a test" in vtt_file["Body"].read().decode("utf-8"), "vtt content"

    # make sure there's a message in the "done" queue
    queue = speech_to_text.get_done_queue()
    msgs = queue.receive_messages(MaxNumberOfMessages=1, WaitTimeSeconds=10)
    assert len(msgs) == 1, "found a done message"
    assert msgs[0].delete(), "delete the message from the queue"

    # make sure the job looks ok
    job = json.loads(msgs[0].body)
    assert job["id"] == job_id
    assert job["finished"]

    jobs = queue.receive_messages(MaxNumberOfMessages=1)
    assert len(jobs) == 0, "queue empty"


def clean():
    """
    Ensure that the bucket and queues are empty.
    """
    todo = speech_to_text.get_todo_queue()
    while messages := todo.receive_messages():
        for m in messages:
            m.delete()

    done = speech_to_text.get_done_queue()
    while messages := done.receive_messages():
        for m in messages:
            m.delete()

    bucket = speech_to_text.get_bucket()
    for obj in bucket.objects.all():
        obj.delete()
