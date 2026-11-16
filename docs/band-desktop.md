# Running the crew in BAND Desktop

In this mode, BAND Desktop runs the coding crew: the Architect, the Builder and the Reviewer. Its daemon, `jamd`, owns each
agent's OpenCode runtime. When a room message mentions one of them, BAND Desktop starts OpenCode (Qwen 3.8 on W&B) in
the run's workspace, hands it the message, and posts what the agent sends back to the room. Each agent's work, tool
calls and reasoning show up live in the BAND Desktop window.

Scout, the Examiner and Nap Guard stay small Python agents (`onsen-scout`, `onsen-examiner`, `onsen-nap-guard`). They
are deterministic or call Nimble, so they don't need a coding runtime.

```
BAND Desktop (jamd) ── owns ──▶ Architect · Builder · Reviewer      OpenCode + Qwen 3.8, one runtime per agent per room
band-sdk processes ──────────▶ Scout · Examiner · Nap Guard
                       all six are BAND identities in one room
```

This is how runs 5 and later ran. Runs 1–4 used band-sdk's `OpencodeAdapter` for the crew instead (`ONSEN_CREW=sdk`,
the default), which needs no desktop app.

## One-time setup

These steps were done on Linux (Ubuntu 24.04). The launchers in `opencode/bin/` are POSIX shell scripts, so on Windows
run the crew under WSL, or adapt the launchers.

1. **Install BAND Desktop** (0.4.18 here): `sudo apt install ./jam-amd64.deb` from
   [docs.band.ai](https://docs.band.ai/band-desktop/install). It installs `band-desktop`, the `band` CLI and `jamd`.
2. **Put OpenCode on your PATH** (`npm i -g opencode-ai`). In the setup wizard, or under **Settings › Integrations**,
   turn on **OpenCode**. Onsen doesn't use the other runtimes.
3. **Sign in.** Use the wizard, or run `band init --auth api-key --user-api-key "$BAND_USER_KEY"`.
4. **Start the daemon with the W&B key**:

   ```bash
   scripts/band-desktop-daemon.sh
   ```

   The daemon passes its own environment to every agent runtime, so this script starts it with a minimal one: home,
   PATH, proxy and CA settings, and `WANDB_API_KEY`. Tokens that happen to be in your shell stay out of the agents'
   reach.
5. **Adopt the three crew agents.** They were registered by `onsen-register`, so they keep their names, handles and
   rooms:

   ```bash
   band adopt --agent-key <architect key> --session onsen-architect --host opencode
   ```

   ```bash
   band adopt --agent-key <builder key> --session onsen-builder --host opencode
   ```

   ```bash
   band adopt --agent-key <reviewer key> --session onsen-reviewer --host opencode
   ```

   The keys are in `~/.onsen/agent_config.yaml`.
6. **Give each one an OpenCode runtime.** In BAND Desktop, open **Agents › Builder › Runtime**, select **Set up** and
   fill in:

   | Field | Value |
   |---|---|
   | Runtime | OpenCode |
   | Approval policy | Allow automatically (the role's OpenCode profile still denies what it must, e.g. edits for the Reviewer) |
   | Command | `<repo>/opencode/bin/onsen-opencode-builder` |
   | Arguments | `acp` |
   | Environment allowlist | `PATH, WANDB_API_KEY` |

   Select **Test runtime**, then **Save agent setup**. Repeat for the Architect and the Reviewer with their own
   launchers. Each launcher loads `opencode/opencode.json` and picks the role's profile (`default_agent`). That is
   how the Reviewer gets an OpenCode runtime that can't edit files.

## Every run

```bash
ONSEN_CREW=desktop scripts/run-factory.sh capyfinder
```

Before the kickoff, `run-factory.sh` runs `uv run onsen-desktop prepare --workspace <new run folder>`, which:
- writes each crew agent's instructions to `~/.onsen/desktop/<role>.md`. The file holds the role's brief from `crew/`,
  `crew/PROTOCOL.md`, and a roster of everyone's BAND handle. It's live-linked in BAND Desktop
  (**Agents › <name> › Instructions**).
- points each agent's runtime at the new workspace (`band runtime template set --spawn-cwd … --apply-and-restart`).

Open the run's room in BAND Desktop to watch it. `scripts/stop-factory.sh` stops the crew's runtimes along with
everything else.

## What changes for the agents

BAND Desktop posts an agent's final answer as a reply to whoever woke it. In Onsen every protocol message goes to
specific agents (a `[ready]` goes to both the Examiner and the Reviewer), so the crew sends every message itself with
`band send <room> "@owner/handle … [tag] …"`. `onsen-desktop prepare` writes a roster of handles into each agent's
instructions.

That leaves the text a turn ends with. Qwen 3.8 can't end a turn without some ("." or "No reply needed."), and BAND
Desktop posts it to whoever woke the agent:
- **Run 5:** the crew traded acknowledgments, and the Architect's "Seal receipt confirmed …" re-sealed the exam.
- **Run 6:** told to stay silent, the Architect looped on no-op tool calls instead.

The fix is in the launcher. In ACP mode, `opencode/bin/onsen-opencode` runs `src/onsen/acp_filter.py`, a small
standard-library proxy between BAND Desktop and `opencode acp`. It holds the agent's message text while a turn is in
flight and passes it on at the end only if it starts with a crew protocol tag (`[ready]`, `[review]`, `[task]`, …).
Tool calls, reasoning and permission requests pass straight through, so BAND Desktop still shows every step. With
that in place, run 7 went from kickoff to `ship` with no stray messages.

## Notes

- `stop-factory.sh` leaves the crew's workers running; their OpenCode runtimes stop by themselves after 10 idle
  minutes. If a worker shows as stopped, `band restart --session onsen-<role>` brings it back.
- Our build machine had no display, so the BAND Desktop window ran on a virtual one (Xvfb). There its web view
  stopped repainting after about 25 minutes. The daemon and the agents were unaffected; restarting `band-desktop`
  brings the window back.
