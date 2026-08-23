"""Monitor the Gemini 2.5 Flash smoke-test tuning job."""
import sys
import time
from google import genai

JOB_NAME = "projects/601576302267/locations/europe-west4/tuningJobs/1031152859573387264"
POLL_SECS = 30
TERMINAL = {"JobState.JOB_STATE_SUCCEEDED", "JobState.JOB_STATE_FAILED",
            "JobState.JOB_STATE_CANCELLED", "JobState.JOB_STATE_PARTIALLY_SUCCEEDED"}

client = genai.Client(vertexai=True, project="raylo-production", location="europe-west4")

last_state = None
start = time.monotonic()
while True:
    job = client.tunings.get(name=JOB_NAME)
    state = str(job.state)
    elapsed_min = (time.monotonic() - start) / 60

    if state != last_state:
        print(f"[{elapsed_min:5.1f}m] state changed: {last_state} -> {state}", flush=True)
        last_state = state

    if state in TERMINAL:
        print(f"[{elapsed_min:5.1f}m] TERMINAL STATE: {state}", flush=True)
        if getattr(job, "error", None):
            print(f"error: {job.error}", flush=True)
        if getattr(job, "tuned_model", None):
            print(f"tuned_model: {job.tuned_model}", flush=True)
        sys.exit(0)

    time.sleep(POLL_SECS)
