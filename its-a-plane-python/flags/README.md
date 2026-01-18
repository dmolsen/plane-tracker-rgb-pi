# Flags

This folder contains simple on/off flags you can toggle by renaming files.

How to use:
- To enable a flag: rename `<name>.off` -> `<name>.on`
- To disable a flag: rename `<name>.on` -> `<name>.off`

Available flags:
- `force_fixture` (controls fixture flight data loading)
- `force_net_no_ssid`
- `force_net_no_wifi`
- `force_net_no_net`
- `force_net_api_down`

Example:
```
mv force_fixture.off force_fixture.on
```
