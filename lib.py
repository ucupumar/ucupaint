import bpy, os
from .common import *
from mathutils import *

# Node tree names
OVERLAY_NORMAL = '~yPL Overlay Normal'
OVERLAY_NORMAL_STRAIGHT_OVER = '~yPL Overlay Normal Straight Over'
CHECK_INPUT_NORMAL = '~yPL Check Input Normal'
CHECK_INPUT_NORMAL_GEOMETRY = '~yPL Check Input Normal Geometry'
CHECK_INPUT_NORMAL_MIXED = '~yPL Check Input Normal Mixed'
CHECK_INPUT_NORMAL_MIXED_BL27 = '~yPL Check Input Normal Mixed BL27'

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
INTENSITY_MULTIPLIER_SHARPEN ='~yPL Intensity Multiplier Sharpen'
INTENSITY_MULTIPLIER_SHARPEN_INVERT ='~yPL Intensity Multiplier Sharpen Invert'
INTENSITY_MULTIPLIER_SHARPEN_NO_FACTOR ='~yPL Intensity Multiplier Sharpen No Factor'
INTENSITY_MULTIPLIER_INVERT ='~yPL Intensity Multiplier Invert'
GET_BITANGENT ='~yPL Get Bitangent'
BITANGENT_FROM_NATIVE_TANGENT = '~yPL Bitangent from Native Tangent'

TANGENT_PROCESS = '~yPL Tangent Process' # For Blender 2.80 to 2.93
TANGENT_PROCESS_300 = '~yPL Tangent Process 3.0' # For Blender 3.0 and above
TANGENT_PROCESS_LEGACY = '~yPL Tangent Process Legacy' # For Blender 2.79

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
COLOR_ID_EQUAL_282 = '~yPL Color ID Equal 2.82'

HEMI = '~yPL Hemi'
FXAA = '~yPL FXAA'

CAVITY = '~yPL Cavity'
DUST = '~yPL Dust'
PAINT_BASE = '~yPL Paint Base'

BLUR_VECTOR = '~yPL Blur Vector'

HEIGHT_PROCESS = '~yPL Height Process'
HEIGHT_PROCESS_TRANSITION = '~yPL Height Process Transition'
HEIGHT_PROCESS_TRANSITION_CREASE = '~yPL Height Process Transition Crease'
HEIGHT_PROCESS_SMOOTH = '~yPL Height Process Smooth'
HEIGHT_PROCESS_TRANSITION_SMOOTH = '~yPL Height Process Transition Smooth'
HEIGHT_PROCESS_TRANSITION_SMOOTH_ZERO_CHAIN = '~yPL Height Process Transition Smooth Zero Chain'
HEIGHT_PROCESS_TRANSITION_SMOOTH_CREASE = '~yPL Height Process Transition Smooth Crease'

HEIGHT_PROCESS_NORMAL_MAP = '~yPL Height Process Normal Map'
HEIGHT_PROCESS_TRANSITION_NORMAL_MAP = '~yPL Height Process Transition Normal Map'
HEIGHT_PROCESS_TRANSITION_NORMAL_MAP_CREASE = '~yPL Height Process Transition Normal Map Crease'
HEIGHT_PROCESS_SMOOTH_NORMAL_MAP = '~yPL Height Process Smooth Normal Map'
HEIGHT_PROCESS_TRANSITION_SMOOTH_NORMAL_MAP = '~yPL Height Process Transition Smooth Normal Map'
HEIGHT_PROCESS_TRANSITION_SMOOTH_NORMAL_MAP_CREASE = '~yPL Height Process Transition Smooth Normal Map Crease'

HEIGHT_MIX_SMOOTH = '~yPL Height Mix Smooth'
HEIGHT_ADD_SMOOTH = '~yPL Height Add Smooth'
STRAIGHT_OVER_HEIGHT_MIX_SMOOTH = '~yPL Straight Over Height Mix Smooth'
STRAIGHT_OVER_HEIGHT_ADD_SMOOTH = '~yPL Straight Over Height Add Smooth'

HEIGHT_COMPARE = '~yPL Height Compare'
HEIGHT_COMPARE_SMOOTH = '~yPL Height Compare Smooth'
STRAIGHT_OVER_HEIGHT_COMPARE = '~yPL Straight Over Height Compare'
STRAIGHT_OVER_HEIGHT_COMPARE_SMOOTH = '~yPL Straight Over Height Compare Smooth'

BUMP_2_NORMAL = '~yPL Bump to Normal'
BUMP_2_NORMAL_SMOOTH = '~yPL Bump to Normal Smooth'
GROUP_BUMP_2_NORMAL = '~yPL Group Bump to Normal'
GROUP_BUMP_2_NORMAL_SMOOTH = '~yPL Group Bump to Normal Smooth'

NORMAL_EMISSION_VIEWER = '~yPL Normal Emission Viewer'
ADVANCED_EMISSION_VIEWER = '~yPL Advanced Emission Viewer'
ADVANCED_NORMAL_EMISSION_VIEWER = '~yPL Advanced Normal Emission Viewer'
#GRID_EMISSION_VIEWER = '~yPL Grid Emission Viewer'

ENGINE_FILTER = '~yPL Engine Filter'

UNPACK_ONSEW = '~yPL Unpack ONSEW'
PACK_ONSEW = '~yPL Pack ONSEW'

BL27_DISP = '~yPL Blender 2.7 Displacement'
COMBINED_VDM = '~yPL Combined VDM'

DECAL_PROCESS = '~yPL Decal Process'

SMOOTH_PREFIX = '~yPL Smooth '

# Nodes that require Blender 2.81 at minimum
EDGE_DETECT = '~yPL Edge Detect'
EDGE_DETECT_CUSTOM_NORMAL = '~yPL Edge Detect Custom Normal'

# Legacy nodes for Blender 2.79
FLIP_BACKFACE_NORMAL_LEGACY = '~yPL Flip Backface Normal Legacy'
FLIP_BACKFACE_BUMP_LEGACY = '~yPL Flip Backface Bump Legacy'
FLIP_BACKFACE_TANGENT_LEGACY = '~yPL Flip Backface Tangent Legacy'
NORMAL_MAP_PREP_LEGACY = '~yPL Normal Map Preparation Legacy'
ENGINE_FILTER_LEGACY = '~yPL Engine Filter Legacy'

TB_DELTA_CALC = '~yPL Transition Bump Delta Calculation'
CH_MAX_HEIGHT_CALC = '~yPL Layer Channel Max Height'
CH_MAX_HEIGHT_TB_CALC = '~yPL Layer Channel Max Height with Transition Bump'
CH_MAX_HEIGHT_TB_ADD_CALC = '~yPL Layer Channel Max Height with Transition Bump Add'
CH_MAX_HEIGHT_TBC_CALC = '~yPL Layer Channel Max Height with Transition Bump Crease'
CH_MAX_HEIGHT_TBC_ADD_CALC = '~yPL Layer Channel Max Height with Transition Bump Crease Add'

EMULATED_CURVE = '~yPL Emulated Curve'
EMULATED_CURVE_FLIP = '~yPL Emulated Curve Flip'
EMULATED_CURVE_SMOOTH = '~yPL Emulated Curve Smooth'
EMULATED_CURVE_SMOOTH_FLIP = '~yPL Emulated Curve Smooth Flip'
FALLOFF_CURVE = '~yPL Falloff Curve'
FALLOFF_CURVE_SMOOTH = '~yPL Falloff Curve Smooth'

START_BUMP_PROCESS = '~yPL Start Bump Process'
START_FINE_BUMP_PROCESS = '~yPL Start Fine Bump Process'
FINE_BUMP_PROCESS = '~yPL Fine Bump Process'
#FINE_BUMP_PROCESS = '~yPL Fine Bump Process Sophisticated'
FINE_BUMP_PROCESS_START_BUMP = '~yPL Fine Bump Process with Start Bump'
FINE_BUMP_PROCESS_START_BUMP_SUBDIV_ON = '~yPL Fine Bump Process with Start Bump Subdiv On'
BUMP_PROCESS = '~yPL Bump Process'
BUMP_PROCESS_SUBDIV_ON = '~yPL Bump Process Subdiv On'
MAX_HEIGHT_TWEAK = '~yPL Max Height Tweak'
MAX_HEIGHT_TWEAK_SMOOTH = '~yPL Max Height Tweak Smooth'
SUBDIV_ON_NORMAL = '~yPL Subdiv On Normal'

# Bake stuff
BAKE_NORMAL = '~yPL Bake Normal'
BAKE_NORMAL_ACTIVE_UV = '~yPL Bake Normal with Active UV'
BAKE_NORMAL_ACTIVE_UV_300 = '~yPL Bake Normal with Active UV 3.0'

# SRGB Stuff
SRGB_2_LINEAR = '~yPL SRGB to Linear'
LINEAR_2_SRGB = '~yPL Linear to SRGB'

FLIP_Y = '~yPL Flip Y'
FLIP_YZ = '~yPL Flip YZ'

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

# GLTF related
GLTF_MATERIAL_OUTPUT = 'glTF Material Output'
GLTF_SETTINGS = 'glTF Settings'

# Manual BSDFs
BL278_BSDF = 'bsdf278'

channel_custom_icon_dict = {
    'RGB' : 'rgb_channel',
    'VALUE' : 'value_channel',
    'NORMAL' : 'vector_channel',
}

def get_icon_folder():
    if not is_bl_newer_than(2, 80):
        icon_set = 'legacy'
    else:
        icons = get_user_preferences().icons 

        if icons == 'DEFAULT':
            bg_color = bpy.context.preferences.themes[0].preferences.space.back
            is_dark_theme = bg_color[0] + bg_color[1] + bg_color[2] < 1.5
            icon_set = 'light' if is_dark_theme else 'dark'
        else:
            icon_set = 'legacy'

    return get_addon_filepath() + 'icons' + os.sep + icon_set.lower() + os.sep

def load_custom_icons():
    import bpy.utils.previews
    # Custom Icon
    if not hasattr(bpy.utils, 'previews'): return
    global custom_icons
    custom_icons = bpy.utils.previews.new()

    folder = get_icon_folder()

    for f in os.listdir(folder):
        icon_name = f.replace('_icon.png', '')
        custom_icons.load(icon_name, folder + f, 'IMAGE')

def unload_custom_icons():
    global custom_icons
    if hasattr(bpy.utils, 'previews'):
        bpy.utils.previews.remove(custom_icons)
        custom_icons = None

def get_icon(custom_icon_name):
    return custom_icons[custom_icon_name].icon_id

def check_uv_difference_to_main_uv(entity):
    yp = entity.id_data.yp
    height_ch = get_root_height_channel(yp)
    if height_ch:
        # Check if entity uv is different to main uv
        if height_ch.main_uv != '' and hasattr(entity, 'uv_name') and entity.uv_name != height_ch.main_uv:
            return True

    return False

def get_neighbor_uv_tree(texcoord_type, entity):

    if texcoord_type == 'UV':
        different_uv = check_uv_difference_to_main_uv(entity)
        if different_uv: return get_node_tree_lib(NEIGHBOR_UV_OTHER_UV)
        return get_node_tree_lib(NEIGHBOR_UV_TANGENT)
    if texcoord_type in {'Generated', 'Normal', 'Object'}:
        return get_node_tree_lib(NEIGHBOR_UV_OBJECT)
    if texcoord_type in {'Camera', 'Window', 'Reflection'}:
        return get_node_tree_lib(NEIGHBOR_UV_CAMERA)

def get_neighbor_uv_tree_name(texcoord_type, entity):
    if texcoord_type == 'UV':
        different_uv = check_uv_difference_to_main_uv(entity)
        if different_uv: return NEIGHBOR_UV_OTHER_UV
        return NEIGHBOR_UV_TANGENT
    if texcoord_type in {'Generated', 'Normal', 'Object', 'Decal'}:
        return NEIGHBOR_UV_OBJECT
    if texcoord_type in {'Camera', 'Window', 'Reflection'}:
        return NEIGHBOR_UV_CAMERA

def get_smooth_mix_node(blend_type, layer_type=''):

    is_group_limited = layer_type == 'GROUP' and blend_type in limited_mask_blend_types

    tree_name = SMOOTH_PREFIX + blend_type
    if is_group_limited:
        tree_name += ' Group'

    tree = bpy.data.node_groups.get(tree_name)

    if not tree:
        tree = bpy.data.node_groups.new(tree_name, 'ShaderNodeTree')

        # IO
        inp = new_tree_input(tree, 'Fac', 'NodeSocketFloatFactor')
        inp.min_value = 0.0
        inp.max_value = 1.0

        new_tree_input(tree, 'Color1', 'NodeSocketColor')
        for d in neighbor_directions:
            new_tree_input(tree, 'Color1 ' + d, 'NodeSocketColor')

        new_tree_input(tree, 'Color2', 'NodeSocketColor')
        for d in neighbor_directions:
            new_tree_input(tree, 'Color2 ' + d, 'NodeSocketColor')

        new_tree_output(tree, 'Color', 'NodeSocketColor')
        for d in neighbor_directions:
            new_tree_output(tree, 'Color ' + d, 'NodeSocketColor')

        # Group alpha limit inputs
        if is_group_limited:
            inp = new_tree_input(tree, 'Limit', 'NodeSocketFloat')
            inp.default_value = 1.0
            for d in neighbor_directions:
                inp = new_tree_input(tree, 'Limit ' + d, 'NodeSocketFloat')
                inp.default_value = 1.0

        # Nodes
        create_essential_nodes(tree)

        start = tree.nodes.get(TREE_START)
        end = tree.nodes.get(TREE_END)

        loc = Vector((0, 0))

        start.location = loc

        loc.x += 200
        bookmark_x = loc.x

        mix = simple_new_mix_node(tree)
        mixcol0, mixcol1, mixout = get_mix_color_indices(mix)
        mix.name = '_mix'
        mix.blend_type = blend_type
        if blend_type not in {'MIX', 'MULTIPLY'}: 
            set_mix_clamp(mix, True)

        mix.location = loc

        tree.links.new(start.outputs['Fac'], mix.inputs[0])
        tree.links.new(start.outputs['Color1'], mix.inputs[mixcol0])
        tree.links.new(start.outputs['Color2'], mix.inputs[mixcol1])
        if not is_group_limited:
            tree.links.new(mix.outputs[mixout], end.inputs['Color'])
        else:
            loc.x += 200

            limit = tree.nodes.new('ShaderNodeMath')
            limit.name = '_limit'
            limit.operation = 'MINIMUM'
            limit.use_clamp = True

            limit.location = loc

            tree.links.new(mix.outputs[mixout], limit.inputs[0])
            tree.links.new(start.outputs['Limit'], limit.inputs[1])
            tree.links.new(limit.outputs[0], end.inputs['Color'])

        loc.y -= 200

        for d in neighbor_directions:

            loc.x = bookmark_x

            mix = simple_new_mix_node(tree)
            mixcol0, mixcol1, mixout = get_mix_color_indices(mix)
            mix.name = '_mix_' + d
            mix.blend_type = blend_type
            if blend_type not in {'MIX', 'MULTIPLY'}: 
                set_mix_clamp(mix, True)

            mix.location = loc

            tree.links.new(start.outputs['Fac'], mix.inputs[0])
            tree.links.new(start.outputs['Color1 ' + d], mix.inputs[mixcol0])
            tree.links.new(start.outputs['Color2 ' + d], mix.inputs[mixcol1])

            if not is_group_limited:
                tree.links.new(mix.outputs[mixout], end.inputs['Color ' + d])
            else:
                loc.x += 200

                limit = tree.nodes.new('ShaderNodeMath')
                limit.name = '_limit_' + d
                limit.operation = 'MINIMUM'
                limit.use_clamp = True

                limit.location = loc

                tree.links.new(mix.outputs[mixout], limit.inputs[0])
                tree.links.new(start.outputs['Limit ' + d], limit.inputs[1])
                tree.links.new(limit.outputs[0], end.inputs['Color ' + d])

            loc.y -= 200

        loc.x += 200

        end.location.x = loc.x

    return tree

def clean_unused_libraries():
    for ng in bpy.data.node_groups:
        if ng.name.startswith('~yPL ') and ng.users == 0:
            remove_datablock(bpy.data.node_groups, ng)

def register():
    load_custom_icons()

def unregister():
    unload_custom_icons()
