# Interpose

**Pose your own rig at a few key frames, and an AI motion model generates the movement between them, written back as keys on your rig's own controls.**

Interpose is a Blender extension for animators. You keep your rig, its controls and your key poses; a motion model (NVIDIA's Kimodo or ARDY for now, others can be added) generates the in-betweens from a text prompt ("a person walks forward and waves"), and the result comes back as ordinary keys you can edit. It works with Rigify, Auto-Rig Pro and CloudRig rigs, and with skeletons such as Mixamo characters, without any setup; other rigs are set up once.

It also retargets an animation from one armature to another, even when their rest poses don't match.

> **Status:** 0.1.0, the first public version. Tested on Windows 11 with an NVIDIA RTX 3090. Feedback and bug reports are welcome on the [issues page](https://github.com/Maxiriton/interpose/issues).

---

- [Features](#features)
- [Requirements](#requirements)
- [Installing the extension](#installing-the-extension)
- [Installing a model](#installing-a-model)
- [Setting up a rig](#setting-up-a-rig)
- [Generating the in-betweens](#generating-the-in-betweens)
- [Prompt segments](#prompt-segments)
- [Limits](#limits)
- [Troubleshooting](#troubleshooting)
- [Retargeting between two armatures](#retargeting-between-two-armatures)
- [Licences](#licences)
- [For developers](#for-developers)

## Features

- **Generate in-betweens** from your key poses and a text prompt, with a motion model running in its own process: Blender never freezes and never loads the model itself. Your keys are never overwritten; the result comes as **Generated** keys, and a generated key you edit becomes yours.
- **Your own rig**: the motion is written on your rig's controls. Limbs you posed in IK stay in IK: their IK controls follow the generated motion.
- **Any key poses**: two or more, one, or none at all (the prompt alone). A key pose can be partial: key only a hand, and the rest of the body is generated around it.
- **Prompt segments**: a track of prompts per character ("walks forward" for 3 s, then "turns and waves"...), drawn as bands in the Dope Sheet, the Timeline and the Graph Editor, edited with the mouse like NLA strips. Generate the whole track with the model's own transitions, or regenerate one segment alone.
- **Rig setup**: Rigify, Auto-Rig Pro and CloudRig rigs and skeletons (Mixamo, Unreal, SMPL, VRM, Daz, Character Creator...) set themselves up. Others are set up by picking their bones, and **Check Rig** tests what the controls really do.
- **Models installed for you**: the add-on installs a model (its Python, its packages, its weights) from its preferences, and checks the setup with a clear fix for each problem.
- **Several characters per scene**, each with its own prompt, segments and settings.
- **Retargeting** between two armatures with different rest poses, bone by bone.

## Requirements

- **Blender 5.2** or newer.
- **To generate**: an **NVIDIA GPU** with enough video memory, and disk space for the model. macOS can't generate (no NVIDIA GPUs); Linux should work but isn't tested yet. The retargeting and the rig setup work everywhere.

| Model | Video memory | Disk | Also needs |
|---|---|---|---|
| **Kimodo** | about 7 GB | about 12 GB | |
| **ARDY**, 8-bit text encoder (the default) | about 10 GB | about 15 GB | Visual Studio's C++ build tools on Windows (a C++ compiler elsewhere) for its post-processing; optional |
| **ARDY**, 4-bit text encoder | about 6 GB | about 12 GB | the same |
| **ARDY**, full text encoder | about 17 GB | about 23 GB | access to Meta's Llama 3 on Hugging Face |

- An internet connection for the install, and Blender's **Allow Online Access** on (**Edit > Preferences > System > Network**).

## Installing the extension

1. Download `interpose-<version>.zip` from the [Releases page](https://github.com/Maxiriton/interpose/releases). Don't unzip it.
2. In Blender, open **Edit > Preferences > Get Extensions**, click the arrow in the top right corner, then **Install from Disk...**, and choose the zip.
3. Interpose is enabled. Its panels are in the 3D Viewport's sidebar (press `N`), in the **Interpose** tab; the animation editors' headers get its buttons too.

To update, install the new zip the same way. Your models stay installed.

## Installing a model

The models aren't part of the extension: the add-on installs the one you choose, on your request, from its official sources. Open **Edit > Preferences > Add-ons > Interpose** and choose the model in **Backend**: its settings and its setup are shown below, with what it supports (text prompt, key poses, prompt segments, longest motion...). One model is loaded on the GPU at a time.

1. Click **Install** on a model. A dialog shows what it downloads, from where, how much, and the licences: read them, they apply to you (see [Licences](#licences)). Confirm.
2. The install runs in the background with its progress, a few minutes for several GB: its own Python and environment (with [uv](https://github.com/astral-sh/uv), downloaded once), its packages (the right PyTorch build for your GPU), its weights. **Cancel** stops it; **Resume Install** goes on where it stopped, after a failure too.
3. **Check Setup** says what is ready and what isn't, each problem with its fix: the environment, the packages, the GPU (PyTorch can use it, enough video memory), the weights.

Where things go:

- **Models Folder**: where the environments go. Empty: `%LOCALAPPDATA%\Interpose` on Windows, `~/.local/share/interpose` on Linux. Choose another drive if yours is short of space.
- Weights from Hugging Face go to its usual cache (`~/.cache/huggingface`), shared with your other tools: weights already there aren't downloaded again.
- **Existing Environment**: use a Python environment where the model is installed already (its Python executable), instead of installing it.
- **Remove** (the bin) deletes the model's environment and the weights installed with it; its weights in the Hugging Face cache too if you tick it, unless another model needs them. **Repair** makes the environment again and completes the weights.

**Gated weights (Hugging Face sign-in).** Kimodo and ARDY's default text encoder need no account. Only ARDY's **Full** text encoder uses Meta's Llama 3 8B Instruct as Meta publishes it, which you must ask access to:

1. Make a Hugging Face account and request access on [Llama 3's page](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct) (**Request Access** in the check opens it), and wait for it to be granted.
2. Click **Sign In**: a terminal opens running Hugging Face's own sign-in. Sign in there yourself (from the browser, or with a token you paste there).
3. **Install** again.

The add-on never asks for, reads, stores or sends your token: Hugging Face's library uses your sign-in by itself.

**The models:**

- **Kimodo** (NVIDIA): generates up to 10 s per prompt, at 30 fps. Installed from [Aero-Ex's fork](https://github.com/Aero-Ex/kimodo), which runs on Windows without a compiler and comes with a 4-bit text encoder (about 5 GB of video memory instead of 17, no gated weights). **Model**: **SOMA, v1.1** (the default) or **SOMA, v1**.
- **ARDY** (NVIDIA): generates window by window (2 s at a time), with no length limit, about a second for 5 s once loaded. **Model**: **SOMA, 30 fps** or **Core, 20 fps** (its own 27-joint skeleton). **Text Encoder**: **8-bit** (the default: 8 GB of video memory, loads in a few seconds), **4-bit** (4.7 GB, the motion a little further from the full one's) or **Full** (about 15 GB, a minute to load, gated). Without a C++ compiler it installs without its post-processing, and follows the key poses less exactly: install Visual Studio's C++ build tools (the "Desktop development with C++" workload), then **Repair**.
- After changing a model's setting, or updating the add-on, the header may say **Weights missing** or **Packages missing**: **Install** gets them (seconds when the weights are already there).

## Setting up a rig

Choose your character as the **Target** at the top of the **Retarget** panel (Interpose tab). That's all for most rigs: as soon as it is chosen, its **rig profile** is set up (the Generate panel says how).

- **Recognized rigs**: **Rigify**, **Auto-Rig Pro** and **CloudRig** get their preset, with their FK controls, IK/FK switches and IK snap.
- **Skeletons** animated directly, without controls (Mixamo, Unreal's mannequin, SMPL, VRM, Daz, Character Creator, a mocap or BVH import...), are recognized from their bone names and hierarchy. An FBX import standing Y-up, or a skeleton facing +Y, is fine.
- **Other rigs**: the **Rig Setup** panel maps the rig to humanoid roles (hips, spine, head, upper arm, forearm, hand, thigh, shin, foot...). **Detect Bones** finds what it can; pick a role's bone in the viewport (Pose Mode) and click the role's **eyedropper** for the rest. Required roles: hips, at least one spine bone, head, upper arms, forearms, hands, thighs, shins and feet. The roles are listed by body part, each one found, missing or optional.
  - **Separate Controls**, on a controller rig: each role has a bone to **read** (on Rigify, the `ORG-` bone, the result of FK and IK) and a control to **write** (on Rigify, the FK control).
  - **IK/FK Limbs** (sub-panel): for each limb, its FK controls, its IK/FK switch property, and how each IK control follows the generated motion (**IK snap**: **Follow** a bone, **Pole** in the limb's plane, **Rest**). A limb without IK snap stays in FK after generating. **Snap FK to IK** snaps the FK controls onto the IK pose on frames you list.
  - **Advanced** (sub-panel): per role, Use Translation and the offset mode (**Roll** copies the bone's direction: arms and legs; **Offset** the rotation from rest: spine, neck, head, feet).
  - The menu next to **Check Rig**: **Load Preset**, **Import Profile** / **Export Profile** (JSON, to reuse a profile on a similar rig), **Add Roles**.
- **Check Rig** tests the profile from the rig's rest pose: each written control is turned (its read bone must turn with it), each IK/FK limb is switched both ways (it must stay where it was). The pose is put back and nothing is keyed. Problems are listed in the panel; **Generate** runs the check itself the first time a profile is used, and an error stops it.
- The profile is stored on the armature data: objects sharing the armature share it, and it travels with a rig linked from a library. Set it up in the rig's own file; in a shot that links the rig, it is read-only (to change it in one shot only, override the armature data too: `rig.data = rig.data.override_create(remap_local_usages=True)`).

## Generating the in-betweens

1. **Choose the character** as the **Target** (see above).
2. **Key your poses** with the rig's controls. Any keyframe type works except **Generated**: Keyframe, Breakdown, Extreme... A frame is a key pose as soon as one of the profile's controls has a key there.
3. In the **Generate** panel (or the animation editors' header), write a **prompt**, what the character does ("A person walks forward and waves"), and choose a **seed**.
4. Click **Generate**. The panel and the status bar show the progress: the model's own steps, then the keys being written. **Esc** or the cancel button stops it, until the keys are being written (a few seconds; Blender stays responsive, you can look around but not edit).

The result is written on the rig's controls as **Generated** keys, on every frame between your first and last key pose. The generation becomes **prompt segment 1**, shown as a band in the timeline. Frames carrying one of your keys are never written; generating again replaces the Generated keys and keeps yours. The whole generation is one undo step.

The first generation starts the model (about 20 s; the header says **Starting**, then **Loading**). The model then stays loaded: the next generations take about 3 s with Kimodo and under a second with ARDY, plus the time to write the keys (on Rigify about 1 s for 120 frames, and as much again for the limbs in IK; more on a character whose meshes are heavy to deform). **Start** / **Stop** load the model ahead of time, or free the GPU.

- **Range**: **Key Poses** (the default) goes from the first key pose to the last one. **Custom** sets a start frame and a duration: generate from the **prompt alone** with no key pose (the motion starts where the character stands on the start frame, facing where it faces; on Rigify move or turn the **root** control), start from **one key pose** or end on one, or **extend** an animation past its last key pose. Key poses outside the range are ignored and never touched.
- **Limbs in IK** stay in IK. The motion is written to the FK controls: on each key pose the FK controls of a limb in IK are snapped to its IK pose first (keyed as normal keys), then its IK controls (hand, foot, pole...) follow the generated motion on every frame, as Generated keys, and the IK/FK switch goes back to what you left. Pose the limb in IK anywhere, and that frame is a key pose for the next generation. Your IK keys are kept.
- **Partial key poses**: a frame where you keyed only some controls (an arm, a foot...) pins only what you keyed: the hand or foot lands where your pose puts it (and the hips, always pinned on a constrained frame); keying the spine, the neck or the head pins the whole body. The rest of that frame is generated, and your keys stay as they are. Your keys are FK rotations, so if the generated body moves a lot there, the hand can land away from where you posed it: key the body as well to keep the whole pose.
- **Editing a Generated key makes it yours**: as soon as you change a generated key (move it, or key over it after posing the rig), it becomes a **Keyframe**, and the next generation uses it as a key pose. Cancel the move (right click) and it goes back to Generated. **Key > Keyframe Type** promotes a key without changing it.
- **Clear Generated Keys** (Generate panel, Interpose menu) removes what the add-on put on the character: its Generated keys, and the keys it made on your key poses (FK controls snapped to your IK pose, IK controls, an IK/FK switch keyed in FK), even on protected bone collections. A key it made that you changed since is yours, and stays. A control left without keys goes back to its rest pose. One undo step.
- Other scene frame rates than the model's are handled: the key poses land exactly on the model's frames and the result is resampled. A character facing any direction, anywhere in the scene, works.
- The model's skeleton is added to the scene as a hidden armature, in an **Interpose Models** collection, next to your character.

## Prompt segments

A character can follow several prompts one after the other: "walks forward" for 3 s, then "turns left and waves" for 2 s... Each **segment** has a start, an end, a prompt and a seed. Segments follow each other with no gap, like a track; your key poses stay constraints inside them.

- **The first generation makes segment 1**; **Add Prompt Segment** (the **+** in the Generate panel) makes it too before generating, and adds the next ones at the end of the track (2 s, no prompt yet). The panel shows the **active** segment (its prompt, seed, start and end); the arrows go to the previous or next one; **−** removes it (the one before takes its frames); the split button cuts the segment under the current frame in two.
- **The bands** at the bottom of the **Dope Sheet**, the **Timeline** and the **Graph Editor** show the panel's character (before its first segment, a band with only its name and a **+** to add one), then the other selected characters with segments. A band shows each prompt, its frames and seed, your key poses (small diamonds) and the transitions. A hatched segment hasn't been generated, or was edited since. **View > Show Prompt Segments** (or the eye in the header) hides them.
- **With the mouse**, like NLA strips: **click** a segment to make it active (a click on a name makes that character the panel's), **drag** a boundary to move it (the neighbour adapts) or drag a segment to move both its boundaries; **Esc** or a right click cancels. **Double click** opens the segment's prompt, seed and frames; **right click** opens its menu: Edit, Split at Current Frame, Add, Remove, Regenerate Segment, Generate Whole Track. **+** after the track adds a segment. Each change is one undo step.
- **The animation editors' header** shows the model's state (with a start button when it isn't loaded) and **Generate**, or the progress bar and its cancel button while generating. The **Interpose** menu next to it has the rest: generate, regenerate the active segment, edit, add, split or remove a segment, Clear Generated Keys, start or stop the model, its errors, the preferences.
- **Generate** in the header (or **Generate Whole Track**) generates the whole track at once, with the model's own transitions between the segments. Kimodo generates up to 10 s per segment, the track can be longer; ARDY changes prompt at each boundary, with no length limit. Each segment lasts 0.5 s at least.
- **Regenerate Segment** (the segment's menu, its popup, the Interpose menu, the Generate panel) generates one segment again, with its own prompt and seed, and leaves the rest of the track as it is: only the segment's frames get new Generated keys, one undo step. The model joins the motion around it, so there is no jump at its boundaries. A neighbour never generated (hatched) isn't joined: generate it afterwards, or the whole track. To regenerate between two key poses, split the track there first.

## Limits

- **Fingers are not generated.** Kimodo and ARDY animate SOMA's 30-joint body; the fingers of their 77-joint output are a fixed relaxed pose. The add-on doesn't map fingers, so they keep your own animation (key them as you like, before or after generating).
- **NVIDIA GPUs only** for generating, Windows tested, Linux not yet; no macOS.
- **Humanoid characters only**: two arms, two legs, a spine and a head. Quadrupeds and props aren't generated.
- **Limbs posed in IK only**, with no FK control to write and no IK/FK switch (some older hand-made rigs), aren't supported: **Check Rig** names them.
- **Rigify's IK limbs are a little shorter than its FK ones**, so in IK the elbows and knees can sit 1 or 2 cm from the generated motion, and a knee doesn't fully straighten (where the generated leg straightens, it stays bent a few cm and can pop forward). Hands and feet follow the motion.
- Kimodo generates at most **10 s per prompt** (per segment with prompt segments).
- **One model on the GPU at a time**: choosing another one stops the previous one.
- The keys can't be written faster than Blender evaluates the rig on each frame: on a character with heavy meshes, writing takes longer than generating.

## Troubleshooting

- **The header says "not set up", "Weights missing" or "Packages missing"**: open the preferences, **Check Setup**, and follow the fix shown for each problem (usually **Install** or **Repair**).
- **The install fails right away**: Blender's **Allow Online Access** must be on (Preferences > System > Network). Look at the install log (the log button next to the model); **Resume Install** goes on where it stopped.
- **The check says a gated repository needs access, or that the sign-in expired**: request access on the repository's page, then **Sign In** (see [Installing a model](#installing-a-model)), then **Install** again.
- **Not enough video memory**: close other applications using the GPU, stop the other model, use ARDY's 8-bit or 4-bit text encoder, or Kimodo.
- **The check says PyTorch can't use the GPU**: update the NVIDIA driver. An RTX 50 series GPU gets a PyTorch build for it (CUDA 12.8) at the install; after changing the GPU, **Repair**.
- **Generate says the rig has a problem**: the Rig Setup panel lists what **Check Rig** found, each with its role. Fix the profile, or the rig, and run **Check Rig** again.
- **The character doesn't move, or only some limbs move**: check that the profile's roles are found (Rig Setup panel) and that your key poses are on the profile's controls. On Rigify, a limb in IK whose IK/FK switch is animated between key poses needs a key pose on the frames where it switches.
- **A pose came out wrong on one frame**: key that frame yourself (it becomes a key pose), or regenerate the segment with another seed.
- **The model doesn't start**: the Interpose menu in the animation editors shows its last errors; the console (Window > Toggle System Console on Windows) has the details. Please include them in a bug report.

## Retargeting between two armatures

The **Retarget** panel copies an animation bone by bone from a *source* armature to a *target* armature, correcting the orientation differences between their rest poses and scaling the root motion to the target's size, and bakes it as keys on the target.

1. **Choose the armatures**: **Target** (the one that receives the animation), then **Source** (the one that holds it). The setup is stored on the target object, so each character keeps its own.
2. **Build the bone list**: **Set Up Bone List** lists every source bone and proposes a target bone by name (exact match first, then partial; a target bone is never used twice). Or **Import from JSON**.
3. **Review each row**: the target bone (empty: the source bone is ignored); **Roll** (the bones point the same way but twist differently) or **Offset** (the full rotation between the rest poses); the translation button for the bones carrying the root motion (usually `Root` and `Hips`).
4. **Translation Scale**: **Auto** computes the ratio of the two rigs' heights (check the heights it reports), or type your own.
5. **Retarget** bakes the animation on the target over the scene's frame range.

- **Record Correction**: when an offset is almost right, select the row, click it, rotate the target bone by hand, then **Finish Recording**: the difference is applied on top. **Update Correction** adds to it, **X** clears it.
- **Snap Active Bone** / **Snap Full Pose** align the target to the source on the current frame, to tune the setup before baking (Pose Mode).
- **Export to JSON** / **Import from JSON** save and load the bone list (names, offset modes, translation, corrections). The translation scale isn't saved: it depends on the two rigs.
- With a Rigify target, match the **FK** controls and set the limbs to FK.
- Retargeting scales the root motion, but can't remove foot sliding between legs of very different proportions.
- Files saved by older versions (one setup per scene) are moved onto their target armature when opened. Files saved when the add-on was called **Retargetor** are brought up to date when opened (save them again with Interpose); a rig linked from a library gets it when its own file is opened and saved.

## Licences

**Interpose** is free software under the [GNU General Public License, version 3 or later](LICENSE) (GPL-3.0-or-later).

**The extension contains no model and no weights.** When you click **Install**, it downloads them on your machine from their official sources, and **each one comes with its own licence, which applies to you** as its user; the install dialog lists them with their links. In short (this is not legal advice; read the licences themselves):

| Component | Source | Licence |
|---|---|---|
| Kimodo code | [nv-tlabs/kimodo](https://github.com/nv-tlabs/kimodo), installed from [Aero-Ex's fork](https://github.com/Aero-Ex/kimodo) | Apache-2.0 |
| Kimodo weights (SOMA-RP v1, v1.1) | [NVIDIA on Hugging Face](https://huggingface.co/nvidia/Kimodo-SOMA-RP-v1.1) | [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/) |
| ARDY code | [nv-tlabs/ardy](https://github.com/nv-tlabs/ardy) | Apache-2.0 |
| ARDY checkpoints (SOMA, Core) | NVIDIA on Hugging Face | [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/) |
| Text encoders: LLM2Vec on Meta Llama 3 8B Instruct, and its 4-bit and 8-bit builds (Aero-Ex, voxta) | [Meta](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct), [McGill-NLP](https://huggingface.co/McGill-NLP/LLM2Vec-Meta-Llama-3-8B-Instruct-mntp), Hugging Face | [Meta Llama 3 Community License](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct/blob/main/LICENSE) and Meta's Acceptable Use Policy |
| uv (installs the models' Python and packages) | [astral-sh/uv](https://github.com/astral-sh/uv), from PyPI | MIT or Apache-2.0 |
| PyTorch and the other Python packages | PyPI, PyTorch's index | their own licences (BSD, MIT, Apache-2.0...) |

What this means:

- **NVIDIA Open Model License**: the models can be used commercially; NVIDIA claims no ownership of the motions you generate, and you are responsible for how you use them. Bypassing a model's safety mechanisms ends the licence. Kimodo's SMPL-X variant, under NVIDIA's research-only licence, is not used.
- **Meta Llama 3 Community License**: commercial use is allowed (a company with more than 700 million monthly users needs Meta's agreement); its Acceptable Use Policy applies; Llama 3 and its outputs can't be used to improve another large language model. Here it only turns your prompt into the model's text features.
- The motions you generate are yours to use, within those licences.

**Built with Meta Llama 3.**

## For developers

The add-on's code is plain Python; the models run in worker processes with their own Python and talk to Blender over JSON lines, so a new model is a folder in `backends/` (see `backends/base.py`). [CLAUDE.md](CLAUDE.md) describes each file and the architecture rules, [ROADMAP.md](ROADMAP.md) the phases and decisions, [DESIGN.md](DESIGN.md) the data model.

- Tests: `python tests/run_tests.py` (see the file for its arguments: the spike outputs, a Kimodo environment, real rigs).
- The core can be used from scripts, without the scene properties: `core.retarget.snap.Retargeter(source, target, pairs, translation_scale)` snaps (`snap_pose`) or bakes (`bake(scene, view_layer, frames)`) a list of `BonePair`s, and `core.profile.compose(profile, joint_map, direction)` builds those pairs from a rig profile and a skeleton's role → joint map.
- Package: `blender --command extension build` in the repository's folder.

## Author

Henri Hebeisen
