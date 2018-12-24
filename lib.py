import bpy, time
from .common import *
from bpy.app.handlers import persistent

# Node tree names
OVERLAY_NORMAL = '~yPL Overlay Normal'
CHECK_INPUT_NORMAL = '~yPL Check Input Normal'

NORMAL_MAP = '~yPL Normal Map'

FLIP_BACKFACE_NORMAL = '~yPL Flip Backface Normal'
FLIP_BACKFACE_BUMP = '~yPL Flip Backface Bump'
FLIP_BACKFACE_TANGENT = '~yPL Flip Backface Tangent'
FLIP_BACKFACE_BITANGENT = '~yPL Flip Backface Bitangent'

STRAIGHT_OVER = '~yPL Straight Over Mix'
STRAIGHT_OVER_BW = '~yPL Straight Over Grayscale Mix'
STRAIGHT_OVER_VEC = '~yPL Straight Over Vector Mix'

STRAIGHT_OVER_BG = '~yPL Straight Over Background Mix'
STRAIGHT_OVER_BG_BW = '~yPL Straight Over Grayscale Background Mix'
STRAIGHT_OVER_BG_VEC = '~yPL Straight Over Vector Background Mix'

#STRAIGHT_OVER_BG_RAMP = '~yPL Straight Over Background Mix Ramp'

STRAIGHT_OVER_HACK = '~yPL Straight Over Hack'

NEIGHBOR_UV ='~yPL Neighbor UV'
NEIGHBOR_UV_TANGENT ='~yPL Neighbor UV (Tangent)'
NEIGHBOR_UV_OBJECT ='~yPL Neighbor UV (Object)'
NEIGHBOR_UV_CAMERA ='~yPL Neighbor UV (Camera)'
NEIGHBOR_UV_OTHER_UV ='~yPL Neighbor UV (Other UV)'
NEIGHBOR_FAKE ='~yPL Fake Neighbor'
FINE_BUMP ='~yPL Fine Bump'
CURVED_FINE_BUMP = '~yPL Curved Fine Bump'
FLIP_CURVED_FINE_BUMP = '~yPL Flip Curved Fine Bump'

TRANSITION_AO = '~yPL Transition AO'
TRANSITION_AO_BG_MIX = '~yPL Transition AO Background Mix'
TRANSITION_AO_STRAIGHT_OVER = '~yPL Transition AO Straight Over'
TRANSITION_AO_FLIP = '~yPL Transition AO Flip'

RAMP = '~yPL Ramp'
RAMP_STRAIGHT_OVER = '~yPL Ramp Straight Over'
RAMP_STRAIGHT_OVER_BG = '~yPL Ramp Straight Over Background'

RAMP_FLIP = '~yPL Ramp Flip'
RAMP_FLIP_BLEND = '~yPL Ramp Flip Blend'
RAMP_FLIP_MIX_BLEND = '~yPL Ramp Flip Mix Blend'
RAMP_FLIP_STRAIGHT_OVER_BLEND = '~yPL Ramp Flip Straight Over Blend'

VECTOR_MIX ='~yPL Vector Mix'
#INVERTED_MULTIPLIER ='~yPL Inverted Multiplier'
INTENSITY_MULTIPLIER ='~yPL Intensity Multiplier'
GET_BITANGENT ='~yPL Get Bitangent'
TEMP_BITANGENT = '~yPL Temp Bitangent'

PARALLAX_OCCLUSION = '~yPL Parallax Occlusion Mapping'

# Bake stuff
BAKE_NORMAL = '~yPL Bake Normal'

# SRGB Stuff
SRGB_2_LINEAR = '~yPL SRGB to Linear'

# Modifier tree names
MOD_RGB2INT = '~yPL Mod RGB To Intensity'
MOD_INT2RGB = '~yPL Mod Intensity To RGB'
MOD_OVERRIDE_COLOR = '~yPL Mod Override Color'
MOD_INVERT = '~yPL Mod Invert'
MOD_INVERT_VALUE = '~yPL Mod Invert Value'
MOD_MULTIPLIER = '~yPL Mod Multiplier'
MOD_MULTIPLIER_VALUE = '~yPL Mod Multiplier Value'
MOD_INTENSITY_HARDNESS = '~yPL Mod Intensity Hardness'

channel_custom_icon_dict = {
        'RGB' : 'rgb_channel',
        'VALUE' : 'value_channel',
        'NORMAL' : 'vector_channel',
        }

channel_icon_dict = {
        'RGB' : 'KEYTYPE_KEYFRAME_VEC',
        'VALUE' : 'HANDLETYPE_FREE_VEC',
        'NORMAL' : 'KEYTYPE_BREAKDOWN_VEC',
        }

def load_custom_icons():
    # Custom Icon
    if not hasattr(bpy.utils, 'previews'): return
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
    custom_icons.load('collapsed_mask', filepath + 'collapsed_mask_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_mask', filepath + 'uncollapsed_mask_icon.png', 'IMAGE')
    custom_icons.load('collapsed_vcol', filepath + 'collapsed_vcol_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_vcol', filepath + 'uncollapsed_vcol_icon.png', 'IMAGE')
    custom_icons.load('collapsed_color', filepath + 'collapsed_color_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_color', filepath + 'uncollapsed_color_icon.png', 'IMAGE')

    custom_icons.load('collapsed_channels', filepath + 'collapsed_channels_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_channels', filepath + 'uncollapsed_channels_icon.png', 'IMAGE')

    custom_icons.load('collapsed_rgb_channel', filepath + 'collapsed_rgb_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_rgb_channel', filepath + 'uncollapsed_rgb_icon.png', 'IMAGE')
    custom_icons.load('collapsed_value_channel', filepath + 'collapsed_value_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_value_channel', filepath + 'uncollapsed_value_icon.png', 'IMAGE')
    custom_icons.load('collapsed_vector_channel', filepath + 'collapsed_vector_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_vector_channel', filepath + 'uncollapsed_vector_icon.png', 'IMAGE')

def get_neighbor_uv_tree(texcoord_type, different_uv=False):
    if texcoord_type == 'UV':
        if different_uv: return get_node_tree_lib(NEIGHBOR_UV_OTHER_UV)
        return get_node_tree_lib(NEIGHBOR_UV_TANGENT)
    if texcoord_type in {'Generated', 'Normal', 'Object'}:
        return get_node_tree_lib(NEIGHBOR_UV_OBJECT)
    if texcoord_type in {'Camera', 'Window', 'Reflection'}: 
        return get_node_tree_lib(NEIGHBOR_UV_CAMERA)

def get_neighbor_uv_tree_name(texcoord_type, different_uv=False):
    if texcoord_type == 'UV':
        if different_uv: return NEIGHBOR_UV_OTHER_UV
        return NEIGHBOR_UV_TANGENT
    if texcoord_type in {'Generated', 'Normal', 'Object'}:
        return NEIGHBOR_UV_OBJECT
    if texcoord_type in {'Camera', 'Window', 'Reflection'}: 
        return NEIGHBOR_UV_CAMERA

def new_intensity_multiplier_node(tree, obj, prop, sharpness=1.0, label=''):
    if label == '': label = 'Intensity Multiplier'
    im = new_node(tree, obj, prop, 'ShaderNodeGroup', label)
    im.node_tree = get_node_tree_lib(INTENSITY_MULTIPLIER)
    im.inputs[1].default_value = sharpness
    im.inputs['Sharpen'].default_value = 1.0

    if BLENDER_28_GROUP_INPUT_HACK:
        duplicate_lib_node_tree(im)

    #m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', obj.path_from_id())
    #if m:
    #    yp = obj.id_data.yp
    #    root_ch = yp.channels[int(m.group(2))]
    #    print(root_ch.name, prop)

    return im

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

    tree_names = []
    exist_groups = []
    for ng in bpy.data.node_groups:
        m = re.match(r'^(~yPL .+?)(?:_Copy?)?(?:\.\d{3}?)?$', ng.name)
        if m and m.group(1) not in exist_groups:
            exist_groups.append(m.group(1))
        #if ng.name.startswith('~yPL '):
        #    exist_groups.append(ng.name)

    if not exist_groups: return

    #print(exist_groups)

    # Load node groups
    with bpy.data.libraries.load(filepath) as (data_from, data_to):
        for ng in data_from.node_groups:
            if ng in exist_groups:
                tree = bpy.data.node_groups.get(ng)
                if tree:
                    tree.name += '__OLD'
                tree_names.append(ng)
                data_to.node_groups.append(ng)

    update_names = []

    #print(tree_names)

    for i, name in enumerate(tree_names):

        lib_tree = bpy.data.node_groups.get(name)
        lib_ver = lib_tree.nodes.get('revision')

        cur_tree = bpy.data.node_groups.get(name+'__OLD')

        # If not found, check if node is duplicated
        if not cur_tree:
            #print(name)
            cur_tree = [n for n in bpy.data.node_groups if n.name.startswith(name) and n.name != name][0]

        cur_ver = cur_tree.nodes.get('revision')

        # Check lib tree revision
        if cur_ver:
            m = re.match(r'.*(\d)', cur_ver.label)
            try: cur_ver = int(m.group(1))
            except: cur_ver = 0
        else: cur_ver = 0

        if lib_ver:
            m = re.match(r'.*(\d)', lib_ver.label)
            try: lib_ver = int(m.group(1))
            except: lib_ver = 0
        else: lib_ver = 0

        #print(name, cur_ver, lib_ver)

        if lib_ver > cur_ver:

            if name not in update_names:
                update_names.append(name)

            # Check for group inside group
            for n in lib_tree.nodes:
                if n.type == 'GROUP' and n.node_tree and n.node_tree.name not in update_names:
                    update_names.append(n.node_tree.name)

            print('INFO: Updating Node group', name, 'to revision', str(lib_ver) + '!')

    #print(update_names)

    for name in tree_names:

        lib_tree = bpy.data.node_groups.get(name)
        cur_tree = bpy.data.node_groups.get(name + '__OLD')

        if cur_tree:

            if name in update_names:

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

                # Create info frames
                create_info_nodes(lib_tree)

            else:
                # Remove loaded lib tree
                bpy.data.node_groups.remove(lib_tree)

                # Bring back original tree name
                cur_tree.name = cur_tree.name[:-5]
        else:

            cur_trees = [n for n in bpy.data.node_groups if n.name.startswith(name) and n.name != name]
            #print(cur_trees)

            if name in update_names:

                for cur_tree in cur_trees:

                    used_nodes = []

                    # Search for old tree usages
                    for mat in bpy.data.materials:
                        if not mat.node_tree: continue
                        for node in mat.node_tree.nodes:
                            if node.type == 'GROUP' and node.node_tree == cur_tree:
                                used_nodes.append(node)

                    for group in bpy.data.node_groups:
                        for node in group.nodes:
                            if node.type == 'GROUP' and node.node_tree == cur_tree:
                                used_nodes.append(node)

                    #print(used_nodes)

                    if used_nodes:

                        # Remember original tree
                        ori_tree = used_nodes[0].node_tree

                        # Duplicate lib tree
                        lib_tree.name += '_Copy'
                        used_nodes[0].node_tree = lib_tree.copy()
                        new_tree = used_nodes[0].node_tree
                        lib_tree.name = name

                        for node in used_nodes:
                            node.node_tree = new_tree

                        # Copy some nodes inside
                        for n in new_tree.nodes:
                            if n.name.startswith('_'):
                                # Try to get the node on original tree
                                ori_n = ori_tree.nodes.get(n.name)
                                if ori_n: copy_node_props(ori_n, n)

                        # Delete original tree
                        bpy.data.node_groups.remove(ori_tree)

                        # Create info frames
                        create_info_nodes(new_tree)

            # Remove lib tree
            bpy.data.node_groups.remove(lib_tree)

    print('INFO: ' + ADDON_TITLE + ' Node group libraries are checked at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def register():
    load_custom_icons()
    #bpy.app.handlers.load_post.append(load_libraries)
    bpy.app.handlers.load_post.append(update_node_tree_libs)

def unregister():
    global custom_icons
    if hasattr(bpy.utils, 'previews'):
        bpy.utils.previews.remove(custom_icons)
    #bpy.app.handlers.load_post.remove(load_libraries)
    bpy.app.handlers.load_post.remove(update_node_tree_libs)
