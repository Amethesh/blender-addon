# Normal Axis Double Tap

A Blender 4.2+ extension. In Edit Mode, when you press **S / G / R** and then
tap an axis key **twice**, the second press constrains to the **Normal**
orientation instead of Local. The header Transform Orientation stays **Global**.

| Keys  | Stock Blender (header = Global) | With this extension |
|-------|---------------------------------|---------------------|
| `G X`   | Global X                      | Global X            |
| `G X X` | Local X                       | **Normal X**        |
| `G X X X` | no constraint               | no constraint       |

This also works for plane constraints (`Shift+X`, and so on) and for S and R.

## How it works

Blender's transform keeps three orientation slots. Each press of the same axis
key moves to the next one (`editors/transform/transform.cc`,
`transform_generics.cc`):

1. **1st press**: the header orientation (the scene's orientation slot).
2. **2nd press**: the operator's `orient_type` if one was passed. Without it,
   Blender uses Local when the header is Global, and Global otherwise.
3. **3rd press**: no constraint.

The add-on registers wrapper operators (`view3d.nadt_resize`,
`view3d.nadt_translate`, `view3d.nadt_rotate`) on S/G/R. When the header is
Global, the wrapper calls the real transform with
`orient_type='NORMAL'` and `'INVOKE_DEFAULT'`. For any other header
orientation, it calls the transform unchanged, so Blender's stock behavior is
kept.

> **Why the scene orientation isn't swapped:** setting the header slot to
> Normal during the transform makes the *first* press Normal and the second
> press Global. That is the reverse of what this add-on is for. Passing
> `orient_type` instead leaves the scene alone, so there's nothing to restore
> on confirm or cancel, and it needs no timers.

### Known side effect

When `orient_type` is passed, Blender also uses that orientation for an
**unconstrained** transform:

- **R with no axis** rotates around the selection's normal, not the view axis.
- **G with typed numbers and no axis** (for example `G 1 Enter`) moves along
  the Normal X axis, not the Global X axis.

Mouse-driven free moves and scaling behave as usual. If free rotation around
the view axis matters to you, turn off *Rotate (R)* in the preferences.

## Install

1. Build the package, either:
   - with Blender:
     `blender --command extension build --source-dir normal_axis_double_tap`
   - or by zipping the *contents* of `normal_axis_double_tap/` so that
     `blender_manifest.toml` sits at the zip root.
2. In Blender, go to **Edit → Preferences → Get Extensions**. Open the **⌄**
   menu (top right) and choose **Install from Disk…**, then pick the zip.
   You can also drag the zip into the Blender window.
3. Make sure **Normal Axis Double Tap** is enabled under **Add-ons**.

For development, you can instead symlink the `normal_axis_double_tap/` folder
into a local extensions repository, such as `.../extensions/user_default/`.

## Preferences

Open **Edit → Preferences → Add-ons → Normal Axis Double Tap**:

- **Scale (S)**, **Move (G)**, **Rotate (R)** turn the behavior on or off per
  tool. When one is off, its key passes through to Blender's default keymap.
- **Also in Object Mode** applies the same behavior in Object Mode. It is off
  by default.

The key bindings are in the add-on keyconfig. They appear in
**Preferences → Keymap** under *3D View → Mesh* and *3D View → Object Mode*,
where you can rebind them.

## Manual test checklist

Setup: open the default scene, select the cube, press **Tab** for Edit Mode,
and set the header Transform Orientation to **Global**. Rotate the cube first
(for example `R Z 30`) so that the Global, Local and Normal axes all differ.
Select one face.

**Core behavior (Edit Mode, header Global)**
- [ ] `G X`: the axis line and header text show **Global** X.
- [ ] `G X X`: the header text shows **Normal** X, and the line follows the face.
- [ ] `G X X X`: the constraint is removed.
- [ ] `S Z Z` scales along the face normal. `R Z Z` rotates around it.
- [ ] `G Shift+Z Shift+Z`: plane constraint in Normal space.
- [ ] `G G` still starts Edge/Vertex Slide.

**Header orientation is never changed**
- [ ] During each transform above, the header dropdown still shows Global.
- [ ] After confirming with **Enter** or LMB, the header is still Global.
- [ ] After cancelling with **Esc** or RMB, the header is still Global, and the
      mesh is back where it started.

**Non-Global header (stock behavior)**
- [ ] Set the header to Local. `G X` = Local, `G X X` = Global.
- [ ] Set the header to Normal. `G X` = Normal, `G X X` = Global.

**Undo / redo**
- [ ] After a transform, **Ctrl+Z** undoes it in a single step.
- [ ] The *Adjust Last Operation* panel (F9) shows Move/Resize/Rotate, and
      editing a value there works.

**Preferences**
- [ ] Turn off *Move (G)*. `G X X` goes back to Local X, and S/R still use Normal.
- [ ] Turn *Move (G)* back on. It works again without restarting Blender.
- [ ] With *Also in Object Mode* off, `G X X` in Object Mode gives Local X.
- [ ] With it on, `G X X` in Object Mode gives Normal X (the object's normal).

**Register / unregister**
- [ ] Disable the add-on. S/G/R behave as stock Blender, and no
      `Normal Double Tap` entries remain in the Keymap preferences.
- [ ] Re-enable it. The behavior comes back without errors in the console.
- [ ] Uninstall the extension. Blender shows no errors.
