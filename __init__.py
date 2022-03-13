bl_info = {
    "name": "Ucupaint",
    "author": "Yusuf Umar, Agni Rakai Sahakarya",
    "version": (0, 9, 9),
    "blender": (2, 80, 0),
    "location": "Node Editor > Properties > PAINTERy",
    "description": "Special node to manage painting layers for Cycles and Eevee materials",
    "wiki_url": "http://github.com/ucupumar/ucupaint-wiki",
    "category": "Node",
}

if "bpy" in locals():
    import imp
    imp.reload(image_ops)
    imp.reload(common)
    imp.reload(bake_common)
    imp.reload(mesh_ops)
    imp.reload(lib)
    imp.reload(ui)
    imp.reload(subtree)
    imp.reload(node_arrangements)
    imp.reload(node_connections)
    imp.reload(preferences)
    imp.reload(vcol_editor)
    imp.reload(transition)
    imp.reload(BakeInfo)
    imp.reload(ImageAtlas)
    imp.reload(MaskModifier)
    imp.reload(Mask)
    imp.reload(Modifier)
    imp.reload(NormalMapModifier)
    imp.reload(Blur)
    imp.reload(Layer)
    imp.reload(Bake)
    imp.reload(BakeToLayer)
    imp.reload(Root)
else:
    from . import image_ops, common, bake_common, mesh_ops, lib, ui, subtree, node_arrangements, node_connections, preferences
    from . import vcol_editor, transition, BakeInfo, ImageAtlas, MaskModifier, Mask, Modifier, NormalMapModifier, Blur, Layer, Bake, BakeToLayer, Root

import bpy 

def register():
    image_ops.register()
    mesh_ops.register()
    preferences.register()
    lib.register()
    ui.register()
    vcol_editor.register()
    transition.register()
    BakeInfo.register()
    ImageAtlas.register()
    MaskModifier.register()
    Mask.register()
    Modifier.register()
    NormalMapModifier.register()
    Blur.register()
    Layer.register()
    Bake.register()
    BakeToLayer.register()
    Root.register()

    print('INFO: ' + bl_info['name'] + ' ' + common.get_current_version_str() + ' is registered!')

def unregister():
    image_ops.unregister()
    mesh_ops.unregister()
    preferences.unregister()
    lib.unregister()
    ui.unregister()
    vcol_editor.unregister()
    transition.unregister()
    BakeInfo.unregister()
    ImageAtlas.unregister()
    MaskModifier.unregister()
    Mask.unregister()
    Modifier.unregister()
    NormalMapModifier.unregister()
    Blur.unregister()
    Layer.unregister()
    Bake.unregister()
    BakeToLayer.unregister()
    Root.unregister()

    print('INFO: ' + bl_info['name'] + ' ' + common.get_current_version_str() + ' is unregistered!')

if __name__ == "__main__":
    register()
