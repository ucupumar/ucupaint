# TODO (Immediate):
# - Musgrave texture (V)
# - Masking (Per texture and modifier)
# - Global mask setting
#   - Bump
#   - Ramp
# - Mask switcher on the list (V)
# - Texture group/folder
# - Eraser brush (check for ypanel implementation)
# - Check for more consistent class names and properties
#
# TODO:
# - Replace total mask node and implement transition bump/ramp chain system
# - Flip bump mode
#   - Crease
#   - Force Transparent
# - Color layer (?)
# - Upper layer affect below layer (?):
#    - Refraction (?)
#    - Blur (?)
# - Bump root channel (??)
# - Matcap view on Normal preview
# - Per texture preview
# - Bake channel
# - 'Ignore below' blend for bake channel result
# - Bake pointiness, AO 
# - Blur UV (?)
# - Texture Group bake proxy
# - Eevee support
# - Armory support (X, proper bake system is better be the solution)
#
# TODO OPT:
# - Lazy node calling (can be useful to prevent missing error)
#
# BUGS:
# - Fine bump still produces wrong result when using non UV texture mapping (V)
# - Sharp bump can cause bleed on color channel (V)
# - Value channel should output only grayscale (V)
# - Musgrave fine bump cannot read below 0.0
#
# KNOWN ISSUES:
# - Cycles has limit of 32 images per material, NOT per node_tree
# - Limit decrease to 20 images if alpha is used
# - Use of cineon images will cause crash (??)

bl_info = {
    "name": "yTexLayers",
    "author": "Yusuf Umar",
    "version": (0, 1, 0),
    "blender": (2, 79, 0),
    "location": "Node Editor > Properties > Texture Layers",
    "description": "Special node to manage texture layers for Cycles materials",
    "warning" : "This is alpha version, incompability to future releases might happen",
    #"wiki_url": "http://patreon.com/ucupumar",
    "category": "Node",
}

if "bpy" in locals():
    import imp
    imp.reload(image_ops)
    imp.reload(common)
    imp.reload(lib)
    imp.reload(ui)
    imp.reload(subtree)
    imp.reload(node_arrangements)
    imp.reload(node_connections)
    imp.reload(preferences)
    imp.reload(vcol_editor)
    imp.reload(Mask)
    imp.reload(Modifier)
    imp.reload(Blur)
    imp.reload(Layer)
    imp.reload(Root)
    #print("Reloaded multifiles")
else:
    from . import image_ops, common, lib, ui, subtree, node_arrangements, node_connections, preferences
    from . import vcol_editor, Mask, Modifier, Blur, Layer, Root
    #print("Imported multifiles")

import bpy 
#from bpy.app.translations import pgettext_iface as iface_

def register():
    # Register classes
    #bpy.utils.register_module(__name__)
    image_ops.register()
    preferences.register()
    lib.register()
    ui.register()
    vcol_editor.register()
    Mask.register()
    Modifier.register()
    Blur.register()
    Layer.register()
    Root.register()

    print('INFO: yTexLayers ' + common.get_current_version_str() + ' is registered!')

def unregister():
    # Remove classes
    #bpy.utils.unregister_module(__name__)
    image_ops.unregister()
    preferences.unregister()
    lib.unregister()
    ui.unregister()
    vcol_editor.unregister()
    Mask.unregister()
    Modifier.unregister()
    Blur.unregister()
    Layer.unregister()
    Root.unregister()

    print('INFO: yTexLayers ' + common.get_current_version_str() + ' is unregistered!')

if __name__ == "__main__":
    register()
