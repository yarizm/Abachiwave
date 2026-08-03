# CC0 Drum Sample Assets

Small CC0 drum samples used by the demo audio renderer.

All samples are sourced from the CC0 1.0 Universal licensed GitHub repository
[EwonRael/BushDrum](https://github.com/EwonRael/BushDrum). The repo ships a full
CC0 1.0 Universal license text at
`https://raw.githubusercontent.com/EwonRael/BushDrum/main/LICENSE`.

## Samples

| Logical file | Source URL |
| --- | --- |
| `kick.wav` | https://raw.githubusercontent.com/EwonRael/BushDrum/main/kick.wav |
| `snare.wav` | https://raw.githubusercontent.com/EwonRael/BushDrum/main/snare-m.wav |
| `closed_hat.wav` | https://raw.githubusercontent.com/EwonRael/BushDrum/main/hihat-closed.wav |
| `open_hat.wav` | https://raw.githubusercontent.com/EwonRael/BushDrum/main/hihat-open.wav |

Regenerate (idempotent, skips existing files):

```bash
uv run python scripts/fetch_cc0_samples.py
```
