# GitHub Commit Activity Bot

This repository contains a small Python script that can create lightweight commits at randomized intervals. It is meant for experimentation inside a repository **you control**. Use it responsibly—bursting large volumes of meaningless commits to public repositories might violate terms of service or trigger anti-abuse automation.

## How it works
- You choose how many commits per hour you would like to generate and for how many hours to run.
- The script modifies/creates a small log file (`activity-log.md` by default) so each commit has a unique change.
- Wait times between commits are randomly jittered around the average interval to avoid a perfectly regular pattern.
- Commits can be pushed after every change, in batches, or once at the end.

## Quick start
1. Make sure this repo is initialized with Git and the remote you plan to push to.
2. Install Python 3.9+.
3. Optionally create and activate a virtual environment.
4. Run:
   ```bash
   python commit_bot.py --commits-per-hour 20 --duration-hours 1 --push-mode end
   ```

The script supports more knobs (dry-run, custom target file, push batch sizes, etc.). See `python commit_bot.py --help` for details.

## Anti-ban considerations
- Keep runs short and infrequent; huge numbers of commits may look suspicious.
- Prefer running in private repos or forks where noisy history does not impact collaborators.
- Use descriptive commit messages instead of nonsense to reduce the chance of automated moderation.
- Always respect GitHub's Terms of Service.

You are responsible for how you use this tool. EOF
