import bpy, time
from .common import *
from bpy.app.handlers import persistent

# Node tree names
OVERLAY_NORMAL = '~TL Overlay Normal'
STRAIGHT_OVER = '~TL Straight Over Mix'
CHECK_INPUT_NORMAL = '~TL Check Input Normal'
FLIP_BACKFACE_NORMAL = '~TL Flip Backface Normal'
NEIGHBOR_UV ='~TL Neighbor UV'
FINE_BUMP ='~TL Fine Bump'

# Modifier tree names
MOD_RGB2INT = '~TL Mod RGB To Intensity'
MOD_INVERT = '~TL Mod Invert'
MOD_INVERT_VALUE = '~TL Mod Invert Value'
MOD_MULTIPLIER = '~TL Mod Multiplier'
MOD_MULTIPLIER_VALUE = '~TL Mod Multiplier Value'

tree_lib_names = {
        OVERLAY_NORMAL,
        STRAIGHT_OVER,
        CHECK_INPUT_NORMAL,
        FLIP_BACKFACE_NORMAL,

        MOD_RGB2INT,
        MOD_INVERT,
        MOD_INVERT_VALUE,
        MOD_MULTIPLIER,
        MOD_MULTIPLIER_VALUE,
        }

def load_custom_icons():
    # Custom Icon
    global custom_icons
    custom_icons = bpy.utils.previews.new()
    filepath = get_addon_filepath() + 'icons' + os.sep
    custom_icons.load('asterisk', filepath + 'asterisk_icon.png', 'IMAGE')

    custom_icons.load('channels', filepath + 'channels_icon.png', 'IMAGE')
    custom_icons.load('rgb_channel', filepath + 'rgb_channel_icon.png', 'IMAGE')
    custom_icons.load('value_channel', filepath + 'value_channel_icon.png', 'IMAGE')
    custom_icons.load('vector_channel', filepath + 'vector_channel_icon.png', 'IMAGE')

    custom_icons.load('add_modifier', filepath + 'add_modifier_icon.png', 'IMAGE')
    custom_icons.load('add_mask', filepath + 'add_mask_icon.png', 'IMAGE')

    custom_icons.load('collapsed_texture', filepath + 'collapsed_texture_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_texture', filepath + 'uncollapsed_texture_icon.png', 'IMAGE')
    custom_icons.load('collapsed_image', filepath + 'collapsed_image_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_image', filepath + 'uncollapsed_image_icon.png', 'IMAGE')
    custom_icons.load('collapsed_modifier', filepath + 'collapsed_modifier_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_modifier', filepath + 'uncollapsed_modifier_icon.png', 'IMAGE')
    custom_icons.load('collapsed_input', filepath + 'collapsed_input_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_input', filepath + 'uncollapsed_input_icon.png', 'IMAGE')
    custom_icons.load('collapsed_uv', filepath + 'collapsed_uv_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_uv', filepath + 'uncollapsed_uv_icon.png', 'IMAGE')

    custom_icons.load('collapsed_rgb_channel', filepath + 'collapsed_rgb_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_rgb_channel', filepath + 'uncollapsed_rgb_icon.png', 'IMAGE')
    custom_icons.load('collapsed_value_channel', filepath + 'collapsed_value_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_value_channel', filepath + 'uncollapsed_value_icon.png', 'IMAGE')
    custom_icons.load('collapsed_vector_channel', filepath + 'collapsed_vector_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_vector_channel', filepath + 'uncollapsed_vector_icon.png', 'IMAGE')

def get_node_tree_lib(name):
    # Node groups necessary are in nodegroups_lib.blend
    filepath = get_addon_filepath() + "lib.blend"

    with bpy.data.libraries.load(filepath) as (data_from, data_to):

        # Load node groups
        exist_groups = [ng.name for ng in bpy.data.node_groups]
        for ng in data_from.node_groups:
            if ng == name and ng not in exist_groups:
                data_to.node_groups.append(ng)
                break

    return bpy.data.node_groups.get(name)

#@persistent
#def load_libraries(scene):
#    # Node groups necessary are in nodegroups_lib.blend
#    filepath = get_addon_filepath() + "lib.blend"
#
#    with bpy.data.libraries.load(filepath) as (data_from, data_to):
#
#        # Load node groups
#        exist_groups = [ng.name for ng in bpy.data.node_groups]
#        for ng in data_from.node_groups:
#            if ng not in exist_groups:
#                data_to.node_groups.append(ng)

@persistent
def update_node_tree_libs(name):
    T = time.time()

    filepath = get_addon_filepath() + "lib.blend"

    if bpy.data.filepath == filepath: return

    trees = []
    tree_names = []
    exist_groups = [ng.name for ng in bpy.data.node_groups if ng.name in tree_lib_names]

    if not exist_groups: return

    # Load node groups
    with bpy.data.libraries.load(filepath) as (data_from, data_to):
        for ng in data_from.node_groups:
            if ng in exist_groups:
                tree = bpy.data.node_groups.get(ng)
                tree.name += '__OLD'
                trees.append(tree)
                tree_names.append(ng)
                data_to.node_groups.append(ng)

    for i, name in enumerate(tree_names):
        update = False

        cur_tree = trees[i]
        cur_ver = cur_tree.nodes.get('version')
        lib_tree = bpy.data.node_groups.get(name)
        lib_ver = lib_tree.nodes.get('version')

        # Check lib tree version
        if cur_ver:
            cur_ver = float(cur_ver.label)

        if lib_ver:
            lib_ver = float(lib_ver.label)

            # Update tree if current version isn't found or older than lib version
            if not cur_ver or (cur_ver and lib_ver > cur_ver):
                update = True

        if update:
            # Search for old tree usages
            for mat in bpy.data.materials:
                if not mat.node_tree: continue
                for node in mat.node_tree.nodes:
                    if node.type == 'GROUP' and node.node_tree == cur_tree:
                        node.node_tree = lib_tree
            for group in bpy.data.node_groups:
                for node in group.nodes:
                    if node.type == 'GROUP' and node.node_tree == cur_tree:
                        node.node_tree = lib_tree

            # Remove old tree
            bpy.data.node_groups.remove(cur_tree)

            print('INFO: Node group', name, 'is updated to version', str(lib_ver) + '!')

        else:
            # Remove loaded lib tree
            bpy.data.node_groups.remove(lib_tree)

            # Bring back original tree name
            cur_tree.name = cur_tree.name[:-5]

    print('INFO: Node group libraries are checked at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def register():
    load_custom_icons()
    #bpy.app.handlers.load_post.append(load_libraries)
    bpy.app.handlers.load_post.append(update_node_tree_libs)

def unregister():
    global custom_icons
    bpy.utils.previews.remove(custom_icons)
    #bpy.app.handlers.load_post.remove(load_libraries)
    bpy.app.handlers.load_post.remove(update_node_tree_libs)
