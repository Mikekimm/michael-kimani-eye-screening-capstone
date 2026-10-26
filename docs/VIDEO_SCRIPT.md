# Walkthrough video script (target 12-14 minutes)

Record your screen with your voice (Zoom, OBS, or Windows Game Bar: Win+G). Read the **Say** lines in your own words;
do the **Show** steps. Keep three windows ready: the clinic app, the specialist portal, and a terminal.
Before recording: delete the `data` folder so the demo starts clean, and have 3 test fundus images
(one clearly abnormal, one normal, one blurry) plus a text file renamed to `bad.jpg`.

Mapping to the brief: **A** core functions, **B** technical requirements, **C** different inputs, **D** testing strategies,
**E** performance and compatibility, plus code quality.

---

## 0:00 Introduction (45 s)
**Show:** the README top and the architecture diagram.
**Say:** "I'm Michael Kimani. This is my capstone: an offline-first retinal screening prototype for diabetic retinopathy.
The user is a clinical officer at a rural health centre with unreliable internet. The app screens a retinal photo on the
device, saves the record locally, and sends flagged or borderline cases to a specialist when a connection is available.
It is screening support, not a diagnosis. I'll show the features, how they work, how I tested them, and how they perform."

## 1:00 Scope: what I planned and what I built (1 min)  *(Scope alignment)*
**Show:** `docs/SCOPE_TABLE.md`.
**Say:** "Compared with my proposal, these are completed: DR classification, local storage, two-way sync, the referral
workflow, and the specialist review portal. These are partial: the on-device model runs on a laptop rather than an Android phone, and
the backend uses Python's standard library with SQLite instead of FastAPI and PostgreSQL. These are not implemented:
glaucoma, cataract, the Android app and the load balancer. I chose depth on one disease and the offline architecture, which
is also what my supervisor asked for."

## 2:00 A. Core functionality, offline (3 min)
**Show:** start **only** the clinic app (`streamlit run app.py`). The backend is **not** running. Say so on camera.
1. Enter operator name, patient code `PT-0001`, eye = left, upload the abnormal image, click **Run screening and save**.
2. Point to the result card, score, threshold, recommendation, and the "Saved on this device" message.
3. Repeat with the normal image (`PT-0002`, right eye).
4. Open **Records and sync**: show the table with eye, result, model version and `pending`.

**Say:** "Nothing here needs the internet. The photo is decoded, the quality checker looks at size, blur, brightness and
whether it looks like a fundus, then the model produces a score. If the score is at or above the threshold I calibrated for 85%
sensitivity, it is flagged. If it is within 0.10 below the threshold it is 'borderline' and is also queued for the specialist,
because I would rather refer a doubtful case than clear it. The record, including the eye and the model version, is saved
before anything else happens."

## 5:00 B. Technical requirements: frontend, backend, data handling (2 min)
**Show:** terminal: `python scripts/run_server.py --demo-tokens`. In the clinic sidebar enter the clinician token; click **Sync now**.
Then open the specialist portal with the specialist token.
1. Show "Uploaded 2 screening(s)". The records change to `synced`.
2. In the portal, open the flagged case: image, eye, model version, score. Choose "Override: no DR", add a note, **Submit review**.
3. Back in the clinic app, **Sync now** again: "1 new specialist review". Select the record in "Review history for".

**Say:** "This is the frontend talking to the backend. The clinic app uploads each record with a checksum of the image; the
server verifies it and stores it once, even if I press sync twice. The specialist's identity comes from their access token, not from
what the browser sends. Reviews are append-only, so a second opinion would be added to the history, not replace the first."

## 7:00 C. Testing with different inputs and error handling (1.5 min)
**Show:** in the clinic app, one at a time:
- the text file named `bad.jpg` -> "could not be read as an image"
- a blank grey image -> "cannot be screened: blank or uniform"
- the blurry image -> screened **with a warning**
- patient code `Jane Doe` -> rejected, "use a code, not the patient's name"
- stop the backend, press **Sync now** -> "Offline ... records stay saved on this device"
- wrong token -> "server rejected the access token"

**Say:** "Each failure gives a clear message, and in every failure case nothing wrong is saved and nothing is lost."

## 8:30 D. Testing strategies (2 min)
**Show:** terminal: `pytest` running; then open `tests/test_api_integration.py` and `docs/TESTING.md`.
**Say:** "I used four strategies. **Unit tests** check each class on its own with a stub model, so they are fast. **Integration tests** start a
real backend on a local port and test authentication, roles, validation and the whole screen-save-sync-review loop.
**Connectivity tests** simulate the network dropping in the middle of a sync and check it resumes without duplicates. **UI smoke tests**
check both Streamlit pages start. There are [FILL: number] tests and [FILL: all] pass. Testing found real bugs: my first app resized
images differently from training; a race could delete an image; and my sync kept retrying a dead connection once per record.
I fixed each and added a test that would have caught it."

## 10:30 E. Performance and compatibility (1.5 min)
**Show:** terminal: `python scripts/benchmark.py --runs 50` and `python scripts/benchmark_pipeline.py`; then the two filled tables in
`docs/TESTING.md`; then the app open in Chrome and a second browser or your phone.
**Say:** "On my [high-end laptop] the model takes [FILL] ms per image; on my [second device] it takes [FILL] ms. The TensorFlow Lite model
is [FILL] MB versus [FILL] MB for the Keras model. The rest of the pipeline takes under [FILL] ms. I also ran the same workflow in
[FILL browsers] and on a phone over the network URL, and it behaved the same."

## 12:00 Code quality and model evaluation (1.5 min)
**Show:** the `src/` folder, then `src/classifier.py`, `src/thresholding.py`, and the printed table from `calibrate_threshold.py`.
**Say:** "The old single script is now a package with one job per class. `BaseClassifier` is an interface with Keras and TensorFlow Lite
implementations, so the service depends on the abstraction and tests can use a stub. The threshold algorithm finds the highest threshold that
reaches the sensitivity target in O(n log n). The threshold is chosen on one half of the held-out data and every number is reported on the
other half, with 95% bootstrap confidence intervals. The result is [FILL sensitivity and specificity], so the 85% / 80% targets are [MET / NOT MET]."

## 13:30 Limitations and close (45 s)
**Say:** "The data has no patient identifiers and contains augmented copies, so my results are optimistic and not clinical evidence.
There is no external test set, no usability study, and security is prototype-grade. Next steps are glaucoma and cataract, packaging the TFLite
model in an Android app, and an external evaluation. Thank you."
