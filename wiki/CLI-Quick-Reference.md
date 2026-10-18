# CLI Quick Reference

Use `./realme-buds --help` for full command details.

> Disable the plugin first so CLI control can use the RFCOMM channel.

## Common commands

```bash
./realme-buds anc status
./realme-buds anc on
./realme-buds anc off
./realme-buds anc transparency
./realme-buds anc cycle
```

```bash
./realme-buds eq status
./realme-buds eq list
./realme-buds eq set balanced
```

```bash
./realme-buds game status
./realme-buds game on
./realme-buds game off
```

```bash
./realme-buds wear status
./realme-buds wear on
./realme-buds wear off
./realme-buds wear mpris-status
```

```bash
./realme-buds multipoint status
./realme-buds multipoint on
./realme-buds multipoint off
```

```bash
./realme-buds find status
./realme-buds find left
./realme-buds find right
./realme-buds find both
./realme-buds find stop
```

```bash
./realme-buds gesture status
./realme-buds gesture list
./realme-buds gesture set left double_tap next_track
./realme-buds gesture set right long_press anc_cycle
./realme-buds gesture anc-modes anc transparency
```

```bash
./realme-buds diagnostics --report
```

## Multi-device explicit selection

```bash
./realme-buds devices
./realme-buds --device AA:BB:CC:DD:EE:FF status
```
