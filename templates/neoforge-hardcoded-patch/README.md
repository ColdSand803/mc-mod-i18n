# mc-mod-i18n Hardcoded Patch Template

This is a minimal NeoForge 1.21.1 companion mod template for consuming the `hardcoded-map.json` exported by mc-mod-i18n.

## What it does

- Reads `config/mc-mod-i18n/hardcoded-map.json` at client startup.
- Replaces exact tooltip text matches through NeoForge `ItemTooltipEvent`.
- Accepts both simple string values and exported object values.

Supported map shapes:

```json
{
  "Copper": "铜",
  "Crystal": { "translation": "水晶" }
}
```

The object shape matches the web UI hardcoded workbench export:

```json
{
  "Copper": {
    "translation": "铜",
    "category": "tooltip",
    "risk": "medium",
    "class": "example.TooltipSource",
    "jar": "example.jar"
  }
}
```

## Build

Install JDK 21, then run:

```powershell
.\gradlew build
```

Copy the built jar from `build/libs/` into the Minecraft `mods` folder. Put the exported mapping at:

```text
config/mc-mod-i18n/hardcoded-map.json
```

## Scope

This MVP only handles tooltip lines. It proves the runtime-consumer path for hardcoded strings without pretending that a resource pack can replace Java literals. Additional entry points can be added later for screens, Ponder scenes, config comments, or mod-specific APIs.
