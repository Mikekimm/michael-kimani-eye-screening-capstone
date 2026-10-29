# Remote usability testing (video call + public HTTPS tunnel)

How to let a tester on another device use the app from this laptop during a video call, then score the
session with SUS. The tasks and the questionnaire are the ones in [README.md](README.md)
and [sus_questionnaire.md](sus_questionnaire.md). Screening support only; not a diagnostic device.

## 1. Run the app behind one public HTTPS address

One origin serves both the app and `/api`: the production build is served by `vite preview`, whose built-in
proxy forwards `/api` to the backend (same `vite.config.ts` as the end-to-end tests). A Cloudflare quick tunnel
points at that one port. No code change is needed:

- the frontend calls the relative path `/api`, so it always talks to the origin it was loaded from;
- sign-in uses Bearer tokens kept in the browser (localStorage), not cookies, so there are no cookie, SameSite
  or domain settings to change;
- browser and API share one origin, so CORS does not apply (`CORS_ORIGINS` stays as it is);
- Vite 5.4.10 (the pinned version) does not check the Host header. If Vite is upgraded to 5.4.12 or later and the
  tunnel shows "Blocked request. This host is not allowed", add `allowedHosts: [".trycloudflare.com"]` to the
  `preview` block in `frontend/vite.config.ts`.

Three PowerShell windows, from the repository root:

```powershell
# 1. backend (port 8000)
cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --port 8000

# 2. production frontend + /api proxy (port 4173)
cd frontend; npm.cmd run build; npx.cmd vite preview --port 4173 --strictPort

# 3. tunnel (install once: winget install --id Cloudflare.cloudflared)
cloudflared tunnel --no-autoupdate --url http://localhost:4173
```

cloudflared prints a line such as `https://<random-words>.trycloudflare.com`. Open that address yourself first
(sign in as the demo nurse), then paste it to the tester in the call chat. It is valid only while the tunnel
runs and is different every time. Quick tunnels are for testing only (no account, no uptime guarantee).

Verified on this laptop on 28 Oct 2026: through the tunnel URL, from a headless Chromium browser emulating a
Pixel 5 phone, the app and `/api/health` loaded; the demo nurse signed in; the consent page appeared; a patient
was registered; a fundus image (the repository's synthetic test image) was uploaded and the result page showed
all three model results with the disclaimer (1.4 s from Analyse to result); History listed the screening. All
API calls returned 200/201. Not verified through the tunnel: offline capture and sync (task 3) and a real phone.

## 2. Safety checklist (every session)

- [ ] Demo accounts only (`docs/video_script.md`); testers who sign up use a made-up address such as
      `t1.test@example.org`, never their own email.
- [ ] Public fundus images only (e.g. two images from APTOS 2019 on Kaggle), sent to the tester before the call.
      No real patient photos and no real patient data anywhere.
- [ ] The tunnel URL is never committed, put in a document or posted publicly. It changes on every run.
- [ ] Stop the tunnel (Ctrl+C in window 3) as soon as the session ends, then stop the frontend and backend.
- [ ] Reset the demo data after testing (backend stopped):
      `.venv\Scripts\python scripts\reset_demo_data.py --yes`. Approved non-demo accounts are kept.
- [ ] While the tunnel runs, anyone with the URL can reach the sign-in page. Keep sessions short and do not
      leave the tunnel open unattended.

## 3. Moderator script (video call with screen share; recording optional)

Before the call: the app and the tunnel are running, you are signed in as the demo **admin** in your own
browser (to approve the tester's sign-up), and the tester has the two public fundus images on their device.
The tester uses a phone for the app if possible (the call on a laptop), so airplane mode in task 3 does not end
the call. On a laptop, they can use Chrome DevTools > Network > "Offline" instead.

1. **Consent** (read aloud): "Thank you for helping. You are testing the app, not yourself. Please think aloud.
   I will not help unless you are stuck for more than a minute. You can stop at any time. I will not record your
   name; you will be T1 in my notes. [If recording:] May I record the screen share and audio for my notes only?
   I will delete it after the analysis." Continue only after a clear yes.
2. Share the tunnel URL in the call chat. Ask the tester to share their screen.
3. **Task 1:** "Create an account, then register a new patient and tell me the code the app gives them." The account is a
   request: when the tester sees "Waiting for administrator approval", approve it on your Users page and tell
   them they can sign in now. (Note how they react to the waiting state.)
4. **Task 2:** "Screen this patient's left eye using the photo on this device, then tell me what the result means and
   what you should do next."
5. **Task 3:** "The internet is now off (switch on airplane mode). Screen the right eye. Then turn the internet
   back on and find out whether it was sent."
6. Time each task and note errors and hesitations (as in `docs/usability/README.md`).
7. **SUS, after the tasks:** read the 10 statements from `docs/usability/sus_questionnaire.md` one by one
   (or paste them in the chat); the tester answers 1 (strongly disagree) to 5 (strongly agree).
8. Ask: "What was most confusing?" and "What would you change?" Write the answers down word for word.
9. Thank the tester, end the call, stop the tunnel and run the safety checklist.

Testers are identified only as T1, T2, ... with role (e.g. nurse, nursing student) and device type.

## 4. Results

1. Add one row per tester to [results.csv](results.csv): `tester_id, role, device, q1..q10
   (1-5), task1_success..task3_success (yes/no), task1_seconds..task3_seconds, comments`. No names or emails.
2. Score:
   ```powershell
   .venv\Scripts\python scripts\sus_score.py docs\usability\results.csv
   ```
   It prints each tester's SUS score (0-100), the mean and the task success rates.
3. Report the number of testers and who they were, task success and time, SUS mean and range, the problems seen
   most often and what was changed because of them. Note that testing was remote (own device and network). With
   fewer than 5 testers, say so and treat the results as indicative only.
