# v0.2.27

Skill windows from a previous session no longer linger — and a stale one can no longer make an update look like it never installed.

- Closing the dashboard now closes the skills with it. Stopping the hub used to leave every skill web server running on its own port; thirteen were found alive on one machine, the oldest up seven days.
- Starting a skill always lands on the current code. A server already answering on the port used to be reused as-is, even when it was a leftover running whatever it loaded days earlier.
- The launcher can finally tell a stale server from a current one. It compares the running version against the installed one to decide whether to restart — but the running server reported the installed version, so the two could never disagree and an update under a running server was always reused. A server now reports the version it actually started with.
- A scheduled suite run is never interrupted by any of this: the cleanup refuses to run while a run is in progress.