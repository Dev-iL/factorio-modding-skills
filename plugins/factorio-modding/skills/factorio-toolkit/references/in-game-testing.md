# Test a mod against the real game

Two scripts launch the game headless in a sandbox (see [install-paths-and-logs.md](install-paths-and-logs.md)); neither
opens a window or touches the user's mods and saves. The following table lists them with `scan_log.py`, which reads a finished run:

| Script | What it proves | Typical time |
|---|---|---|
| `check_data.py --mod DIR` | The data stage loads: the game exits 0 on `--dump-data`, the log has no errors, and `data-raw-dump.json` parses. | 4-22 s |
| `run_tests.py --mod DIR` | The control stage runs and the mod's own assertions pass: the script creates a map with the mod, then benchmarks it for a few ticks. | 5-25 s |
| `scan_log.py --log FILE` | Reads a log once and lists errors with stage, file and log excerpt. | instant |

All three exit 0 on success, 1 when the mod fails, and 2 when the environment needs fixing (missing game, bad path).
A failure names the stage (`data` or `control`), the file and line or the prototype, and a log excerpt.

## Data-stage details

- `--check-unused-prototype-data` is always passed. Without it, the game accepts a misspelt or unknown prototype property
  silently with exit code 0. With the flag it logs `Value ROOT.item.x.bogus was not used.`, and `check_data.py` reports that as
  an error. A vanilla install logs none of these, so any such line belongs to the mod. Use `--allow-unused` to downgrade it.
- `--expect type/name` (repeatable) also requires that prototype in `data.raw`, for example `--expect item/my-chest`.
- `--dump-to FILE` copies the dump so the finished prototypes can be searched.
- `--dump-data` does not read sprite files, so a wrong `filename` or sprite rectangle passes the data stage. `--graphics` adds a
  second launch (`--dump-icon-sprites`, which loads every sprite) with a small game window for about 50 s. A missing file or an
  out-of-range rectangle stops it with the error. Use it whenever the mod ships graphics (see [graphics-ladder.md](graphics-ladder.md)).

## Write control-stage tests

`run_tests.py` reads results from the log. A test reports by calling `log()` with one of these forms. The `[FMS-TEST]` tag is this plugin's own marker, not a
Factorio feature:

```lua
log("[FMS-TEST] PASS inserter bonus applied")
log("[FMS-TEST] FAIL inserter bonus applied: expected 2, got 1")
```

Run assertions where they will execute:

- `script.on_init` runs once, when the map is created (the first launch). Use it for checks on `prototypes`, settings, and
  initial state.
- `script.on_nth_tick(1, ...)` runs during the benchmark (the second launch; `--ticks` sets how long). Use it for behaviour
  over time. Unregister it after the first call with `script.on_nth_tick(1, nil)` unless the check needs every tick.

A Lua error or a failed `assert` stops the game with a non-zero exit code and is reported as a `control` stage failure with the
Lua error line. A mod that reports no `[FMS-TEST]` lines fails, so a test that never ran cannot pass.
A complete passing example is `tests/fixtures/mods/fms-good` in this repository.

Prefer asserting on prototypes (`prototypes.item[...]`, `prototypes.entity[...]`) in `on_init`; it is the cheapest
check and needs no game state. Entity behaviour needs a surface: create entities with `game.surfaces[1].create_entity`.

## Mods that need an official expansion

Official mods named in `info.json` `dependencies` (for example `space-age`, which pulls in `quality` and
`elevated-rails`) are enabled automatically. `--enable NAME` enables another one. `--keep` leaves the sandbox
(printed path) for inspection.
