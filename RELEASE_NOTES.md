# v0.2.26

- Rotation: a run made on the first day of a new AP no longer files newly tracked trucks into the AP that just closed. The counts report can still be serving the closed AP on day 1; a "Current month" window that does not contain today is now rejected and the report's own next window is used instead.
- Rotation: the location-slot ledger refuses to record a roster read against a closed AP.
- AFM: the rotation GRPU window now follows the real 5-4-4 AP calendar instead of a flat 28-day grid, so a 5-week AP is scored against the 5-week standard.