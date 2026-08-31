# H3 resource decisions

## Active local runtime

| Resource | Role | Current gate |
|---|---|---|
| MiniMax H3 FL2VA | Final keyframe-led shots | Proven |
| Ref2VA | Image/video/audio references | Proven but not default final quality |
| FastH3 preview LoRA | Four-step animatics | Proven |
| Turbo v4 LoRA | Six-step production inserts | Proven |
| H3 LongVideos | Scene continuity and handoffs | Installed and proven on a 23.75s chain |
| H3 Audio T8 | Dialogue/audio planning, mixing and continuation | Nodes active; dialogue proof still required |
| ControlNet Union | Pose/depth/edge control | Loader-proven; controlled media proof still required |
| H3 latent upscaler | Higher-resolution refine | Node/model present; visual A/B still required |
| MiniMax Music 3 | Fully local scoring | Proven |

## Selective reference sources

- `javawock7618/comfy-MiniMax-H3-workflows`: reuse only the I2V, Ref2VA, Bridge, TTS, Music 3 and upscale patterns that fit the pinned runtime.
- `MiniMax-AI/awesome-minimax-h3-integration`: discovery and compatibility register; not executable production code.
- `CommunityVideo_Image_files/h3-prompting`: detailed schema and failure reference behind the condensed Skill Foundry skills.
- `H3_Prompt_Director_Shareable_Pack_v2_2026-08-13`: gold prompts, style, motion, audio and QA reference.
- `MiniMax_H3_CE_v0.2.json`: reference only; the live runtime still lacks 22 node types. Extract one useful feature at a time rather than installing the whole dependency graph.
- ADetailer TXT2IMG/IMG2IMG workflows: reference only; they currently lack 31/30 node types. Use only when a real keyframe/face-repair need appears.
- `message.txt`: shot-coverage idea source only. Its 30 half-second shots exceed H3's demonstrated prompt budget.
- `Hermes Multiverse — Product & Technical Specification.md`: software-product specification, not a cinematic-series bible.

## Skill Foundry planning chain

`character-sheet-design` → `h3-style-picker` → `storyboard-to-shots` → `multi-shot-storytelling` → `h3-prompt-crafting` → `h3-audio-dialogue-syntax` → `motion-notation-prompting` → `video-cost-routing`.

No further H3 plugin installation is authorised before the character/reference review unless a bounded proof demonstrates a specific missing capability.
