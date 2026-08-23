"""Monitor the full 164k-row Gemini 2.5 Flash tuning job."""
import sys
import time
from google import genai

JOB_NAME = "projects/601576302267/locations/europe-west4/tuningJobs/1504505809470488576"
POLL_SECS = 60
HEARTBEAT_EVERY = 10  # ~10 minutes
TERMINAL = {"JobState.JOB_STATE_SUCCEEDED", "JobState.JOB_STATE_FAILED",
            "JobState.JOB_STATE_CANCELLED", "JobState.JOB_STATE_PARTIALLY_SUCCEEDED"}

client = genai.Client(vertexai=True, project="raylo-production", location="europe-west4")

last_state = None
start = time.monotonic()
poll_count = 0
while True:
    job = client.tunings.get(name=JOB_NAME)
    state = str(job.state)
    elapsed_min = (time.monotonic() - start) / 60

    if state != last_state:
        print(f"[{elapsed_min:5.1f}m] state changed: {last_state} -> {state}", flush=True)
        last_state = state
    elif poll_count % HEARTBEAT_EVERY == 0:
        print(f"[{elapsed_min:5.1f}m] heartbeat: still {state}", flush=True)

    if state in TERMINAL:
        print(f"[{elapsed_min:5.1f}m] TERMINAL STATE: {state}", flush=True)
        if getattr(job, "error", None):
            print(f"error: {job.error}", flush=True)
        if getattr(job, "tuned_model", None):
            print(f"tuned_model: {job.tuned_model}", flush=True)
        if getattr(job, "tuning_data_stats", None):
            print(f"tuning_data_stats: {job.tuning_data_stats}", flush=True)
        sys.exit(0)

    poll_count += 1
    time.sleep(POLL_SECS)
