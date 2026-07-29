# v0.2.24

## Automatic runs are yours now

**Add any job to any run.** A run used to hold whole skills, and only 11 of the
suite's ~46 runnable jobs were wired up at all. Now every job has a name and
shows up in a picker: 24 jobs across 11 skills. Open a run, hit **+ Add a job**,
pick what you want, drag it into order.

Things you could not schedule before, and now can:

- **P&L "Analyze all centers"** — the morning pulled the numbers from WebPAL
  every day and never built the tables from them. Add both and it does.
- **Truck rotation** — the making-it ranking, last month's tracking and the
  scorecard export (only the score and counts pull were reachable).
- **Refresh the org hierarchy** — when this is stale, anything set to "my
  district" quietly falls back to your own MCO. It can run first, automatically.
- Policy-publication refresh, repair-shop discovery, store-manager refresh,
  the auction audit, the one-way planner, and the P&L scope pull and backfill.

**Every job has its own settings.** Give one its own time limit, choose whether
it runs for your MCO, your district or your area, and fill in details it needs
(the auction audit's window start). A job that is missing a required detail says
so and is skipped, instead of failing at 07:00.

**Scope is no longer a hidden global.** Nothing used to send a level, so
changing the app-wide scope silently widened some jobs and not others, with
nothing on screen saying which. Each job now carries its own.

## Delete means delete

Nothing ships pre-scheduled. A fresh install has no runs until you make one —
start from a template (Morning, Midday, Truck, Storage, Weekly upkeep) or pick
jobs yourself. Deleting a run removes its Windows task too, and it stays
deleted.

**Leftover scheduled tasks** left behind by an older version, or by a run you
deleted, now get their own card with a Remove button. They were invisible
before, which is why a deleted run could still look like it was running.

## Fixes

- Removing a schedule reported a failure when it had actually worked (it was
  reading Windows' wording instead of asking whether the task was gone).
- The suite never starts or stops the dashboard itself — it is the app running
  the editor.
- Your existing runs are carried over automatically.