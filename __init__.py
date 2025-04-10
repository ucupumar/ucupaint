bl_info = {
    "name": "Ucupaint",
    "author": "Yusuf Umar, Agni Rakai Sahakarya, Jan Bláha, Ahmad Rifai, morirain, Patrick W. Crawford, neomonkeus, Kareem Haddad, passivestar",
    "version": (2, 2, 2),
    "blender": (2, 76, 0),
    "location": "Node Editor > Properties > Ucupaint",
    "warning": "",
    "description": "Special node to manage painting layers for Cycles and Eevee materials",
    "wiki_url": "https://ucupumar.github.io/ucupaint-wiki/",
    "doc_url": "https://ucupumar.github.io/ucupaint-wiki/",
    "category": "Node",
}

if "bpy" in locals():
    import imp
    imp.reload(Localization)
    imp.reload(image_ops)
    imp.reload(common)
    imp.reload(bake_common)
    imp.reload(modifier_common)
    imp.reload(lib)
    imp.reload(ui)
    imp.reload(subtree)
    imp.reload(transition_common)
    imp.reload(input_outputs)
    imp.reload(node_arrangements)
    imp.reload(node_connections)
    imp.reload(preferences)
    imp.reload(vector_displacement_lib)
    imp.reload(vector_displacement)
    imp.reload(vcol_editor)
    imp.reload(transition)
    imp.reload(BakeTarget)
    imp.reload(BakeInfo)
    imp.reload(UDIM)
    imp.reload(ImageAtlas)
    imp.reload(MaskModifier)
    imp.reload(Mask)
    imp.reload(Modifier)
    imp.reload(NormalMapModifier)
    imp.reload(Layer)
    imp.reload(ListItem)
    imp.reload(Bake)
    imp.reload(BakeToLayer)
    imp.reload(Root)
    imp.reload(versioning)
    imp.reload(addon_updater_ops)
    imp.reload(Test)
else:
    from . import Localization
    from . import image_ops, common, bake_common, modifier_common, lib, ui, subtree, transition_common, input_outputs, node_arrangements, node_connections, preferences
    from . import vector_displacement_lib, vector_displacement
    from . import vcol_editor, transition, BakeTarget, BakeInfo, UDIM, ImageAtlas, MaskModifier, Mask, Modifier, NormalMapModifier, Layer, ListItem, Bake, BakeToLayer, Root, versioning
    from . import addon_updater_ops
    from . import Test

import bpy 

def register():
    Localization.register_module(ui)

    image_ops.register()
    preferences.register()
    lib.register()
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
    addon_updater_ops.register()
    Test.register()

    print('INFO: ' + common.get_addon_title() + ' ' + common.get_current_version_str() + ' is registered!')

def unregister():
    Localization.unregister_module(ui)

    image_ops.unregister()
    preferences.unregister()
    lib.unregister()
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
    addon_updater_ops.unregister()
    Test.unregister()

    print('INFO: ' + common.get_addon_title() + ' ' + common.get_current_version_str() + ' is unregistered!')

if __name__ == "__main__":
    register()
