# warframeBuild

A free, non-commercial build optimizer for Warframe primary and secondary weapons.

Pick a gun and the tool computes:

- **Max damage**: the highest burst DPS against a neutral target.
- **Recommended**: the best all-rounder, averaged across all factions.
- **Per faction**: one build tuned for each faction's damage-type modifiers.

Builds include the mods (with slot order for elements), exilus, arcane, Incarnon perks,
the Kuva/Tenet bonus element, and the forma needed to fit them.
The damage math follows the WARFRAME Wiki pages
[Damage/Calculation](https://wiki.warframe.com/w/Damage/Calculation) and
[Calculating Bonuses](https://wiki.warframe.com/w/Calculating_Bonuses).

Status: planning done, implementation starting. See [PLAN.md](PLAN.md).

## Repository

Developed on GitLab; GitHub is a read-only mirror.

## License

Code: [GNU AGPL-3.0](LICENSE).
Data: WFCD-derived data under MIT; WARFRAME Wiki-derived data under CC BY-NC-SA 3.0.
See [NOTICE](NOTICE) for details.

## Credits

- [Digital Extremes](https://www.digitalextremes.com/): Warframe is their trademark.
  This project is not affiliated with or endorsed by Digital Extremes.
- [Warframe Community Developers (WFCD)](https://github.com/WFCD): game data via
  [warframestat.us](https://api.warframestat.us) and `warframe-items`.
- [WARFRAME Wiki](https://wiki.warframe.com) contributors: damage formulas, Incarnon evolutions,
  faction modifiers, Archon Shards.
