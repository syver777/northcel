# Pattern sources

Ten complete, compiling `.ncel` films used by the
[patterns cookbook](../../docs/patterns/README.md). Each one renders every frame;
the docs check renders them again in CI.

| File | Pattern |
| --- | --- |
| `01-head-turn-6fps.ncel` | head turn in 6 fps cels |
| `02-blink.ncel` | blink |
| `03-jump-anticipation-squash.ncel` | jump with anticipation and squash |
| `04-colour-beat.ncel` | colour filling at a specific beat |
| `05-cloud-drift.ncel` | cloud drift |
| `06-progressive-assembly.ncel` | character assembled progressively |
| `07-duck-walk.ncel` | duck walk |
| `08-line-boil.ncel` | line boil |
| `09-crowd-swarm.ncel` | crowd as a swarm |
| `10-two-shot.ncel` | two-shot with a frame override |

```console
$ northcel check examples/patterns/01-head-turn-6fps.ncel
$ northcel film examples/patterns/01-head-turn-6fps.ncel -o frames/
```
