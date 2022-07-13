import bpy, time
from .common import *
from .subtree import *
from mathutils import *
from bpy.app.handlers import persistent
from distutils.version import LooseVersion #, StrictVersion
from .node_arrangements import *
from .node_connections import *

# Node tree names
OVERLAY_NORMAL = '~yPL Overlay Normal'
OVERLAY_NORMAL_STRAIGHT_OVER = '~yPL Overlay Normal Straight Over'
CHECK_INPUT_NORMAL = '~yPL Check Input Normal'

NORMAL_MAP = '~yPL Normal Map'
NORMAL_MAP_PREP = '~yPL Normal Map Preparation'

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

STRAIGHT_OVER_HEIGHT_MIX = '~yPL Straight Over Height Mix'
STRAIGHT_OVER_HEIGHT_ADD = '~yPL Straight Over Height Add'

#STRAIGHT_OVER_BG_RAMP = '~yPL Straight Over Background Mix Ramp'

SPREAD_ALPHA = '~yPL Spread Alpha'
SPREAD_ALPHA_SMOOTH = '~yPL Spread Alpha Smooth'
SPREAD_NORMALIZED_HEIGHT = '~yPL Spread Normalized Height'

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
#RAMP_STRAIGHT_OVER_BG = '~yPL Ramp Straight Over Background'
RAMP_BG_MIX_UNLINK = '~yPL Ramp Background Mix Unlink'
RAMP_BG_MIX_CHILD = '~yPL Ramp Background Mix Child'
RAMP_BG_MIX = '~yPL Ramp Background Mix'

RAMP_FLIP = '~yPL Ramp Flip'
RAMP_FLIP_BLEND = '~yPL Ramp Flip Blend'
RAMP_FLIP_MIX_BLEND = '~yPL Ramp Flip Mix Blend'
RAMP_FLIP_STRAIGHT_OVER_BLEND = '~yPL Ramp Flip Straight Over Blend'

VECTOR_MIX ='~yPL Vector Mix'
#INVERTED_MULTIPLIER ='~yPL Inverted Multiplier'
INTENSITY_MULTIPLIER ='~yPL Intensity Multiplier'
GET_BITANGENT ='~yPL Get Bitangent'
BITANGENT_FROM_NATIVE_TANGENT = '~yPL Bitangent from Native Tangent'
TANGENT_PROCESS = '~yPL Tangent Process'

PARALLAX_OCCLUSION = '~yPL Parallax Occlusion Mapping'
PARALLAX_OCCLUSION_PREP = '~yPL Parallax Occlusion Mapping Preparation'
PARALLAX_OCCLUSION_PREP_OBJECT = '~yPL Parallax Occlusion Mapping Preparation (Object)'
PARALLAX_OCCLUSION_PREP_CAMERA = '~yPL Parallax Occlusion Mapping Preparation (Camera)'
PARALLAX_OCCLUSION_PROC = '~yPL Parallax Occlusion Mapping Process'

HEIGHT_SCALE = '~yPL Height Scale'
HEIGHT_SCALE_TRANS_BUMP = '~yPL Height Scale Transition Bump'
HEIGHT_SCALE_TRANS_FINE_BUMP = '~yPL Height Scale Transition Fine Bump'
HEIGHT_NORMALIZE = '~yPL Normalize Height'

OBJECT_INDEX_EQUAL = '~yPL Object Index Equal'
OBJECT_INDEX_GREATER_THAN = '~yPL Object Index Greater Than'
OBJECT_INDEX_LESS_THAN = '~yPL Object Index Less Than'

COLOR_ID_EQUAL = '~yPL Color ID Equal'

HEMI = '~yPL Hemi'
FXAA = '~yPL FXAA'

CAVITY = '~yPL Cavity'
DUST = '~yPL Dust'
PAINT_BASE = '~yPL Paint Base'

# NEW ORDER

HEIGHT_PROCESS = '~yPL Height Process'
#HEIGHT_PROCESS_GROUP = '~yPL Height Process Group'
HEIGHT_PROCESS_TRANSITION = '~yPL Height Process Transition'
#HEIGHT_PROCESS_TRANSITION_GROUP = '~yPL Height Process Transition Group'
HEIGHT_PROCESS_TRANSITION_CREASE = '~yPL Height Process Transition Crease'
#HEIGHT_PROCESS_TRANSITION_CREASE_GROUP = '~yPL Height Process Transition Crease Group'
HEIGHT_PROCESS_SMOOTH = '~yPL Height Process Smooth'
#HEIGHT_PROCESS_SMOOTH_GROUP = '~yPL Height Process Smooth Group'
HEIGHT_PROCESS_TRANSITION_SMOOTH = '~yPL Height Process Transition Smooth'
#HEIGHT_PROCESS_TRANSITION_SMOOTH_GROUP = '~yPL Height Process Transition Smooth Group'
HEIGHT_PROCESS_TRANSITION_SMOOTH_ZERO_CHAIN = '~yPL Height Process Transition Smooth Zero Chain'
#HEIGHT_PROCESS_TRANSITION_SMOOTH_ZERO_CHAIN_GROUP = '~yPL Height Process Transition Smooth Zero Chain Group'
HEIGHT_PROCESS_TRANSITION_SMOOTH_CREASE = '~yPL Height Process Transition Smooth Crease'
#HEIGHT_PROCESS_TRANSITION_SMOOTH_CREASE_GROUP = '~yPL Height Process Transition Smooth Crease Group'

HEIGHT_PROCESS_NORMAL_MAP = '~yPL Height Process Normal Map'
HEIGHT_PROCESS_TRANSITION_NORMAL_MAP = '~yPL Height Process Transition Normal Map'
HEIGHT_PROCESS_TRANSITION_NORMAL_MAP_CREASE = '~yPL Height Process Transition Normal Map Crease'
HEIGHT_PROCESS_SMOOTH_NORMAL_MAP = '~yPL Height Process Smooth Normal Map'
HEIGHT_PROCESS_TRANSITION_SMOOTH_NORMAL_MAP = '~yPL Height Process Transition Smooth Normal Map'
HEIGHT_PROCESS_TRANSITION_SMOOTH_NORMAL_MAP_CREASE = '~yPL Height Process Transition Smooth Normal Map Crease'

HEIGHT_COMPARE = '~yPL Height Compare'
HEIGHT_MIX_SMOOTH = '~yPL Height Mix Smooth'
HEIGHT_ADD_SMOOTH = '~yPL Height Add Smooth'
HEIGHT_COMPARE_SMOOTH = '~yPL Height Compare Smooth'
STRAIGHT_OVER_HEIGHT_MIX_SMOOTH = '~yPL Straight Over Height Mix Smooth'
STRAIGHT_OVER_HEIGHT_ADD_SMOOTH = '~yPL Straight Over Height Add Smooth'
STRAIGHT_OVER_HEIGHT_COMPARE_SMOOTH = '~yPL Straight Over Height Compare Smooth'

NORMAL_PROCESS = '~yPL Normal Process'
#NORMAL_PROCESS_GROUP = '~yPL Normal Process Group'
NORMAL_PROCESS_SMOOTH = '~yPL Normal Process Smooth'
#NORMAL_PROCESS_SMOOTH_GROUP = '~yPL Normal Process Smooth Group'

NORMAL_MAP_PROCESS = '~yPL Normal Map Process'
NORMAL_MAP_PROCESS_TRANSITION = '~yPL Normal Map Process Transition'
NORMAL_MAP_PROCESS_SMOOTH = '~yPL Normal Map Process Smooth'
NORMAL_MAP_PROCESS_SMOOTH_TRANSITION = '~yPL Normal Map Process Smooth Transition'

ADVANCED_EMISSION_VIEWER = '~yPL Advanced Emission Viewer'
#GRID_EMISSION_VIEWER = '~yPL Grid Emission Viewer'

ENGINE_FILTER = '~yPL Engine Filter'

UNPACK_ONSEW = '~yPL Unpack ONSEW'
PACK_ONSEW = '~yPL Pack ONSEW'

BL27_DISP = '~yPL Blender 2.7 Displacement'

SMOOTH_PREFIX = '~yPL Smooth '

# Legacy nodes for Blender 2.79
FLIP_BACKFACE_NORMAL_LEGACY = '~yPL Flip Backface Normal Legacy'
FLIP_BACKFACE_BUMP_LEGACY = '~yPL Flip Backface Bump Legacy'
FLIP_BACKFACE_TANGENT_LEGACY = '~yPL Flip Backface Tangent Legacy'
NORMAL_MAP_PREP_LEGACY = '~yPL Normal Map Preparation Legacy'
TANGENT_PROCESS_LEGACY = '~yPL Tangent Process Legacy'
ENGINE_FILTER_LEGACY = '~yPL Engine Filter Legacy'

# END OF NEW ORDER

#HEIGHT_PROCESS_BUMP_MIX = '~yPL Height Process Bump Mix'
#HEIGHT_PROCESS_BUMP_ADD = '~yPL Height Process Bump Add'
#
#HEIGHT_PROCESS_TRANSITION_BUMP = '~yPL Height Process Transition Bump'
#HEIGHT_PROCESS_TRANSITION_BUMP_MIX = '~yPL Height Process Transition Bump Mix'
#HEIGHT_PROCESS_TRANSITION_BUMP_ADD = '~yPL Height Process Transition Bump Add'
#
#HEIGHT_PROCESS_TRANSITION_BUMP_CREASE_MIX = '~yPL Height Process Transition Bump Crease Mix'
#HEIGHT_PROCESS_TRANSITION_BUMP_CREASE_ADD = '~yPL Height Process Transition Bump Crease Add'
#
#HEIGHT_PROCESS_NORMAL_MAP_MIX = '~yPL Height Process Normal Map Mix'
#HEIGHT_PROCESS_NORMAL_MAP_ADD = '~yPL Height Process Normal Map Add'
#
#HEIGHT_PROCESS_TRANSITION_NORMAL_MAP_MIX = '~yPL Height Process Transition Normal Map Mix'
#HEIGHT_PROCESS_TRANSITION_NORMAL_MAP_ADD = '~yPL Height Process Transition Normal Map Add'
#
#HEIGHT_PROCESS_TRANSITION_NORMAL_MAP_CREASE_MIX = '~yPL Height Process Transition Normal Map Crease Mix'
#HEIGHT_PROCESS_TRANSITION_NORMAL_MAP_CREASE_ADD = '~yPL Height Process Transition Normal Map Crease Add'
#
#NORMAL_PROCESS_BUMP = '~yPL Normal Process Bump'
#
#NORMAL_PROCESS_TRANSITION_SMOOTH_BUMP_MIX = '~yPL Normal Process Transition Smooth Bump Mix'
#NORMAL_PROCESS_TRANSITION_SMOOTH_BUMP_ADD = '~yPL Normal Process Transition Smooth Bump Add'
#
#NORMAL_PROCESS_TRANSITION_SMOOTH_BUMP_ZERO_CHAIN_MIX = '~yPL Normal Process Transition Smooth Bump Zero Chain Mix'
#NORMAL_PROCESS_TRANSITION_SMOOTH_BUMP_ZERO_CHAIN_ADD = '~yPL Normal Process Transition Smooth Bump Zero Chain Add'
#
#NORMAL_PROCESS_TRANSITION_SMOOTH_BUMP_CREASE_MIX = '~yPL Normal Process Transition Smooth Bump Crease Mix'
#NORMAL_PROCESS_TRANSITION_SMOOTH_BUMP_CREASE_ADD = '~yPL Normal Process Transition Smooth Bump Crease Add'
#
#NORMAL_PROCESS_BUMP_MIX = '~yPL Normal Process Bump Mix'
#NORMAL_PROCESS_BUMP_ADD = '~yPL Normal Process Bump Add'
#
#NORMAL_MAP_PROCESS_BUMP = '~yPL Normal Map Process Bump'
#NORMAL_MAP_PROCESS_TRANSITION_BUMP = '~yPL Normal Map Process Transition Bump'
#
#NORMAL_MAP_PROCESS_SMOOTH_BUMP_MIX = '~yPL Normal Map Process Smooth Bump Mix'
#NORMAL_MAP_PROCESS_SMOOTH_BUMP_ADD = '~yPL Normal Map Process Smooth Bump Add'
#
#NORMAL_MAP_PROCESS_TRANSITION_SMOOTH_BUMP_MIX = '~yPL Normal Map Process Transition Smooth Bump Mix'
#NORMAL_MAP_PROCESS_TRANSITION_SMOOTH_BUMP_ADD = '~yPL Normal Map Process Transition Smooth Bump Add'
#
#NORMAL_MAP_PROCESS_TRANSITION_SMOOTH_BUMP_MIX = '~yPL Normal Map Process Transition Smooth Bump Mix'
#NORMAL_MAP_PROCESS_TRANSITION_SMOOTH_BUMP_ADD = '~yPL Normal Map Process Transition Smooth Bump Add'
#
#NORMAL_MAP_PROCESS_TRANSITION_SMOOTH_BUMP_MIX = '~yPL Normal Map Process Transition Smooth Bump Mix'
#NORMAL_MAP_PROCESS_TRANSITION_SMOOTH_BUMP_ADD = '~yPL Normal Map Process Transition Smooth Bump Add'
#
#NORMAL_MAP_PROCESS_TRANSITION_SMOOTH_BUMP_CREASE_MIX = '~yPL Normal Map Process Transition Smooth Bump Crease Mix'
#NORMAL_MAP_PROCESS_TRANSITION_SMOOTH_BUMP_CREASE_ADD = '~yPL Normal Map Process Transition Smooth Bump Crease Add'

#DISP_MIX = '~yPL Displacement Mix'
#DISP_OVERLAY = '~yPL Displacement Overlay'
#HEIGHT_PACK = '~yPL Height Pack'

EMULATED_CURVE = '~yPL Emulated Curve'
EMULATED_CURVE_SMOOTH = '~yPL Emulated Curve Smooth'
FALLOFF_CURVE = '~yPL Falloff Curve'
FALLOFF_CURVE_SMOOTH = '~yPL Falloff Curve Smooth'

FINE_BUMP_PROCESS = '~yPL Fine Bump Process'
BUMP_PROCESS = '~yPL Bump Process'

# Bake stuff
BAKE_NORMAL = '~yPL Bake Normal'
BAKE_NORMAL_ACTIVE_UV = '~yPL Bake Normal with Active UV'

# SRGB Stuff
SRGB_2_LINEAR = '~yPL SRGB to Linear'
LINEAR_2_SRGB = '~yPL Linear to SRGB'

FLIP_Y = '~yPL Flip Y'

# Modifier tree names
MOD_RGB2INT = '~yPL Mod RGB To Intensity'
MOD_INT2RGB = '~yPL Mod Intensity To RGB'
MOD_OVERRIDE_COLOR = '~yPL Mod Override Color'
MOD_INVERT = '~yPL Mod Invert'
MOD_INVERT_VALUE = '~yPL Mod Invert Value'
MOD_MULTIPLIER = '~yPL Mod Multiplier'
MOD_MULTIPLIER_VALUE = '~yPL Mod Multiplier Value'
MOD_INTENSITY_HARDNESS = '~yPL Mod Intensity Hardness'
MOD_MATH = '~yPL Mod Math'
MOD_MATH_VALUE = '~yPL Mod Math Value'


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
    import bpy.utils.previews
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

    custom_icons.load('texture', filepath + 'texture_icon.png', 'IMAGE')
    custom_icons.load('collapsed_texture', filepath + 'collapsed_texture_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_texture', filepath + 'uncollapsed_texture_icon.png', 'IMAGE')

    custom_icons.load('image', filepath + 'image_icon.png', 'IMAGE')
    custom_icons.load('collapsed_image', filepath + 'collapsed_image_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_image', filepath + 'uncollapsed_image_icon.png', 'IMAGE')

    custom_icons.load('modifier', filepath + 'modifier_icon.png', 'IMAGE')
    custom_icons.load('collapsed_modifier', filepath + 'collapsed_modifier_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_modifier', filepath + 'uncollapsed_modifier_icon.png', 'IMAGE')

    custom_icons.load('input', filepath + 'input_icon.png', 'IMAGE')
    custom_icons.load('collapsed_input', filepath + 'collapsed_input_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_input', filepath + 'uncollapsed_input_icon.png', 'IMAGE')

    custom_icons.load('uv', filepath + 'uv_icon.png', 'IMAGE')
    custom_icons.load('collapsed_uv', filepath + 'collapsed_uv_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_uv', filepath + 'uncollapsed_uv_icon.png', 'IMAGE')

    custom_icons.load('mask', filepath + 'mask_icon.png', 'IMAGE')
    custom_icons.load('disabled_mask', filepath + 'disabled_mask_icon.png', 'IMAGE')
    custom_icons.load('collapsed_mask', filepath + 'collapsed_mask_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_mask', filepath + 'uncollapsed_mask_icon.png', 'IMAGE')

    custom_icons.load('collapsed_vcol', filepath + 'collapsed_vertex_color_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_vcol', filepath + 'uncollapsed_vertex_color_icon.png', 'IMAGE')

    custom_icons.load('close', filepath + 'close_icon.png', 'IMAGE')
    custom_icons.load('clean', filepath + 'clean_icon.png', 'IMAGE')

    custom_icons.load('vertex_color', filepath + 'vertex_color_icon.png', 'IMAGE')

    custom_icons.load('bake', filepath + 'bake_icon.png', 'IMAGE')
    custom_icons.load('group', filepath + 'group_icon.png', 'IMAGE')
    custom_icons.load('background', filepath + 'background_icon.png', 'IMAGE')
    custom_icons.load('blend', filepath + 'blend_icon.png', 'IMAGE')
    custom_icons.load('open_image', filepath + 'open_image_icon.png', 'IMAGE')
    custom_icons.load('nodetree', filepath + 'nodetree_icon.png', 'IMAGE')
    custom_icons.load('rename', filepath + 'rename_icon.png', 'IMAGE')

    custom_icons.load('object_index', filepath + 'object_index_icon.png', 'IMAGE')
    custom_icons.load('collapsed_object_index', filepath + 'collapsed_object_index_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_object_index', filepath + 'uncollapsed_object_index_icon.png', 'IMAGE')

    custom_icons.load('hemi', filepath + 'hemi_icon.png', 'IMAGE')
    custom_icons.load('collapsed_hemi', filepath + 'collapsed_hemi_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_hemi', filepath + 'uncollapsed_hemi_icon.png', 'IMAGE')

    custom_icons.load('color', filepath + 'color_icon.png', 'IMAGE')
    custom_icons.load('collapsed_color', filepath + 'collapsed_color_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_color', filepath + 'uncollapsed_color_icon.png', 'IMAGE')

    custom_icons.load('collapsed_channels', filepath + 'collapsed_channels_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_channels', filepath + 'uncollapsed_channels_icon.png', 'IMAGE')

    custom_icons.load('collapsed_rgb_channel', filepath + 'collapsed_rgb_channel_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_rgb_channel', filepath + 'uncollapsed_rgb_channel_icon.png', 'IMAGE')
    custom_icons.load('collapsed_value_channel', filepath + 'collapsed_value_channel_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_value_channel', filepath + 'uncollapsed_value_channel_icon.png', 'IMAGE')
    custom_icons.load('collapsed_vector_channel', filepath + 'collapsed_vector_channel_icon.png', 'IMAGE')
    custom_icons.load('uncollapsed_vector_channel', filepath + 'uncollapsed_vector_channel_icon.png', 'IMAGE')


def get_icon(custom_icon_name):
    return custom_icons[custom_icon_name].icon_id

def check_uv_difference_to_main_uv(entity):
    yp = entity.id_data.yp
    height_ch = get_root_height_channel(yp)
    if height_ch:

        # Set height channel main uv if its still empty
        #if height_ch.main_uv == '' and len(yp.uvs) > 0:
        #    height_ch.main_uv = yp.uvs[0].name

        # Check if entity uv is different to main uv
        if height_ch.main_uv != '' and hasattr(entity, 'uv_name') and entity.uv_name != height_ch.main_uv:
            return True

    return False

#def get_neighbor_uv_tree(texcoord_type, different_uv=False, entity=None):
def get_neighbor_uv_tree(texcoord_type, entity):

    if texcoord_type == 'UV':
        different_uv = check_uv_difference_to_main_uv(entity)
        if different_uv: return get_node_tree_lib(NEIGHBOR_UV_OTHER_UV)
        return get_node_tree_lib(NEIGHBOR_UV_TANGENT)
    if texcoord_type in {'Generated', 'Normal', 'Object'}:
        return get_node_tree_lib(NEIGHBOR_UV_OBJECT)
    if texcoord_type in {'Camera', 'Window', 'Reflection'}:
        return get_node_tree_lib(NEIGHBOR_UV_CAMERA)

#def get_neighbor_uv_tree_name(texcoord_type, different_uv=False, entity=None):
def get_neighbor_uv_tree_name(texcoord_type, entity):
    if texcoord_type == 'UV':
        different_uv = check_uv_difference_to_main_uv(entity)
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

def get_smooth_mix_node(blend_type):
    tree = bpy.data.node_groups.get(SMOOTH_PREFIX + blend_type)
    if not tree:
        tree = bpy.data.node_groups.new(SMOOTH_PREFIX + blend_type, 'ShaderNodeTree')

        # IO
        inp = tree.inputs.new('NodeSocketFloatFactor', 'Fac')
        inp.min_value = 0.0
        inp.max_value = 1.0

        tree.inputs.new('NodeSocketColor', 'Color1')
        for d in neighbor_directions:
            tree.inputs.new('NodeSocketColor', 'Color1 ' + d)

        tree.inputs.new('NodeSocketColor', 'Color2')
        for d in neighbor_directions:
            tree.inputs.new('NodeSocketColor', 'Color2 ' + d)

        tree.outputs.new('NodeSocketColor', 'Color')
        for d in neighbor_directions:
            tree.outputs.new('NodeSocketColor', 'Color ' + d)

        # Nodes
        create_essential_nodes(tree)

        start = tree.nodes.get(TREE_START)
        end = tree.nodes.get(TREE_END)

        loc = Vector((0, 0))

        start.location = loc

        mixes = {}
        mix = tree.nodes.new('ShaderNodeMixRGB')
        mix.name = '_mix'
        mix.blend_type = blend_type

        loc.x += 200
        mix.location = loc

        tree.links.new(start.outputs['Fac'], mix.inputs['Fac'])
        tree.links.new(start.outputs['Color1'], mix.inputs['Color1'])
        tree.links.new(start.outputs['Color2'], mix.inputs['Color2'])
        tree.links.new(mix.outputs[0], end.inputs['Color'])

        for d in neighbor_directions:
            mix = tree.nodes.new('ShaderNodeMixRGB')
            mix.name = '_mix_' + d
            mix.blend_type = blend_type

            loc.y -= 200
            mix.location = loc

            tree.links.new(start.outputs['Fac'], mix.inputs['Fac'])
            tree.links.new(start.outputs['Color1 ' + d], mix.inputs['Color1'])
            tree.links.new(start.outputs['Color2 ' + d], mix.inputs['Color2'])
            tree.links.new(mix.outputs[0], end.inputs['Color ' + d])

        loc.x += 200
        end.location.x = loc.x

    return tree

def clean_unused_libraries():
    for ng in bpy.data.node_groups:
        if ng.name.startswith('~yPL ') and ng.users == 0:
            bpy.data.node_groups.remove(ng)

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

def flip_tangent_sign():
    meshes = []

    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.data not in meshes:
            meshes.append(obj.data)
            for vc in get_vertex_colors(obj):
                if vc.name.startswith(TANGENT_SIGN_PREFIX):

                    i = 0
                    for poly in obj.data.polygons:
                        for idx in poly.loop_indices:
                            vert = obj.data.loops[idx]
                            col = vc.data[i].color
                            if is_greater_than_280():
                                vc.data[i].color = (1.0-col[0], 1.0-col[1], 1.0-col[2], 1.0)
                            else: vc.data[i].color = (1.0-col[0], 1.0-col[1], 1.0-col[2])
                            i += 1

def get_lib_revision(tree):
    rev = tree.nodes.get('revision')

    # Check lib tree revision
    if rev:
        m = re.match(r'.*(\d)', rev.label)
        try: revision = int(m.group(1))
        except: revision = 0
    else: revision = 0

    return revision

@persistent
def update_routine(name):
    T = time.time()

    cur_version = get_current_version_str()

    for ng in bpy.data.node_groups:
        if not hasattr(ng, 'yp'): continue
        if not ng.yp.is_ypaint_node: continue

        #print(ng.name, 'ver:', ng.yp.version)
        update_happened = False

        # Version 0.9.1 and above will fix wrong bake type stored on images bake type
        if LooseVersion(ng.yp.version) < LooseVersion('0.9.1'):
            #print(cur_version)
            for layer in ng.yp.layers:
                if layer.type == 'IMAGE':
                    source = get_layer_source(layer)

                    if source.image and source.image.y_bake_info.is_baked:
                        #print(source.image)
                        for type_name, label in bake_type_suffixes.items():
                            if label in source.image.name and source.image.y_bake_info.bake_type != type_name:
                                source.image.y_bake_info.bake_type = type_name
                                print('INFO: Bake type of', source.image.name, 'is fixed by setting it to', label + '!')
                                update_happened = True

        # Version 0.9.2 and above will move mapping outside source group
        if LooseVersion(ng.yp.version) < LooseVersion('0.9.2'):

            for layer in ng.yp.layers:
                tree = get_tree(layer)

                mapping_replaced = False

                # Move layer mapping
                if layer.source_group != '':
                    group = tree.nodes.get(layer.source_group)
                    if group:
                        mapping_ref = group.node_tree.nodes.get(layer.mapping)
                        if mapping_ref:
                            mapping = new_node(tree, layer, 'mapping', 'ShaderNodeMapping')
                            copy_node_props(mapping_ref, mapping)
                            group.node_tree.nodes.remove(mapping_ref)
                            set_uv_neighbor_resolution(layer, mapping=mapping)
                            mapping_replaced = True
                            print('INFO: Mapping of', layer.name, 'is moved out!')

                # Move mask mapping
                for mask in layer.masks:
                    if mask.group_node != '':
                        group = tree.nodes.get(mask.group_node)
                        if group:
                            mapping_ref = group.node_tree.nodes.get(mask.mapping)
                            if mapping_ref:
                                mapping = new_node(tree, mask, 'mapping', 'ShaderNodeMapping')
                                copy_node_props(mapping_ref, mapping)
                                group.node_tree.nodes.remove(mapping_ref)
                                set_uv_neighbor_resolution(mask, mapping=mapping)
                                mapping_replaced = True
                                print('INFO: Mapping of', mask.name, 'is moved out!')

                if mapping_replaced:
                    reconnect_layer_nodes(layer)
                    rearrange_layer_nodes(layer)
                    update_happened = True

        # Version 0.9.3 and above will replace override color modifier with newer override system
        if LooseVersion(ng.yp.version) < LooseVersion('0.9.3'):

            for layer in ng.yp.layers:
                for i, ch in enumerate(layer.channels):
                    root_ch = ng.yp.channels[i]
                    mod_ids = []
                    for j, mod in enumerate(ch.modifiers):
                        if mod.type == 'OVERRIDE_COLOR':
                            mod_ids.append(j)

                    for j in reversed(mod_ids):
                        mod = ch.modifiers[j]
                        tree = get_mod_tree(ch)

                        ch.override = True
                        if root_ch.type == 'VALUE':
                            ch.override_value = mod.oc_val
                        else:
                            ch.override_color = (mod.oc_col[0], mod.oc_col[1], mod.oc_col[2])

                        if ch.override_type != 'DEFAULT':
                            ch.override_type = 'DEFAULT'

                        # Delete the nodes and modifier
                        remove_node(tree, mod, 'oc')
                        ch.modifiers.remove(j)

                    if mod_ids:
                        reconnect_layer_nodes(layer)
                        rearrange_layer_nodes(layer)
                        update_happened = True

        # Version 0.9.4 and above will replace multipier modifier with math modifier
        if LooseVersion(ng.yp.version) < LooseVersion('0.9.4'):

            mods = []
            parents = []
            types = []

            for channel in ng.yp.channels:
                channel_tree = get_mod_tree(channel)
                for mod in channel.modifiers:
                    if mod.type == 'MULTIPLIER' :
                        mods.append(mod)
                        parents.append(channel)
                        types.append(channel.type)

            for layer in ng.yp.layers:
                layer_tree = get_mod_tree(layer)
                for mod in layer.modifiers:
                    if mod.type == 'MULTIPLIER' :
                        mods.append(mod)
                        parents.append(layer)
                        types.append('RGB')

                for i, ch in enumerate(layer.channels):
                    root_ch = ng.yp.channels[i]
                    ch_tree = get_mod_tree(ch)
                    for j, mod in enumerate(ch.modifiers):
                        if mod.type == 'MULTIPLIER' :
                            mods.append(mod)
                            parents.append(ch)
                            types.append(root_ch.type)

            for i, mod in enumerate(mods):
                parent = parents[i]
                ch_type = types[i]

                tree = get_mod_tree(parent)

                mod.name = 'Math'
                mod.type = 'MATH'
                remove_node(tree, mod, 'multiplier')
                math = new_node(tree, mod, 'math', 'ShaderNodeGroup', 'Math')

                if ch_type == 'VALUE':
                    math.node_tree = get_node_tree_lib(MOD_MATH_VALUE)
                else:
                    math.node_tree = get_node_tree_lib(MOD_MATH)
                
                duplicate_lib_node_tree(math)

                mod.affect_alpha = True
                math.node_tree.nodes.get('Mix.A').mute = False

                mod.math_a_val = mod.multiplier_a_val
                mod.math_r_val = mod.multiplier_r_val
                math.node_tree.nodes.get('Math.R').use_clamp = mod.use_clamp
                math.node_tree.nodes.get('Math.A').use_clamp = mod.use_clamp
                if ch_type != 'VALUE':
                    mod.math_g_val = mod.multiplier_g_val
                    mod.math_b_val = mod.multiplier_b_val
                    math.node_tree.nodes.get('Math.G').use_clamp = mod.use_clamp
                    math.node_tree.nodes.get('Math.B').use_clamp = mod.use_clamp

            if mods:
                for layer in ng.yp.layers:
                    reconnect_layer_nodes(layer)
                    rearrange_layer_nodes(layer)
                reconnect_yp_nodes(ng)
                rearrange_yp_nodes(ng)
                update_happened = True

        # Version 0.9.5 and above have ability to use vertex color alpha on layer
        if LooseVersion(ng.yp.version) < LooseVersion('0.9.5'):

            for layer in ng.yp.layers:
                # Update vcol layer to use alpha by reconnection
                if layer.type == 'VCOL':

                    # Smooth bump channel need another fake neighbor for alpha
                    smooth_bump_ch = get_smooth_bump_channel(layer)
                    if smooth_bump_ch and smooth_bump_ch.enable:
                        layer_tree = get_tree(layer)
                        uv_neighbor_1 = replace_new_node(layer_tree, layer, 'uv_neighbor_1', 'ShaderNodeGroup', 'Neighbor UV 1', 
                                NEIGHBOR_FAKE, hard_replace=True)

                    reconnect_layer_nodes(layer)
                    rearrange_layer_nodes(layer)
                    update_happened = True

        # Version 0.9.6 and above will use native vertex color node for Blender 2.81+
        #if (LooseVersion(ng.yp.version) < LooseVersion('0.9.6') or is_created_using_279() or is_created_using_280()) and is_greater_than_281():

        #    for layer in ng.yp.layers:
        #        layer_tree = get_tree(layer)

        #        # Update vcol layer to use alpha by reconnection
        #        if layer.type == 'VCOL':

        #            source = get_layer_source(layer)
        #            name = source.attribute_name
        #            label = source.label
        #            source = replace_new_node(layer_tree, layer, 'source', 'ShaderNodeVertexColor', label)
        #            source.layer_name = name

        #        for ch in layer.channels:

        #            if ch.override_type == 'VCOL':
        #                source = get_channel_source(ch, layer, layer_tree)
        #                if source:
        #                    name = source.attribute_name
        #                    label = source.label
        #                    source = replace_new_node(layer_tree, ch, 'source', 'ShaderNodeVertexColor', label)
        #                    source.layer_name = name
        #                    update_happened = True

        #            cache_vcol = layer_tree.nodes.get(ch.cache_vcol)
        #            if cache_vcol:
        #                name = cache_vcol.attribute_name
        #                label = cache_vcol.label
        #                cache_vcol = replace_new_node(layer_tree, ch, 'cache_vcol', 'ShaderNodeVertexColor', label)
        #                cache_vcol.layer_name = name
        #                update_happened = True

        #        for mask in layer.masks:
        #            if mask.type == 'VCOL':
        #                source = get_mask_source(mask)
        #                name = source.attribute_name
        #                label = source.label
        #                source = replace_new_node(layer_tree, mask, 'source', 'ShaderNodeVertexColor', label)
        #                source.layer_name = name
        #                update_happened = True

        #        if update_happened:
        #            reconnect_layer_nodes(layer)
        #            rearrange_layer_nodes(layer)

        # Version 0.9.8 and above will use sRGB images by default
        if LooseVersion(ng.yp.version) < LooseVersion('0.9.8'):

            for layer in ng.yp.layers:
                if not layer.enable: continue

                image_found = False
                if layer.type == 'IMAGE':

                    source = get_layer_source(layer)
                    if source and source.image and not source.image.is_float: 
                        if source.image.colorspace_settings.name != 'sRGB':
                            source.image.colorspace_settings.name = 'sRGB'
                            print('INFO:', source.image.name, 'image is now using sRGB!')
                        check_layer_image_linear_node(layer)
                    image_found = True

                for ch in layer.channels:
                    if not ch.enable or not ch.override: continue

                    if ch.override_type == 'IMAGE':

                        source = get_channel_source(ch)
                        if source and source.image and not source.image.is_float:
                            if source.image.colorspace_settings.name != 'sRGB':
                                source.image.colorspace_settings.name = 'sRGB'
                                print('INFO:', source.image.name, 'image is now using sRGB!')
                            check_layer_channel_linear_node(ch)
                        image_found = True

                for mask in layer.masks:
                    if not mask.enable: continue

                    if mask.type == 'IMAGE':
                        source = get_mask_source(mask)
                        if source and source.image and not source.image.is_float:
                            if source.image.colorspace_settings.name != 'sRGB':
                                source.image.colorspace_settings.name = 'sRGB'
                                print('INFO:', source.image.name, 'image is now using sRGB!')
                            check_mask_image_linear_node(mask)
                        image_found = True

                if image_found:
                    rearrange_layer_nodes(layer)
                    reconnect_layer_nodes(layer)

        # Version 0.9.9 have separate normal and bump override
        if LooseVersion(ng.yp.version) < LooseVersion('0.9.9'):
            for layer in ng.yp.layers:
                for i, ch in enumerate(layer.channels):
                    root_ch = ng.yp.channels[i]
                    if root_ch.type == 'NORMAL' and ch.normal_map_type == 'NORMAL_MAP' and ch.override:

                        # Disable override first
                        ch.override = False

                        # Rename pointers
                        ch.cache_1_image = ch.cache_image

                        # Remove previous pointers
                        ch.cache_image = ''

                        # Copy props
                        ch.override_1_type = ch.override_type
                        ch.override_type = 'DEFAULT'

                        # Enable override
                        ch.override_1 = True

                        # Copy active edit
                        ch.active_edit_1 = ch.active_edit

                        print('INFO:', layer.name, root_ch.name, 'now has separate override properties!')

        # Update version
        if update_happened:
            ng.yp.version = cur_version
            print('INFO:', ng.name, 'is updated to version', cur_version)

    # Special update for opening Blender below 2.92 file
    if is_created_before_292() and is_greater_than_292():
        show_message = False
        for ng in bpy.data.node_groups:
            if not hasattr(ng, 'yp'): continue
            if not ng.yp.is_ypaint_node: continue
            show_message = True
            
            for layer in ng.yp.layers:
                # Update vcol layer to use alpha by reconnection
                if layer.type == 'VCOL':
                    reconnect_layer_nodes(layer)
                    rearrange_layer_nodes(layer)

        if show_message:
            print("INFO: Now " + get_addon_title() + " capable to use vertex paint alpha since Blender 2.92, Enjoy!")

    # Special update for opening Blender 2.79 file
    filepath = get_addon_filepath() + "lib.blend"
    if is_created_using_279() and is_greater_than_280() and bpy.data.filepath != filepath:

        legacy_groups = []
        newer_groups = []
        newer_group_names = []

        for ng in bpy.data.node_groups:

            m = re.match(r'^(~yPL .+)(?: Legacy)(?:_Copy)?(?:\.\d{3}?)?$', ng.name)
            if m and ng.name not in legacy_groups:
                legacy_groups.append(ng)
                newer_group_names.append(m.group(1))
                #print(ng.name, m.group(1))

        # Load node groups
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            for ng in data_from.node_groups:
                if ng in newer_group_names:
                    tree = bpy.data.node_groups.get(ng)
                    #if tree:
                    #    tree.name += '__OLD'
                    #tree_names.append(ng)
                    data_to.node_groups.append(ng)
                    #print(ng)

        # Fill newer groups
        for name in newer_group_names:
            newer_groups.append(bpy.data.node_groups.get(name))

        # List of already copied groups
        copied_groups = []

        # Update from legacy to newer groups
        for i, legacy_ng in enumerate(legacy_groups):
            newer_ng = newer_groups[i]
            #print(legacy_ng.name, newer_ng.name)

            if '_Copy' not in legacy_ng.name:

                # Search for legacy tree usages
                for mat in bpy.data.materials:
                    if not mat.node_tree: continue
                    for node in mat.node_tree.nodes:
                        if node.type == 'GROUP' and node.node_tree == legacy_ng:
                            node.node_tree = newer_ng

                for group in bpy.data.node_groups:
                    for node in group.nodes:
                        if node.type == 'GROUP' and node.node_tree == legacy_ng:
                            node.node_tree = newer_ng

                print('INFO:', legacy_ng.name, 'is replaced to', newer_ng.name + '!')

                # Remove old tree
                bpy.data.node_groups.remove(legacy_ng)

                # Create info frames
                create_info_nodes(newer_ng)

            else:

                used_nodes = []
                parent_trees = []

                # Search for old tree usages
                for mat in bpy.data.materials:
                    if not mat.node_tree: continue
                    for node in mat.node_tree.nodes:
                        if node.type == 'GROUP' and node.node_tree == legacy_ng:
                            used_nodes.append(node)
                            parent_trees.append(mat.node_tree)

                for group in bpy.data.node_groups:
                    for node in group.nodes:
                        if node.type == 'GROUP' and node.node_tree == legacy_ng:
                            used_nodes.append(node)
                            parent_trees.append(group)

                #print(legacy_ng.name, used_nodes)

                if used_nodes:

                    # Remember original tree
                    ori_tree = used_nodes[0].node_tree

                    # Duplicate lib tree
                    if '_Copy' not in newer_ng.name:
                        newer_ng.name += '_Copy'
                    used_nodes[0].node_tree = newer_ng.copy()
                    new_tree = used_nodes[0].node_tree
                    #newer_ng.name = name

                    print('INFO:', ori_tree.name, 'is replaced to', new_tree.name + '!')

                    if newer_ng not in copied_groups:
                        copied_groups.append(newer_ng)

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

        # Remove already copied groups
        for ng in copied_groups:
            bpy.data.node_groups.remove(ng)

    print('INFO: ' + get_addon_title() + ' update routine are done at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')


def get_inside_group_update_names(tree, update_names):

    for n in tree.nodes:
        if n.type == 'GROUP' and n.node_tree and n.node_tree.name not in update_names:
            update_names.append(n.node_tree.name)
            update_names = get_inside_group_update_names(n.node_tree, update_names)

    return update_names

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
        cur_trees = [n for n in bpy.data.node_groups if n.name.startswith(name) and n.name != name]

        #print(cur_trees)

        for cur_tree in cur_trees:
            # Check lib tree revision
            cur_ver = get_lib_revision(cur_tree)
            lib_ver = get_lib_revision(lib_tree)
            #print(name, cur_tree.name, lib_tree.name, cur_ver, lib_ver)

            if lib_ver > cur_ver:

                if name not in update_names:
                    update_names.append(name)

                # Check for group inside group
                update_names = get_inside_group_update_names(lib_tree, update_names)

                # Flip tangent if tangent process is updated to ver 1
                if name == TANGENT_PROCESS and cur_ver == 0 and lib_ver == 1:
                    flip_tangent_sign()

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
                    parent_trees = []

                    # Search for old tree usages
                    for mat in bpy.data.materials:
                        if not mat.node_tree: continue
                        for node in mat.node_tree.nodes:
                            if node.type == 'GROUP' and node.node_tree == cur_tree:
                                used_nodes.append(node)
                                parent_trees.append(mat.node_tree)

                    for group in bpy.data.node_groups:
                        for node in group.nodes:
                            if node.type == 'GROUP' and node.node_tree == cur_tree:
                                used_nodes.append(node)
                                parent_trees.append(group)

                    #print(used_nodes)

                    if used_nodes:

                        # Remember original tree
                        ori_tree = used_nodes[0].node_tree

                        # Duplicate lib tree
                        lib_tree.name += '_Copy'
                        used_nodes[0].node_tree = lib_tree.copy()
                        new_tree = used_nodes[0].node_tree
                        lib_tree.name = name

                        cur_ver = get_lib_revision(ori_tree)
                        lib_ver = get_lib_revision(lib_tree)

                        for i, node in enumerate(used_nodes):
                            node.node_tree = new_tree

                            # Hemi revision 1 has normal input
                            if name == HEMI and cur_ver == 0 and lib_ver == 1:
                                geom = parent_trees[i].nodes.get(GEOMETRY)
                                if geom: parent_trees[i].links.new(geom.outputs['Normal'], node.inputs['Normal'])

                        # Copy some nodes inside
                        for n in new_tree.nodes:
                            if n.name.startswith('_'):
                                # Try to get the node on original tree
                                ori_n = ori_tree.nodes.get(n.name)
                                if ori_n: copy_node_props(ori_n, n)

                        # Update hemi node
                        if name == HEMI:
                            # Copy hemi stuffs
                            cur_norm = ori_tree.nodes.get('Normal')
                            new_norm = new_tree.nodes.get('Normal')

                            new_norm.outputs[0].default_value = cur_norm.outputs[0].default_value

                            cur_vt = ori_tree.nodes.get('Vector Transform')
                            new_vt = new_tree.nodes.get('Vector Transform')

                            new_vt.convert_from = cur_vt.convert_from
                            new_vt.convert_to = cur_vt.convert_to

                        # Delete original tree
                        bpy.data.node_groups.remove(ori_tree)

                        # Create info frames
                        create_info_nodes(new_tree)

            # Remove lib tree
            bpy.data.node_groups.remove(lib_tree)

    print('INFO: ' + get_addon_title() + ' Node group libraries are checked at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def register():
    load_custom_icons()
    #bpy.app.handlers.load_post.append(load_libraries)
    bpy.app.handlers.load_post.append(update_node_tree_libs)
    bpy.app.handlers.load_post.append(update_routine)

def unregister():
    global custom_icons
    if hasattr(bpy.utils, 'previews'):
        bpy.utils.previews.remove(custom_icons)
    #bpy.app.handlers.load_post.remove(load_libraries)
    bpy.app.handlers.load_post.remove(update_node_tree_libs)
    bpy.app.handlers.load_post.remove(update_routine)
