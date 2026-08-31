# Character build requirements

## Decision

Yes. Character references can be added and improved later without blocking ad-hoc private video requests.

The studio has two separate contracts:

1. **Shot contract:** `productions/<project>/studio.toml` supplies an approved local keyframe, prompt, backend and quality route. This is what the current renderer consumes.
2. **Character-pack contract:** `assets/characters/<character_id>/` preserves reusable identity references, variants and review decisions. The renderer does not currently require or parse this manifest.

This is deliberate late binding: make a private one-off shot from a small approved reference packet now; complete or promote the reusable character pack later.

## Three operating levels

### 1. Minimum ad-hoc request packet

Enough to create one private production without first cleaning the whole character library:

- request or project name;
- character name or provisional `character_id`;
- one named `variant_id` (use `provisional` if undecided);
- one to five selected local reference-image paths;
- three to eight identity anchors that must not drift;
- required outfit, prop and scene details;
- target duration and format;
- voice mode: narrator, dialogue or silent;
- confirmation that the output remains local and private.

If an approved keyframe already exists, the shot can go straight into `studio.toml`. If only raw reference images exist, a local keyframe must be created and approved first. The current H3 runner animates approved keyframes; it does not create them.

A full character sheet, complete lore reconciliation and permanent manifest are **not** required for this lane.

### 2. Reusable character pack

Use this when a character will recur across shots or productions. It adds:

- stable identity and variant IDs;
- preserved source files;
- a written identity contract;
- default outfit, palette and signature props;
- approved derived keyframes or look proofs;
- review and canon status;
- provenance and conflict notes.

### 3. Advanced production references

Add only when the production needs them:

- expression and mouth-shape references;
- assigned local voice reference;
- hand and prop-grip detail;
- dynamic/action poses;
- multi-character scale and position maps;
- recurring-location turnarounds;
- deliberate style variants.

Do not delay narration-led or single-character work for these optional assets.

## What a complete reference set looks like

### Identity minimum

- one clear primary image;
- full face visible;
- hair, eyes, skin tone and distinctive marks readable;
- default outfit and colour anchors visible;
- character shown at a useful scale rather than buried in a group image.

### Reusable production set

- front, three-quarter, side and back views where available;
- full-body neutral pose;
- neutral, joy, anger, sorrow and surprise expressions;
- outfit front/back and material details;
- signature prop on its own and held correctly;
- one or more approved cinematic keyframes proving the design works outside a turnaround sheet.

### Dialogue/action extension

- mouth closed plus useful speech shapes;
- close facial-expression range;
- hands holding required props;
- walking, running, seated and action poses as needed;
- local voice ID or consented voice source;
- two-shot references showing relative height and left-to-right identity mapping.

These are target requirements, not prerequisites for the first ad-hoc request.

## Source material is not production truth

The upstream repository and the split image library contain mixed material:

- confirmed lore;
- unconfirmed descriptions;
- third-party or cameo references;
- visual ideas;
- generated interpretations;
- contradictory variants.

Treat all of it as **source evidence**, not automatically as canonical production truth.

Repository roles remain separate:

- `characters/<slug>.md` — lore, roles, confidence notes and public archive context;
- `assets/characters/<slug>/source/` — selected original media used for production;
- `assets/characters/<slug>/variations/` — approved local derivatives, keyframes and look proofs;
- `assets/characters/<slug>/README.md` — reconciliation and provenance notes;
- `assets/characters/<slug>/manifest.yaml` — the current reusable-pack intake record.

Do not copy the whole external image library into the repository. Select only the files needed for the current character or request. Preserve the larger raw library in place.

## Chopping, changing and reconciling upstream information

Editing is allowed in the **curation layer**, never by silently rewriting the original evidence.

For each character:

1. Record the upstream repository path and source revision in the character-pack README.
2. Preserve selected source images unchanged under `source/`.
3. Extract the useful information into four groups:
   - confirmed identity/lore;
   - unconfirmed claims;
   - visible design anchors;
   - production-only adaptation.
4. Remove contradictions from the production prompt by choosing one named variant.
5. Store alternate looks as separate `variant_id` values rather than averaging them together.
6. Record what was changed and why in the README or `notes`.
7. Update `characters/<slug>.md` only as a separate editorial decision. Asset intake must not silently redefine public lore.

Example:

```text
character_id: teknium
variant_id: triangular-shades-canon
```

and separately:

```text
character_id: teknium
variant_id: portal-visor-production
canon_status: alternate-production-interpretation
```

Both may coexist. Each production locks one variant.

## Local file structure

```text
assets/characters/<character_id>/
├── source/          # selected originals, unchanged
├── variations/      # approved local keyframes and look proofs
├── README.md        # provenance, conflicts and curation decisions
└── manifest.yaml    # reusable-pack intake record
```

Use lowercase stable IDs matching `^[a-z0-9][a-z0-9._-]*$`.

The existing `assets/characters/teknium/manifest.yaml` predates the newer private intake template and uses a different shape. Treat it as legacy evidence. New or next-touched packs should follow `assets/characters/_template/manifest.yaml`; do not block ad-hoc rendering on migrating old manifests.

## Manifest requirements

The current template contains:

- `schema_version`;
- `character_id`, `display_name`, `review_state`, `canon_status`, `variant_id`;
- `identity` fields;
- `default_outfit` and palette;
- `props`;
- `source_files`;
- `style_variants`;
- `ensemble_references`;
- optional local voice details;
- local/private policy and notes.

### Provisional pack

Set at least:

- `schema_version: 1`;
- stable `character_id` and `variant_id`;
- `display_name`;
- `review_state: pending`;
- `canon_status: unreviewed` or an explicit alternate status;
- the known identity anchors;
- selected `source_files`;
- `privacy.local_only: true`;
- `privacy.publish_allowed: false`.

### Approved reusable pack

Before marking `review_state: approved`, confirm:

- the identity contract is specific enough to reproduce;
- source paths exist and stay under the trusted repository root;
- default outfit, palette and signature props are recorded;
- the selected variant is unambiguous;
- at least one approved local keyframe or look proof exists under `variations/`;
- provenance and conflicts are recorded in the README/notes;
- any required style, ensemble or voice references are present.

Do not invent new manifest fields ad hoc. If the template needs structured per-image provenance later, revise and version the schema deliberately. Until then, keep detailed per-image provenance in the character README and use the existing manifest fields.

## Ad-hoc workflow that works now

1. Receive a short content brief plus selected reference paths.
2. Choose or assign provisional character and variant IDs.
3. Write a production-local identity fragment containing only the anchors needed for that request.
4. Create the keyframe locally, or accept a pre-approved local keyframe.
5. Review that keyframe for identity, outfit, prop and scene correctness.
6. Store the approved keyframe under the character pack or production folder inside the repository.
7. Reference it from `productions/<project>/studio.toml`.
8. Run `python3 -m pipeline.cli validate --manifest <project>/studio.toml --repo-root .`.
9. Render only after validation and keyframe approval.
10. After delivery, either leave the references provisional or promote useful material into a reusable pack.

The character-specific render blocker is an absent or unapproved local keyframe—not an incomplete permanent character library.

## Ad-hoc request template

```text
PROJECT OR REQUEST:
TYPE: advert / episode / test
CHARACTER NAME:
CHARACTER ID: existing or provisional
VARIANT ID: existing or provisional
SELECTED REFERENCE PATHS: 1–5 local files
IDENTITY ANCHORS: 3–8 points that must not change
OUTFIT / PROP:
SCENE OR ACTION:
DURATION:
FORMAT: 16:9 / 9:16 / both
VOICE: narrator / dialogue / silent
REQUIRED WORDS OR CTA:
KEYFRAME: existing approved path / create locally first
PRIVACY: local-private
```

This is enough to begin an ad-hoc request. The curator can complete the full character pack afterwards.

## Acceptance checks

### Ad-hoc ready

- [ ] Selected references are local and readable.
- [ ] Character and variant are named, even if provisional.
- [ ] Identity anchors are explicit.
- [ ] The keyframe is local, approved and physically contained under the repository root.
- [ ] The production manifest validates.
- [ ] Output remains local/private.

### Reusable-pack ready

- [ ] Source originals are preserved unchanged.
- [ ] The current template manifest parses.
- [ ] Character, variant and review status are explicit.
- [ ] Identity, outfit, palette and props are sufficient to reproduce the look.
- [ ] At least one approved local variation exists.
- [ ] Conflicts and production adaptations are documented.
- [ ] Style, ensemble and voice references are added only where required.

## Related files

- `assets/characters/_template/manifest.yaml` — current private intake template.
- `assets/characters/_template/README.md` — short intake rules.
- `docs/asset-intake.md` — existing source/variation separation.
- `docs/local-private-studio.md` — runner, privacy and delivery commands.
- `pipeline/studio.py` — the enforced project/shot contract.
- `productions/teknium-portal-sequence/v2/studio.toml` — working approved-keyframe example.
