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

# (KeyMap, KeyMapItem) pairs created by this add-on, removed on unregister.
_addon_keymaps = []


def _get_prefs(context):
    addon = context.preferences.addons.get(__package__)
    return addon.preferences if addon else None


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

        kwargs = {}
        if context.scene.transform_orientation_slots[0].type == 'GLOBAL':
            # Only affects the second axis press (see module docstring).
            kwargs["orient_type"] = 'NORMAL'

        # The transform runs modally and registers its own undo step and redo
        # panel when it finishes, so this wrapper stays out of the undo stack.
        op('INVOKE_DEFAULT', **kwargs)
        return {'FINISHED'}


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


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    _register_keymaps()


def unregister():
    _unregister_keymaps()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
