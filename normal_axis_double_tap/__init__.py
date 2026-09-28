# SPDX-License-Identifier: GPL-3.0-or-later

"""Normal Axis Double Tap.

Makes a second axis key press during Grab/Rotate/Scale constrain to the Normal
orientation instead of Local, while the header orientation stays Global.

How Blender cycles axis constraints (editors/transform/transform.cc,
transform_generics.cc): a transform keeps three orientation slots and every
press of the same axis key advances through them:

    1st press -> O_SCENE : the header orientation
    2nd press -> O_SET   : the operator's ``orient_type`` if it was passed,
                           otherwise Local (header Global) or Global (header not Global)
    3rd press -> no constraint

So invoking the transform with ``orient_type='NORMAL'`` while the header is
Global gives X = Global, X X = Normal. Nothing in the scene is modified, so
there is no state to restore after the transform confirms or cancels.

Blender 5.0 changed this: when ``orient_type`` is passed, the transform starts
in the O_SET slot, so the first axis press only moves to "no constraint" and
everything shifts by one (X = nothing, X X = Global, X X X = Normal). To undo
the shift, one extra AXIS_X modal event is fed to the transform when the S/G/R
key that launched it is released: from O_SET with no constraint, that event
moves to O_DEFAULT with no constraint. The release item lives in the active
keyconfig's "Transform Modal Map" and is only active from the moment the
wrapper launches a transform until that key is released, so other transforms
never see it.
"""

import bpy
from bpy.props import BoolProperty


# (wrapper idname, transform operator, key, preference attribute)
_TRANSFORMS = (
    ("view3d.nadt_resize", "resize", 'S', "use_scale"),
    ("view3d.nadt_translate", "translate", 'G', "use_move"),
    ("view3d.nadt_rotate", "rotate", 'R', "use_rotate"),
)

_KEYMAP_EDIT = "Mesh"
_KEYMAP_OBJECT = "Object Mode"
_KEYMAP_TRANSFORM_MODAL = "Transform Modal Map"

# Blender 5.0+ starts a transform that has ``orient_type`` set one step into
# the axis cycle (see module docstring).
_NEEDS_RELEASE_STEP = bpy.app.version >= (5, 0, 0)

_AXIS_KEYS = {'X', 'Y', 'Z'}

# (KeyMap, KeyMapItem) pairs created by this add-on, removed on unregister.
_addon_keymaps = []


def _get_prefs(context):
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


def _transform_modal_map():
    # Modal keymaps can't live in the add-on keyconfig, so the release items go
    # into the active keyconfig. They are looked up by value every time rather
    # than stored, because switching keymap presets frees that keyconfig.
    kc = bpy.context.window_manager.keyconfigs.active
    return kc.keymaps.get(_KEYMAP_TRANSFORM_MODAL) if kc else None


def _is_release_item(kmi):
    # Stock transform modal maps have no AXIS_X item on a key release.
    return kmi.propvalue == 'AXIS_X' and kmi.value == 'RELEASE' and kmi.any


def _release_item(key):
    """Return the release item for ``key``, creating it (inactive) on first use."""
    km = _transform_modal_map()
    if km is None:
        return None
    for kmi in km.keymap_items:
        if kmi.type == key and _is_release_item(kmi):
            return kmi
    kmi = km.keymap_items.new_modal('AXIS_X', key, 'RELEASE', any=True)
    kmi.active = False
    return kmi


def _deactivate_release_items():
    km = _transform_modal_map()
    if km is None:
        return
    for kmi in km.keymap_items:
        if _is_release_item(kmi):
            kmi.active = False


def _remove_release_items():
    km = _transform_modal_map()
    if km is None:
        return
    for kmi in [kmi for kmi in km.keymap_items if _is_release_item(kmi)]:
        km.keymap_items.remove(kmi)


def _transform_running(window):
    return any(
        op.bl_idname.startswith(("TRANSFORM_OT_", "transform."))
        for op in window.modal_operators
    )


class _NADT_TransformWrapper:
    bl_options = {'INTERNAL'}

    # Set by subclasses.
    transform_op = ""
    pref_attr = ""

    def invoke(self, context, event):
        prefs = _get_prefs(context)
        if prefs is None or not getattr(prefs, self.pref_attr):
            return {'PASS_THROUGH'}
        if context.mode == 'OBJECT' and not prefs.use_object_mode:
            return {'PASS_THROUGH'}

        op = getattr(bpy.ops.transform, self.transform_op)
        if not op.poll('INVOKE_DEFAULT'):
            return {'PASS_THROUGH'}

        use_normal = context.scene.transform_orientation_slots[0].type == 'GLOBAL'
        kwargs = {"orient_type": 'NORMAL'} if use_normal else {}

        # The transform runs modally and registers its own undo step and redo
        # panel when it finishes, so this wrapper stays out of the undo stack.
        result = op('INVOKE_DEFAULT', **kwargs)

        if not (use_normal and _NEEDS_RELEASE_STEP and 'RUNNING_MODAL' in result):
            return {'FINISHED'}
        kmi = _release_item(event.type)
        if kmi is None:
            return {'FINISHED'}

        # Stay above the transform's modal handler until the launch key is
        # released, so the release item can be switched off again right away.
        kmi.active = True
        self._key = event.type
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == self._key and event.value == 'RELEASE':
            # The transform below still receives this release and gets its extra
            # AXIS_X step; the deactivation applies from the next event loop.
            _deactivate_release_items()
            return {'FINISHED', 'PASS_THROUGH'}
        if not _transform_running(context.window):
            _deactivate_release_items()
            return {'FINISHED', 'PASS_THROUGH'}
        if event.type in _AXIS_KEYS and event.value == 'PRESS':
            # Axis key pressed while the launch key is still held: the transform
            # hasn't had its extra step yet, so this press would be misread.
            # Drop it; pressing the axis again after release works as expected.
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}


class VIEW3D_OT_nadt_resize(_NADT_TransformWrapper, bpy.types.Operator):
    """Scale, with a double-tapped axis constraining to Normal orientation"""
    bl_idname = "view3d.nadt_resize"
    bl_label = "Resize (Normal Double Tap)"
    transform_op = "resize"
    pref_attr = "use_scale"


class VIEW3D_OT_nadt_translate(_NADT_TransformWrapper, bpy.types.Operator):
    """Move, with a double-tapped axis constraining to Normal orientation"""
    bl_idname = "view3d.nadt_translate"
    bl_label = "Move (Normal Double Tap)"
    transform_op = "translate"
    pref_attr = "use_move"


class VIEW3D_OT_nadt_rotate(_NADT_TransformWrapper, bpy.types.Operator):
    """Rotate, with a double-tapped axis constraining to Normal orientation"""
    bl_idname = "view3d.nadt_rotate"
    bl_label = "Rotate (Normal Double Tap)"
    transform_op = "rotate"
    pref_attr = "use_rotate"


class NADT_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    use_scale: BoolProperty(
        name="Scale (S)",
        description="Double-tapping an axis while scaling constrains to Normal",
        default=True,
    )
    use_move: BoolProperty(
        name="Move (G)",
        description="Double-tapping an axis while moving constrains to Normal",
        default=True,
    )
    use_rotate: BoolProperty(
        name="Rotate (R)",
        description="Double-tapping an axis while rotating constrains to Normal",
        default=True,
    )
    use_object_mode: BoolProperty(
        name="Also in Object Mode",
        description="Apply the same behavior to S/G/R in Object Mode",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        col = layout.column(heading="Enable For")
        col.prop(self, "use_scale")
        col.prop(self, "use_move")
        col.prop(self, "use_rotate")
        layout.prop(self, "use_object_mode")
        layout.label(
            text="Only active while the header Transform Orientation is Global.",
            icon='INFO',
        )


_classes = (
    VIEW3D_OT_nadt_resize,
    VIEW3D_OT_nadt_translate,
    VIEW3D_OT_nadt_rotate,
    NADT_AddonPreferences,
)


def _register_keymaps():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        # Background mode has no add-on keyconfig.
        return
    for km_name in (_KEYMAP_EDIT, _KEYMAP_OBJECT):
        km = kc.keymaps.new(name=km_name, space_type='EMPTY')
        for idname, _transform_op, key, _pref_attr in _TRANSFORMS:
            kmi = km.keymap_items.new(idname, key, 'PRESS')
            _addon_keymaps.append((km, kmi))


def _unregister_keymaps():
    for km, kmi in _addon_keymaps:
        km.keymap_items.remove(kmi)
    _addon_keymaps.clear()
    _remove_release_items()


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    _register_keymaps()


def unregister():
    _unregister_keymaps()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
