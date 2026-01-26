bl_info = {
    "name": "Ucupaint",
    "author": "Yusuf Umar, Agni Rakai Sahakarya, Jan Bláha, Ahmad Rifai, morirain, Patrick W. Crawford, neomonkeus, Kareem Haddad, passivestar, Przemysław Bągard",
    "version": (2, 4, 3),
    "blender": (2, 80, 0),
    "location": "Node Editor > Properties > Ucupaint",
    "warning": "",
    "description": "Special node to manage painting layers for Cycles and Eevee materials",
    "wiki_url": "https://ucupumar.github.io/ucupaint-wiki/",
    "doc_url": "https://ucupumar.github.io/ucupaint-wiki/",
    "category": "Node",
}

if "bpy" in locals():
    import importlib
    importlib.reload(Localization)
    importlib.reload(BaseOperator)
    importlib.reload(image_ops)
    importlib.reload(common)
    importlib.reload(bake_common)
    importlib.reload(modifier_common)
    importlib.reload(lib)
    importlib.reload(Decal)
    importlib.reload(ui)
    importlib.reload(subtree)
    importlib.reload(transition_common)
    importlib.reload(input_outputs)
    importlib.reload(node_arrangements)
    importlib.reload(node_connections)
    importlib.reload(preferences)
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
    importlib.reload(addon_updater_ops)
    importlib.reload(Test)
    importlib.reload(credits_ui)
else:
    from . import Localization
    from . import BaseOperator, image_ops, common, bake_common, modifier_common, lib, Decal, ui, subtree, transition_common, input_outputs, node_arrangements, node_connections, preferences
    from . import vector_displacement_lib, vector_displacement
    from . import vcol_editor, transition, BakeTarget, BakeInfo, UDIM, ImageAtlas, MaskModifier, Mask, Modifier, NormalMapModifier, Layer, ListItem, Bake, BakeToLayer, Root, versioning
    from . import addon_updater_ops
    from . import Test
    from . import credits_ui

import bpy 

def register():
    Localization.register_module(ui)

    image_ops.register()
    preferences.register()
    lib.register()
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
    addon_updater_ops.register()
    Test.register()
    credits_ui.register()

    print('INFO: ' + common.get_addon_title() + ' ' + common.get_current_version_str() + ' is registered!')

def unregister():
    Localization.unregister_module(ui)

    credits_ui.unregister()
    image_ops.unregister()
    preferences.unregister()
    lib.unregister()
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
    addon_updater_ops.unregister()
    Test.unregister()

    print('INFO: ' + common.get_addon_title() + ' ' + common.get_current_version_str() + ' is unregistered!')

if __name__ == "__main__":
    register()
