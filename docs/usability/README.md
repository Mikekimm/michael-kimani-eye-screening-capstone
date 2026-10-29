# Usability test kit (about 15 minutes per tester)

Goal: check that people who match the intended users (health workers, or failing that nursing or
clinical students) can complete the core tasks without help, and measure perceived usability with the
System Usability Scale (SUS). Aim for 3-5 testers; record what you actually ran, even if it is fewer.

Remote sessions (video call and a public HTTPS tunnel): see [remote_testing.md](remote_testing.md).

## Before each session
1. Run the app (README section 7) on a phone or a laptop in phone-sized view.
2. Prepare 2 **public** fundus images (e.g. from APTOS 2019 on Kaggle) on the device. Never use real patient photos.
3. Read the tester this: "You are testing the app, not yourself. Please think aloud. I will not help unless you are stuck for more than a minute. You can stop at any time. I will not record your name."
4. Give each tester an ID (T1, T2, ...). Record only the ID, role (e.g. nurse, student) and device.

## Tasks (time each, note errors and where they hesitated)
| Task | Instructions to the tester | Success = |
|---|---|---|
| 1 | "Create an account, then register a new patient and tell me the code the app gives them." | patient page with the new code (e.g. PHC-XXXXXX) shown; tester reads the code |
| 2 | "Screen this patient's left eye using the photo on this device, then tell me what the result means and what you should do next." | result shown; tester explains the band is an estimate and states the recommended action |
| 3 | "The internet is now off (switch on airplane mode). Screen the right eye. Then turn the internet back on and find out whether it was sent." | photo saved while offline; tester finds it synced in History |

## After the tasks
1. The tester fills in [sus_questionnaire.md](sus_questionnaire.md) (10 statements, 1-5).
2. Ask: "What was most confusing?" and "What would you change?" Write the answers down word for word.
3. Enter everything into [results.csv](results.csv) (one row per tester).

## Scoring and reporting
```powershell
.venv\Scripts\python scripts\sus_score.py docs\usability\results.csv
```
It prints each tester's SUS score (0-100), the mean and the task success rates. A SUS score above about
68 is usually read as above average. Report: number of testers and who they were, task success and
time, SUS mean and range, the 3-5 problems seen most often, and what you changed because of them. With
fewer than 5 testers, say so and treat the results as indicative only.
