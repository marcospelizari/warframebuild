# warframeBuild

**Pick a gun. Get the build that kills fastest, and see why.**

warframeBuild is a free, non-commercial fan site for Warframe players. It works out the
best mods for every primary and secondary weapon in the game, so you can spend your time
playing instead of doing spreadsheet math.

## Why it exists

Modding a gun in Warframe is harder than it looks. Elements combine depending on which
slot each mod sits in, critical hits climb through tiers, armor and shields soak damage
differently, status effects stack and tick over time, and every faction takes more or less
damage from each element. A mod that looks strong on paper can be the weakest choice
against the enemies you actually fight.

Build guides usually give you one build and ask you to trust it. Damage calculators show
the numbers, but you have to know which build to try. warframeBuild does the searching for
you. It tries the mod combinations, scores each one in simulated Steel Path fights, keeps
the fastest, and shows you how it got there.

## What you get for each gun

- **A Recommended build**: one build you can leave equipped for everything, without swapping
  mods every mission.
- **A build for each faction**: Grineer, Corpus, Infested, Corrupted, Sentient, The Murmur,
  Scaldra and Techrot, each tuned to how that faction takes damage.
- **The complete setup**: the mods in slot order, the exilus mod, the arcane, Incarnon
  evolutions, the best Kuva, Tenet or Coda bonus element, and how many forma it needs.
- **Advice beside the build**: which Archon Shards and aura mods help this gun most.
- **What every mod is worth**: how much slower the build would kill without it.
- **Kill times you can read**: the time to kill each enemy, and a plain "not killed in 10 s"
  when the gun can't finish the job.
- **Your own version**: change any mod and the build is scored again on the spot. Share it
  with a link.
- **A primer build**, for guns that are good at spreading status effects: fire it for a
  moment, then switch to your main weapon, which hits the primed enemies harder.

The **Tier List** ranks every gun by how fast its Recommended build kills. The **Updates**
page shows what changed after each game update.

## How it decides

Each build is tested against a fixed set of Steel Path enemies at level 120, two from every
faction, with real armor, shields and faction weaknesses. The score is the average time it
takes to kill them, counting status damage over time and reloads. A faction build is scored
on that faction's enemies; the Recommended build is scored on all of them, with each
faction counting equally.

The damage rules follow the [WARFRAME Wiki](https://wiki.warframe.com) and are checked
against numbers read in the game's arsenal and Simulacrum.

## Honest about its limits

- **The numbers are estimates.** They are averages, and real fights vary. Check them in the
  arsenal.
- **Every assumption is listed** next to the build, with a link to its source: whether it
  aims for the head, the enemy level, how many stacks a conditional effect is given.
- **"Best found" is not "optimal".** When a gun has too many combinations to try them all,
  the site says so instead of claiming the perfect build.
- **What isn't calculated yet is marked.** If part of a gun, such as one of its Incarnon
  evolutions, isn't fully modelled, the page says so and warns that the build may be stronger.

## Scope

Primary and secondary weapons only, for now. Warframe abilities, companions and rivens are
not part of the builds yet. Melee and Warframes may come later.

## Status

In development, not yet online.

Developed on GitLab. This GitHub repository is a read-only mirror.

## Credits and license

Warframe is a trademark of [Digital Extremes](https://www.digitalextremes.com/). This is a
fan project, not affiliated with or endorsed by Digital Extremes.

Thanks to the [WARFRAME Wiki](https://wiki.warframe.com) contributors (damage rules,
Incarnon evolutions, enemies, faction modifiers, Archon Shards), the
[Warframe Community Developers](https://github.com/WFCD) (weapon data) and
[warframe-public-export-plus](https://github.com/calamity-inc/warframe-public-export-plus)
(Calamity, Inc. and AMelonInsideLemon: mod and weapon compatibility).

Code: [GNU AGPL-3.0](LICENSE). Data from WFCD and export-plus: MIT. Data from the WARFRAME Wiki,
and the builds computed from it: CC BY-NC-SA 3.0. Details in [NOTICE](NOTICE).
