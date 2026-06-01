# Shop Player Auto Acquire

`scripts/run_websoccer_shop_player_auto_acquire.py` automates paid shop-player listup decisions.

Default mode is read-only. It fetches `/sync/all.json`, resolves wanted/block players, and exits without calling shop mutation APIs. Add `--execute` to spend P.

## Decision Rules

1. Stop before listup when current P is `reserveP` or less. Default `reserveP=100`.
2. Call `/shop_player/listup/<team_id>/<world_id>.json`.
3. If `r0` is in the release block list, call `/shop_player/drop`.
4. If no offered player is in the wanted list, call `/shop_player/drop`.
5. If one or more offered players are wanted and `r0` is not blocked, acquire the highest-priority wanted player.
6. Repeat until P reaches the reserve threshold, an API error occurs, or `maxListups` is reached.

## CLI Example

```bash
python3 scripts/run_websoccer_shop_player_auto_acquire.py \
  --profile-data /path/to/WebSoccer/Data \
  --wanted アルハライ,ニード \
  --blocked-release サローヤン,ロベルト \
  --position fw
```

Execute mode:

```bash
python3 scripts/run_websoccer_shop_player_auto_acquire.py \
  --profile-data /path/to/WebSoccer/Data \
  --wanted アルハライ,ニード \
  --blocked-release サローヤン,ロベルト \
  --position fw \
  --execute
```

## JSON Config

```json
{
  "wanted": ["アルハライ", "ニード", 545],
  "blockedRelease": ["サローヤン", "ロベルト"],
  "position": "fw",
  "reserveP": 100,
  "maxListups": 50,
  "listupType": 1
}
```

Run with:

```bash
python3 scripts/run_websoccer_shop_player_auto_acquire.py --config config/shop_player_team005.json --execute
```

`position` may be `auto`, `fw`, `mf`, `df`, `gk`, or `omakase`. In `auto`, the script uses the only wanted-player position when all wanted players share one position; otherwise it uses `omakase`.
