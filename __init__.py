# TODO (Immediate):
# - Musgrave texture (V)
# - Color layer (V)
# - Transparent/Background layer (V)
# - Eevee support (V)
# - Masking (V)
#   - Replace total mask node and implement transition bump/ramp chain system (V)
#   - Active Mask switcher on the list (V)
#   - Make sure mask has blending option consistency (X, Meh, its consistent enough)
# - Transition effects (V)
#   - Bump (V)
#   - Ramp (V)
#   - Flip bump mode (V)
#   - Crease (X, too bloated)
#   - AO (V)
#   - Make transition effect option hidden in add modifier menu (V)
#   - Option for transition ao link with channel intensity (V)
#   - Per channel transition edge intensity (V)
#   - AO option to exclude area within intensity (V)
#   - AO and ramp contribute to alpha
# - Texture group/folder
#   - Basic multilevel implementation (V)
#   - Works with mask and transition effects
# - New layer/mask improvements
#   - Open Image as Mask (V)
#   - Open Vcol as Mask/Layer (V)
#   - Add mask option when creating new layer (V)
#   - Remove RGB to Intensity when creating new layer bc its no longer necessary (X, why remove a feature?)
# - Lazy channel nodes (?)
#   - Nodes won't exists until it's enabled (X, replaced with next point)
#   - Blend nodes will be muted at default if not enabled
#   - Add option to Optimize the entire tl nodes
# - Make sure background layer blending and its ui is consistent (V)
# - Make sure there's no duplicate group when appending (V)
# - Every modifiers has intensity value for muting to prevent recompilation (V)
# - Fix change blend type behavior where it always delete previous node (V)
# - Add intensity multiplier to non transition bump (X, transition already do the job)
# - Oveeride color should be override value for value channel (V)
# - Make sure ui is expanded if modifier or transition is added (V)
# - Very large texture (UDIM like) to prevent number of image limits
# - Bake channel (& layer group)
# - Refactor for more consistent class names and properties
# - Multiple tl node selector from ui (V)
# - Fix backface consistency with Blender 2.8 & 2.7

# TODO:
# - Eraser brush (check for ypanel implementation)
# - Height based bump channel (similar to substance)
# - Upper layer affect below layer (?):
#   - Refraction
#   - Blur (X?, Already covered by native SSS)
# - Preview extra
#   - Matcap view on Normal preview
#   - Per texture preview
# - Bake extra
#   - Pointiness
#   - AO
#   - Highpoly
#   - Blur (can be only applied on select layer channel)
#   - 'Ignore below' blend for bake channel result
# - Duplicate layer
# - Armory support (X, proper bake system is better be the solution)
#
# TODO OPT:
# - Lazy node calling (can be useful to prevent missing error)
#
# BUGS:
# - Fine bump still produces wrong result when using non UV texture mapping (V)
# - Sharp bump can cause bleed on color channel (V)
# - Value channel should output only grayscale (V)
# - Wrong result after adding texture modifier (V, need more testing)
# - Transition AO at flip produce wrong result (V)
# - Bring back modifier on normal channel at Color layer (V)
# - Childen layers produce wrong result after delete parent only (V)
# - Float image still lose precision after packed (its very apparent on bump effect)
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
    imp.reload(transition)
    imp.reload(Mask)
    imp.reload(Modifier)
    imp.reload(Blur)
    imp.reload(Layer)
    imp.reload(Root)
    #print("Reloaded multifiles")
else:
    from . import image_ops, common, lib, ui, subtree, node_arrangements, node_connections, preferences
    from . import vcol_editor, transition, Mask, Modifier, Blur, Layer, Root
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
    transition.register()
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
    transition.unregister()
    Mask.unregister()
    Modifier.unregister()
    Blur.unregister()
    Layer.unregister()
    Root.unregister()

    print('INFO: yTexLayers ' + common.get_current_version_str() + ' is unregistered!')

if __name__ == "__main__":
    register()
