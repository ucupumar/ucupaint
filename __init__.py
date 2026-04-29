bl_info = {
    "name": "Ucupaint",
    "author": "Yusuf Umar, Agni Rakai Sahakarya, Jan Bláha, Ahmad Rifai, morirain, Patrick W. Crawford, neomonkeus, Kareem Haddad, passivestar, Przemysław Bągard",
    "version": (2, 4, 7),
    "blender": (2, 76, 0),
    "location": "Node Editor > Properties > Ucupaint",
    "warning": "",
    "description": "Special node to manage painting layers for Cycles and Eevee materials",
    "wiki_url": "https://ucupumar.github.io/ucupaint-wiki/",
    "doc_url": "https://ucupumar.github.io/ucupaint-wiki/",
    "category": "Node",
}

def is_available(module_relpath):
    import importlib.util
    return importlib.util.find_spec(module_relpath, package=__package__)

if "bpy" in locals():
    import importlib
    importlib.reload(common)
    if 'addon_updater_preferences' in locals(): importlib.reload(addon_updater_preferences)
    if 'credits_ui' in locals(): importlib.reload(credits_ui)
    importlib.reload(preferences)
    importlib.reload(lib)
    importlib.reload(BaseOperator)
    importlib.reload(Localization)
    importlib.reload(image_ops)
    importlib.reload(bake_common)
    importlib.reload(modifier_common)
    importlib.reload(Decal)
    importlib.reload(ui)
    importlib.reload(subtree)
    importlib.reload(transition_common)
    importlib.reload(input_outputs)
    importlib.reload(node_arrangements)
    importlib.reload(node_connections)
    importlib.reload(vector_displacement_lib)
    importlib.reload(vector_displacement)
    importlib.reload(vcol_editor)
    importlib.reload(transition)
    importlib.reload(BakeTarget)
    importlib.reload(BakeInfo)
    importlib.reload(UDIM)
    importlib.reload(ImageAtlas)
    importlib.reload(MaskModifier)
    importlib.reload(Mask)
    importlib.reload(Modifier)
    importlib.reload(NormalMapModifier)
    importlib.reload(Layer)
    importlib.reload(ListItem)
    importlib.reload(Bake)
    importlib.reload(BakeToLayer)
    importlib.reload(Root)
    importlib.reload(versioning)
    if 'addon_updater_ops' in locals(): importlib.reload(addon_updater_ops)
    if 'Test' in locals(): importlib.reload(Test)
    if 'psd_io' in locals(): importlib.reload(psd_io)
else:
    from . import common
    if is_available('.addon_updater_preferences'): from . import addon_updater_preferences
    if is_available('.credits_ui'): from . import credits_ui
    from . import preferences
    from . import lib
    from . import BaseOperator
    from . import Localization
    from . import image_ops, bake_common, modifier_common, Decal, ui, subtree, transition_common, input_outputs, node_arrangements, node_connections
    from . import vector_displacement_lib, vector_displacement
    from . import vcol_editor, transition, BakeTarget, BakeInfo, UDIM, ImageAtlas, MaskModifier, Mask, Modifier, NormalMapModifier, Layer, ListItem, Bake, BakeToLayer, Root, versioning
    if is_available('.addon_updater_ops'): from . import addon_updater_ops
    if is_available('.Test'): from . import Test
    if is_available('.psd_io'): from . import psd_io

import bpy

def register():
    if common.is_bl_newer_than(2, 80):
        # Checking other ucupaint installation
        package_names = ['ucupaint', 'ucupaint_plus', 'bl_ext.blender_org.ucupaint', 'bl_ext.user_default.ucupaint', 'bl_ext.user_default.ucupaint_plus']
        for pkg_name in package_names:
            if __package__ == pkg_name: continue
            addons = bpy.context.preferences.addons
            if pkg_name in addons:
                raise ValueError("Another ucupaint version is installed, please disable it first.")

    if 'credits_ui' in globals(): credits_ui.register()
    preferences.register()
    lib.register()
        
    Localization.register_module(ui)

    image_ops.register()
    Decal.register()
    ui.register()
    vcol_editor.register()
    transition.register()
    vector_displacement.register()
    BakeTarget.register()
    BakeInfo.register()
    UDIM.register()
    ImageAtlas.register()
    MaskModifier.register()
    Mask.register()
    Modifier.register()
    NormalMapModifier.register()
    Layer.register()
    ListItem.register()
    Bake.register()
    BakeToLayer.register()
    Root.register()
    versioning.register()
    if 'addon_updater_ops' in globals(): addon_updater_ops.register()
    if 'Test' in globals(): Test.register()

    print('INFO: ' + common.get_addon_title() + ' ' + common.get_current_version_str() + ' is registered!')

def unregister():
    if 'credits_ui' in globals(): credits_ui.unregister()
    preferences.unregister()
    lib.unregister()

    Localization.unregister_module(ui)

    image_ops.unregister()
    Decal.unregister()
    ui.unregister()
    vcol_editor.unregister()
    transition.unregister()
    vector_displacement.unregister()
    BakeTarget.unregister()
    BakeInfo.unregister()
    UDIM.unregister()
    ImageAtlas.unregister()
    MaskModifier.unregister()
    Mask.unregister()
    Modifier.unregister()
    NormalMapModifier.unregister()
    Layer.unregister()
    ListItem.unregister()
    Bake.unregister()
    BakeToLayer.unregister()
    Root.unregister()
    versioning.unregister()
    if 'addon_updater_ops' in globals(): addon_updater_ops.unregister()
    if 'Test' in globals(): Test.unregister()

    print('INFO: ' + common.get_addon_title() + ' ' + common.get_current_version_str() + ' is unregistered!')

if __name__ == "__main__":
    register()
