# Running the seats in BAND Desktop

BAND Desktop runs Onsen's four coding seats: the Architect, the Builder, the Examiner and the Reviewer. Its daemon,
`jamd`, owns one OpenCode runtime per seat per room. When a room message mentions a seat, BAND Desktop starts (or
wakes) that seat's runtime in the run's workspace, hands it the message, and shows its work, tool calls and reasoning
live in the BAND Desktop window. Every coding seat runs GPT-6 Luna (OpenAI) at medium effort.

Nap Guard stays a small band-sdk agent (`onsen-nap-guard`, plus its watch `onsen-quiet-watch`): it has no model, so it
needs no coding runtime.

```
BAND Desktop (jamd) ── owns ──▶ Architect · Builder · Examiner · Reviewer   OpenCode + GPT-6 Luna, one runtime per seat per room
band-sdk process ────────────▶ Nap Guard                                    no model: the gate, the checker runs, the watch
                       all five are BAND identities in one room
```

## One-time setup

These steps were done on Linux (Ubuntu 24.04, 4 vCPU). The launchers in `opencode/bin/` are POSIX shell scripts, so on
Windows run the seats under WSL, or adapt the launchers.

1. **Install BAND Desktop** (0.4.18 here): `sudo apt install ./jam-amd64.deb` from
   [docs.band.ai](https://docs.band.ai/band-desktop/install). It installs `band-desktop`, the `band` CLI and `jamd`.
2. **Put OpenCode on your PATH** (`npm i -g opencode-ai`; we ran 1.19.5). In the setup wizard, or under
   **Settings › Integrations**, turn on **OpenCode**. Onsen doesn't use the other runtimes.
3. **Sign in.** Use the wizard, or run `band init --auth api-key --user-api-key "$BAND_USER_KEY"`.
4. **Register the five seats** with `uv run onsen-register`. It creates the BAND identities and writes their keys to
   `$ONSEN_HOME/agent_config.yaml`.
5. **Start the daemon**:

   ```bash
   scripts/band-desktop-daemon.sh
   ```

   The daemon passes its own environment to every runtime it starts, so this script starts it with a minimal one:
   home, PATH (with the factory's `bin/` first), proxy and CA settings, `OPENAI_API_KEY`, `ONSEN_OPENCODE_CONFIG`
   (the OpenCode config to load, `opencode/opencode-openai.json`) and the checker settings (`ONSEN_HOME`,
   `ONSEN_CHECKER_DIR`, `ONSEN_CHECKER_PY`, `ONSEN_TRACK`, `ONSEN_CHECKS_DIR`). Tokens that happen to be in your shell
   stay out of the seats' reach.
6. **Adopt the four coding seats**, which keep the names and handles `onsen-register` gave them:

   ```bash
   band adopt --agent-key <architect key> --session onsen-architect --host opencode
   ```

   ```bash
   band adopt --agent-key <builder key> --session onsen-builder --host opencode
   ```

   ```bash
   band adopt --agent-key <examiner key> --session onsen-examiner --host opencode
   ```

   ```bash
   band adopt --agent-key <reviewer key> --session onsen-reviewer --host opencode
   ```

7. **Give each seat its OpenCode runtime**, through its own launcher (repeat for `architect`, `builder`, `examiner`
   and `reviewer`):

   ```bash
   band runtime template set --session onsen-builder --transport opencode \
     --spawn-command <repo>/opencode/bin/onsen-opencode-builder --spawn-arg acp --runtime-approval approve-all \
     --runtime-env PATH --runtime-env OPENAI_API_KEY --runtime-env ONSEN_OPENCODE_CONFIG --runtime-env HOME \
     --runtime-env ONSEN_HOME --runtime-env ONSEN_CHECKER_DIR --runtime-env ONSEN_CHECKER_PY \
     --runtime-env ONSEN_TRACK --runtime-env ONSEN_CHECKS_DIR
   ```

   (An adopted seat with no template yet gets one from **Agents › seat › Runtime › Set up** first.) Each launcher puts
   the factory's `bin/` first on `PATH` (BAND Desktop starts runtimes with `/usr/bin` first, which would hide the room
   linter), loads the OpenCode config with the seat's permission profile (the Reviewer's denies every edit; OpenCode's
   question tool and BAND's ask-the-human tool are off for everyone), sets the seat's git name, gives shell commands
   25 minutes, installs the git hook that keeps the Examiner and the Reviewer from committing, and runs
   `src/onsen/acp_filter.py` in front of `opencode acp`.

## Every run

```bash
scripts/run-dark.sh <result repository> <task file> "Onsen · Dossier"
```

It moves earlier runs' exam workspaces and the seats' scratch files out of reach, takes the seats out of old rooms,
installs the result repository's own pre-commit hook (no commits to an accepted stage's folder), starts Nap Guard in
dark mode, runs `uv run onsen-desktop prepare --workspace <result repository>`, opens a fresh room with the five seats,
posts the task as the only human message, and starts Nap Guard's watch on the room. `onsen-desktop prepare`:
- writes each seat's instructions to `$ONSEN_HOME/desktop/<seat>.md`: its mandate (`mandates/`), the room protocol
  (`crew/PROTOCOL.md`), its own tools, and a roster of every seat's BAND handle. The file is live-linked in BAND
  Desktop (**Agents › <name> › Instructions**).
- points each seat's runtime at the result repository (the Examiner at its own workspace, so its exam stays out of the
  repository until it is published) and restarts it.

Open the run's room in BAND Desktop to watch it.

## What changes for the seats

BAND Desktop posts the text a turn ends with as a reply to whoever woke the seat. In Onsen every protocol message goes
to specific seats (a `[ready]` goes to both the Examiner and the Reviewer), so the seats send every message themselves
with `band send <room> "@owner/handle … [tag] …"`, through the room linter. `acp_filter.py`, a small standard-library
proxy between BAND Desktop and `opencode acp`, keeps a turn's closing text out of the room, and when a working seat's
turn ends without it having sent anything, prompts it to carry on (and, if its last edit was cut off mid-stream, to
make that change again in smaller parts). Tool calls, reasoning and permission requests pass straight through, so BAND
Desktop still shows every step.

A seat hears new messages only between its turns. That is why every mandate says to end the turn while waiting, and
why Nap Guard's watch interrupts the Builder's turn (`band runtime interrupt` on the room's host session) when it must
hear something at once: its stage was accepted, or a commit the checker claims has gone five minutes without a
handoff.

## Notes

- Our build machine had no display, so the BAND Desktop window ran on a virtual one (Xvfb). In a room with a long
  history its renderer used about two of the machine's four cores and slowed the band's checks; on its Home page it
  uses a tenth of a core. The daemon and the seats don't depend on the window: restarting `band-desktop` is safe.
- Before the event, the coding seats ran Qwen 3.8 27B on W&B Inference (`opencode/opencode.json`); the launchers
  still accept that config through `ONSEN_OPENCODE_CONFIG` with `WANDB_API_KEY`.
