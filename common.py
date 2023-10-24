import bpy, os, sys, re, time, numpy, math
from mathutils import *
from bpy.app.handlers import persistent
#from .__init__ import bl_info

BLENDER_28_GROUP_INPUT_HACK = False

MAX_VERTEX_DATA = 8

LAYERGROUP_PREFIX = '~yP Layer '
MASKGROUP_PREFIX = '~yP Mask '

INFO_PREFIX = '__yp_info_'

TREE_START = 'Group Input'
TREE_END = 'Group Output'
ONE_VALUE = 'One Value'
ZERO_VALUE = 'Zero Value'

BAKED_PARALLAX = 'Baked Parallax'
BAKED_PARALLAX_FILTER = 'Baked Parallax Filter'

TEXCOORD = 'Texture Coordinate'
GEOMETRY = 'Geometry'

PARALLAX_PREP_SUFFIX = ' Parallax Preparation'
PARALLAX = 'Parallax'

MOD_TREE_START = '__mod_start'
MOD_TREE_END = '__mod_end'

HEIGHT_MAP = 'Height Map'

START_UV = ' Start UV'
DELTA_UV = ' Delta UV'
CURRENT_UV = ' Current UV'

LAYER_VIEWER = '_Layer Viewer'
LAYER_ALPHA_VIEWER = '_Layer Alpha Viewer'
EMISSION_VIEWER = 'Emission Viewer'

ITERATE_GROUP = '~yP Iterate Parallax Group'
PARALLAX_DIVIDER = 4

FLOW_VCOL = '__flow_'

COLOR_ID_VCOL_NAME = '__yp_color_id'

BUMP_MULTIPLY_TWEAK = 5

blend_type_items = (("MIX", "Mix", ""),
	             ("ADD", "Add", ""),
	             ("SUBTRACT", "Subtract", ""),
	             ("MULTIPLY", "Multiply", ""),
	             ("SCREEN", "Screen", ""),
	             ("OVERLAY", "Overlay", ""),
	             ("DIFFERENCE", "Difference", ""),
	             ("DIVIDE", "Divide", ""),
	             ("DARKEN", "Darken", ""),
	             ("LIGHTEN", "Lighten", ""),
	             ("HUE", "Hue", ""),
	             ("SATURATION", "Saturation", ""),
	             ("VALUE", "Value", ""),
	             ("COLOR", "Color", ""),
	             ("SOFT_LIGHT", "Soft Light", ""),
	             ("LINEAR_LIGHT", "Linear Light", ""))

mask_blend_type_items = (("MIX", "Replace", ""),
	             ("ADD", "Add", ""),
	             ("SUBTRACT", "Subtract", ""),
	             ("MULTIPLY", "Multiply", ""),
	             ("SCREEN", "Screen", ""),
	             ("OVERLAY", "Overlay", ""),
	             ("DIFFERENCE", "Difference", ""),
	             ("DIVIDE", "Divide", ""),
	             ("DARKEN", "Darken", ""),
	             ("LIGHTEN", "Lighten", ""),
	             ("HUE", "Hue", ""),
	             ("SATURATION", "Saturation", ""),
	             ("VALUE", "Value", ""),
	             ("COLOR", "Color", ""),
	             ("SOFT_LIGHT", "Soft Light", ""),
	             ("LINEAR_LIGHT", "Linear Light", ""))

COLORID_TOLERANCE = 0.003906 # 1/256

TEMP_UV = '~TL Temp Paint UV'

TANGENT_SIGN_PREFIX = '__tsign_'

neighbor_directions = ['n', 's', 'e', 'w']

normal_blend_items = (
        ('MIX', 'Mix', ''),
        #('VECTOR_MIX', 'Vector Mix', ''),
        ('OVERLAY', 'Overlay', ''),
        ('COMPARE', 'Compare Height', '')
        )

height_blend_items = (
        ('REPLACE', 'Replace', ''),
        ('COMPARE', 'Compare', ''),
        ('ADD', 'Add', ''),
        )

layer_type_items = (
        ('IMAGE', 'Image', ''),
        #('ENVIRONMENT', 'Environment', ''),
        ('BRICK', 'Brick', ''),
        ('CHECKER', 'Checker', ''),
        ('GRADIENT', 'Gradient', ''),
        ('MAGIC', 'Magic', ''),
        ('MUSGRAVE', 'Musgrave', ''),
        ('NOISE', 'Noise', ''),
        #('POINT_DENSITY', 'Point Density', ''),
        #('SKY', 'Sky', ''),
        ('VORONOI', 'Voronoi', ''),
        ('WAVE', 'Wave', ''),
        ('VCOL', 'Vertex Color', ''),
        ('BACKGROUND', 'Background', ''),
        ('COLOR', 'Solid Color', ''),
        ('GROUP', 'Group', ''),
        ('HEMI', 'Fake Lighting', ''),
        )

mask_type_items = (
        ('IMAGE', 'Image', ''),
        #('ENVIRONMENT', 'Environment', ''),
        ('BRICK', 'Brick', ''),
        ('CHECKER', 'Checker', ''),
        ('GRADIENT', 'Gradient', ''),
        ('MAGIC', 'Magic', ''),
        ('MUSGRAVE', 'Musgrave', ''),
        ('NOISE', 'Noise', ''),
        #('POINT_DENSITY', 'Point Density', ''),
        #('SKY', 'Sky', ''),
        ('VORONOI', 'Voronoi', ''),
        ('WAVE', 'Wave', ''),
        ('VCOL', 'Vertex Color', ''),
        ('HEMI', 'Fake Lighting', ''),
        ('OBJECT_INDEX', 'Object Index', ''),
        ('COLOR_ID', 'Color ID', '')
        )

channel_override_type_items = (
        ('DEFAULT', 'Default', ''),
        ('IMAGE', 'Image', ''),
        #('ENVIRONMENT', 'Environment', ''),
        ('BRICK', 'Brick', ''),
        ('CHECKER', 'Checker', ''),
        ('GRADIENT', 'Gradient', ''),
        ('MAGIC', 'Magic', ''),
        ('MUSGRAVE', 'Musgrave', ''),
        ('NOISE', 'Noise', ''),
        #('POINT_DENSITY', 'Point Density', ''),
        #('SKY', 'Sky', ''),
        ('VORONOI', 'Voronoi', ''),
        ('WAVE', 'Wave', ''),
        ('VCOL', 'Vertex Color', ''),
        #('BACKGROUND', 'Background', ''),
        #('COLOR', 'Solid Color', ''),
        #('GROUP', 'Group', ''),
        #('HEMI', 'Fake Lighting', ''),
        )

# Override 1 will only use default value or image for now
channel_override_1_type_items = (
        ('DEFAULT', 'Default', ''),
        ('IMAGE', 'Image', ''),
        )

hemi_space_items = (
        ('WORLD', 'World Space', ''),
        ('OBJECT', 'Object Space', ''),
        ('CAMERA', 'Camera Space', ''),
        )

layer_type_labels = {
        'IMAGE' : 'Image',
        #'ENVIRONMENT' : 'Environment',
        'BRICK' : 'Brick',
        'CHECKER' : 'Checker',
        'GRADIENT' : 'Gradient',
        'MAGIC' : 'Magic',
        'MUSGRAVE' : 'Musgrave',
        'NOISE' : 'Noise',
        #'POINT_DENSITY' : 'Point Density',
        #'SKY' : 'Sky',
        'VORONOI' : 'Voronoi',
        'WAVE' : 'Wave',
        'VCOL' : 'Vertex Color',
        'BACKGROUND' : 'Background',
        'COLOR' : 'Solid Color',
        'GROUP' : 'Layer Group',
        'HEMI' : 'Fake Lighting',
        }

bake_type_items = (
        ('AO', 'Ambient Occlusion', ''),
        ('POINTINESS', 'Pointiness', ''),
        ('CAVITY', 'Cavity', ''),
        ('DUST', 'Dust', ''),
        ('PAINT_BASE', 'Paint Base', ''),

        ('BEVEL_NORMAL', 'Bevel Normal', ''),
        ('BEVEL_MASK', 'Bevel Grayscale', ''),

        ('MULTIRES_NORMAL', 'Multires Normal', ''),
        ('MULTIRES_DISPLACEMENT', 'Multires Displacement', ''),

        ('OTHER_OBJECT_NORMAL', 'Other Objects Normal', ''),
        ('OTHER_OBJECT_EMISSION', 'Other Objects Emission', ''),
        ('OTHER_OBJECT_CHANNELS', 'Other Objects Ucupaint Channels', ''),

        ('SELECTED_VERTICES', 'Selected Vertices/Edges/Faces', ''),

        ('FLOW', 'Flow Map based on straight UVMap', ''),
        )

channel_override_labels = {
        'DEFAULT' : 'Default',
        'IMAGE' : 'Image',
        'BRICK' : 'Brick',
        'CHECKER' : 'Checker',
        'GRADIENT' : 'Gradient',
        'MAGIC' : 'Magic',
        'MUSGRAVE' : 'Musgrave',
        'NOISE' : 'Noise',
        'VORONOI' : 'Voronoi',
        'WAVE' : 'Wave',
        'VCOL' : 'Vertex Color',
        'HEMI' : 'Fake Lighting',
        }

bake_type_labels = {
        'AO' : 'Ambient Occlusion',
        'POINTINESS': 'Pointiness',
        'CAVITY': 'Cavity',
        'DUST': 'Dust',
        'PAINT_BASE': 'Paint Base',

        'BEVEL_NORMAL': 'Bevel Normal',
        'BEVEL_MASK': 'Bevel Grayscale',

        'MULTIRES_NORMAL': 'Multires Normal',
        'MULTIRES_DISPLACEMENT': 'Multires Displacement',

        'OTHER_OBJECT_NORMAL': 'Other Objects Normal',
        'OTHER_OBJECT_EMISSION': 'Other Objects Emission',
        'OTHER_OBJECT_CHANNELS': 'Other Objects Ucupaint Channels',

        'SELECTED_VERTICES': 'Selected Vertices',

        'FLOW': 'Flow'
        }

bake_type_suffixes = {
        'AO' : 'AO',
        'POINTINESS': 'Pointiness',
        'CAVITY': 'Cavity',
        'DUST': 'Dust',
        'PAINT_BASE': 'Paint Base',

        'BEVEL_NORMAL': 'Bevel Normal',
        'BEVEL_MASK': 'Bevel Grayscale',

        'MULTIRES_NORMAL': 'Normal Multires',
        'MULTIRES_DISPLACEMENT': 'Displacement Multires',

        'OTHER_OBJECT_NORMAL': 'OO Normal',
        'OTHER_OBJECT_EMISSION': 'OO Emission',
        'OTHER_OBJECT_CHANNELS': 'OO Channel',

        'SELECTED_VERTICES': 'Selected Vertices',

        'FLOW': 'Flow'
        }

texcoord_lists = [
        'Generated',
        'Normal',
        #'UV',
        'Object',
        'Camera',
        'Window',
        'Reflection',
        ]

texcoord_type_items = (
        ('Generated', 'Generated', ''),
        ('Normal', 'Normal', ''),
        ('UV', 'UV', ''),
        ('Object', 'Object', ''),
        ('Camera', 'Camera', ''),
        ('Window', 'Window', ''),
        ('Reflection', 'Reflection', ''),
        )

channel_socket_input_bl_idnames = {
    'RGB': 'NodeSocketColor',
    'VALUE': 'NodeSocketFloatFactor',
    'NORMAL': 'NodeSocketVector',
}

channel_socket_output_bl_idnames = {
    'RGB': 'NodeSocketColor',
    'VALUE': 'NodeSocketFloat',
    'NORMAL': 'NodeSocketVector',
}

possible_object_types = {
        'MESH',
        'META',
        'CURVE',
        'CURVES',
        'SURFACE',
        'FONT'
        }

texture_node_types = {
        'TEX_IMAGE',
        'TEX_BRICK',
        'TEX_ENVIRONMENT',
        'TEX_CHECKER',
        'TEX_GRADIENT',
        'TEX_MAGIC',
        'TEX_MUSGRAVE',
        'TEX_NOISE',
        'TEX_POINTDENSITY',
        'TEX_SKY',
        'TEX_VORONOI',
        'TEX_WAVE',
        }

layer_node_bl_idnames = {
        'IMAGE' : 'ShaderNodeTexImage',
        'ENVIRONMENT' : 'ShaderNodeTexEnvironment',
        'BRICK' : 'ShaderNodeTexBrick',
        'CHECKER' : 'ShaderNodeTexChecker',
        'GRADIENT' : 'ShaderNodeTexGradient',
        'MAGIC' : 'ShaderNodeTexMagic',
        'MUSGRAVE' : 'ShaderNodeTexMusgrave',
        'NOISE' : 'ShaderNodeTexNoise',
        'POINT_DENSITY' : 'ShaderNodeTexPointDensity',
        'SKY' : 'ShaderNodeTexSky',
        'VORONOI' : 'ShaderNodeTexVoronoi',
        'WAVE' : 'ShaderNodeTexWave',
        'VCOL' : 'ShaderNodeAttribute',
        'BACKGROUND' : 'NodeGroupInput',
        'COLOR' : 'ShaderNodeRGB',
        'GROUP' : 'NodeGroupInput',
        'HEMI' : 'ShaderNodeGroup',
        'OBJECT_INDEX' : 'ShaderNodeGroup',
        'COLOR_ID' : 'ShaderNodeGroup',
        }

io_suffix = {
        'GROUP' : ' Group',
        'BACKGROUND' : ' Background',
        'ALPHA' : ' Alpha',
        'DISPLACEMENT' : ' Displacement',
        'HEIGHT' : ' Height',
        'MAX_HEIGHT' : ' Max Height',
        'HEIGHT_ONS' : ' Height ONS',
        'HEIGHT_EW' : ' Height EW',
        'UV' : ' UV',
        'TANGENT' : ' Tangent',
        'BITANGENT' : ' Bitangent',
        }

io_names = {
        'Generated' : 'Texcoord Generated',
        'Object' : 'Texcoord Object',
        'Normal' : 'Texcoord Normal',
        'Camera' : 'Texcoord Camera',
        'Window' : 'Texcoord Window',
        'Reflection' : 'Texcoord Reflection',
        }

math_method_items = (
    ("ADD", "Add", ""),
    ("SUBTRACT", "Subtract", ""),
    ("MULTIPLY", "Multiply", ""),
    ("DIVIDE", "Divide", ""),
    ("POWER", "Power", ""),
    ("LOGARITHM", "Logarithm", ""),
    )

vcol_domain_items = (
    ('POINT', 'Vertex', ''),
    ('CORNER', 'Face Corner', ''),
    )

vcol_data_type_items = (
    ('FLOAT_COLOR', 'Color', ''),
    ('BYTE_COLOR', 'Byte Color', ''),
    )

limited_mask_blend_types = {
    'ADD',
    'DIVIDE',
    'SCREEN',
    'MIX',
    'DIFFERENCE',
    'LIGHTEN',
    'VALUE',
    'LINEAR_LIGHT',
    }

TEXCOORD_IO_PREFIX = 'Texcoord '
PARALLAX_MIX_PREFIX = 'Parallax Mix '
PARALLAX_DELTA_PREFIX = 'Parallax Delta '
PARALLAX_CURRENT_PREFIX = 'Parallax Current '
PARALLAX_CURRENT_MIX_PREFIX = 'Parallax Current Mix '

GAMMA = 2.2

def versiontuple(v):
    return tuple(map(int, (v.split("."))))

def get_addon_name():
    return os.path.basename(os.path.dirname(bpy.path.abspath(__file__)))

def get_addon_title():
    bl_info = sys.modules[get_addon_name()].bl_info
    return bl_info['name']

def get_addon_warning():
    bl_info = sys.modules[get_addon_name()].bl_info
    return bl_info['warning']

def get_alpha_suffix():
    bl_info = sys.modules[get_addon_name()].bl_info
    if 'Alpha' in bl_info['warning']:
        return ' Alpha'
    elif 'Beta' in bl_info['warning']:
        return ' Beta'
    return ''

def get_current_version_str():
    bl_info = sys.modules[get_addon_name()].bl_info
    return str(bl_info['version']).replace(', ', '.').replace('(','').replace(')','')

def is_greater_than_280():
    if bpy.app.version >= (2, 80, 0):
        return True
    return False

def is_greater_than_281():
    if bpy.app.version >= (2, 81, 0):
        return True
    return False

def is_greater_than_282():
    if bpy.app.version >= (2, 82, 0):
        return True
    return False

def is_greater_than_283():
    if bpy.app.version >= (2, 83, 0):
        return True
    return False

def is_greater_than_292():
    if bpy.app.version >= (2, 92, 0):
        return True
    return False

def is_greater_than_300():
    if bpy.app.version >= (3, 00, 0):
        return True
    return False

def is_greater_than_320():
    if bpy.app.version >= (3, 2, 0):
        return True
    return False

def is_version_320():
    if bpy.app.version[0] == 3 and bpy.app.version[1] == 2:
        return True
    return False

def is_greater_than_330():
    if bpy.app.version >= (3, 3, 0):
        return True
    return False

def is_greater_than_340():
    if bpy.app.version >= (3, 4, 0):
        return True
    return False

def is_greater_than_350():
    if bpy.app.version >= (3, 5, 0):
        return True
    return False

def is_greater_than_400():
    if bpy.app.version >= (4, 0, 0):
        return True
    return False

def is_created_using_279():
    if bpy.data.version[:2] == (2, 79):
        return True
    return False

def is_created_before_300():
    if bpy.data.version[:2] < (3, 0):
        return True
    return False

def is_created_before_340():
    if bpy.data.version[:2] < (3, 4):
        return True
    return False

def is_created_using_280():
    if bpy.data.version[:2] == (2, 80):
        return True
    return False

def is_created_before_292():
    if bpy.data.version < (2, 92, 0):
        return True
    return False

def set_active_object(obj):
    if is_greater_than_280():
        bpy.context.view_layer.objects.active = obj
    else: bpy.context.scene.objects.active = obj

def link_object(scene, obj):
    if is_greater_than_280():
        scene.collection.objects.link(obj)
    else: scene.objects.link(obj)

def get_object_select(obj):
    if is_greater_than_280():
        try: return obj.select_get()
        except: return False
    else: return obj.select

def set_object_select(obj, val):
    if is_greater_than_280():
        obj.select_set(val)
    else: obj.select = val

def set_object_hide(obj, val):
    if is_greater_than_280():
        obj.hide_set(val)
    else: obj.hide = val

def get_scene_objects():
    if is_greater_than_280():
        return bpy.context.view_layer.objects
    else: return bpy.context.scene.objects

def get_viewport_shade():
    if is_greater_than_280():
        return bpy.context.area.spaces[0].shading.type
    else: return bpy.context.area.spaces[0].viewport_shade

def get_user_preferences():
    if is_greater_than_280():
        return bpy.context.preferences.addons[__package__].preferences
    return bpy.context.user_preferences.addons[__package__].preferences

def get_all_layer_collections(arr, col):
    if col not in arr:
        arr.append(col)
    for c in col.children:
        arr = get_all_layer_collections(arr, c)
    return arr

def get_object_parent_layer_collections(arr, col, obj):
    for o in col.collection.objects:
        if o == obj:
            if col not in arr: arr.append(col)

    if not arr:
        for c in col.children:
            get_object_parent_layer_collections(arr, c, obj)
            if arr: break

    if arr:
        if col not in arr: arr.append(col)

    return arr

def get_node_input_index(node, inp):
    index = -1

    try: index = [i for i, s in enumerate(node.inputs) if s == inp][0]
    except Exception as e: print(e)

    return index

def get_active_material():
    scene = bpy.context.scene
    engine = scene.render.engine
    obj = None
    if hasattr(bpy.context, 'object'):
        obj = bpy.context.object
    elif is_greater_than_280():
        obj = bpy.context.view_layer.objects.active

    if not obj: return None

    mat = obj.active_material

    if engine in {'BLENDER_RENDER', 'BLENDER_GAME'}:
        return None

    return mat

def get_list_of_ypaint_nodes(mat):

    if not mat.node_tree: return []
    
    yp_nodes = []
    for node in mat.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree.yp.is_ypaint_node:
            yp_nodes.append(node)

    return yp_nodes

def in_active_279_layer(obj):
    scene = bpy.context.scene
    space = bpy.context.space_data
    if space.type == 'VIEW_3D' and space.local_view:
        return any([layer for layer in obj.layers_local_view if layer])
    else:
        return any([layer for i, layer in enumerate(obj.layers) if layer and scene.layers[i]])

def in_renderable_layer_collection(obj):
    if is_greater_than_280():
        layer_cols = get_object_parent_layer_collections([], bpy.context.view_layer.layer_collection, obj)
        if any([lc for lc in layer_cols if lc.collection.hide_render]): return False
        return True
    else:
        return in_active_279_layer(obj)

def is_layer_collection_hidden(obj):
    layer_cols = get_object_parent_layer_collections([], bpy.context.view_layer.layer_collection, obj)
    if any([lc for lc in layer_cols if lc.collection.hide_viewport]): return True
    if any([lc for lc in layer_cols if lc.hide_viewport]): return True
    return False

def get_addon_filepath():
    return os.path.dirname(bpy.path.abspath(__file__)) + os.sep

def srgb_to_linear_per_element(e):
    if e <= 0.03928:
        return e/12.92
    else: 
        return pow((e + 0.055) / 1.055, 2.4)

def linear_to_srgb_per_element(e):
    if e > 0.0031308:
        return 1.055 * (pow(e, (1.0 / 2.4))) - 0.055
    else: 
        return 12.92 * e

def srgb_to_linear(inp):

    if type(inp) == float:
        return srgb_to_linear_per_element(inp)

    elif type(inp) == Color:

        c = inp.copy()

        for i in range(3):
            c[i] = srgb_to_linear_per_element(c[i])

        return c

def linear_to_srgb(inp):

    if type(inp) == float:
        return linear_to_srgb_per_element(inp)

    elif type(inp) == Color:

        c = inp.copy()

        for i in range(3):
            c[i] = linear_to_srgb_per_element(c[i])

        return c

def divide_round_i(a, b):
    return (2 * a + b) / (2 * b)

def blend_color_mix_byte(src1, src2, intensity1=1.0, intensity2=1.0):
    dst = [0.0, 0.0, 0.0, 0.0]

    c1 = list(src1)
    c2 = list(src2)

    c1[3] *= intensity1
    c2[3] *= intensity2

    if c2[3] != 0.0:

        # Multiply first by 255
        for i in range(4):
            c1[i] *= 255
            c2[i] *= 255

        # Straight over operation
        t = c2[3]
        mt = 255 - t
        tmp = [0.0, 0.0, 0.0, 0.0]
        
        tmp[0] = (mt * c1[3] * c1[0]) + (t * 255 * c2[0])
        tmp[1] = (mt * c1[3] * c1[1]) + (t * 255 * c2[1])
        tmp[2] = (mt * c1[3] * c1[2]) + (t * 255 * c2[2])
        tmp[3] = (mt * c1[3]) + (t * 255)
        
        dst[0] = divide_round_i(tmp[0], tmp[3])
        dst[1] = divide_round_i(tmp[1], tmp[3])
        dst[2] = divide_round_i(tmp[2], tmp[3])
        dst[3] = divide_round_i(tmp[3], 255)

        # Divide it back
        for i in range(4):
            dst[i] /= 255

    else :
        # No op
        dst[0] = c1[0]
        dst[1] = c1[1]
        dst[2] = c1[2]
        dst[3] = c1[3]

    return dst

def copy_id_props(source, dest, extras = []):
    props = dir(source)
    #print()
    #print(source)
    filters = ['bl_rna', 'rna_type']
    filters.extend(extras)

    for prop in props:
        if prop.startswith('__'): continue
        if prop in filters: continue
        #print(prop)
        try: val = getattr(source, prop)
        except:
            print('Error prop:', prop)
            continue
        attr_type = str(type(val))
        #print(attr_type, prop)

        if 'bpy_prop_collection_idprop' in attr_type:
            dest_val = getattr(dest, prop)
            for subval in val:
                dest_subval = dest_val.add()
                copy_id_props(subval, dest_subval)

        elif 'bpy_prop_array' in attr_type:
            dest_val = getattr(dest, prop)
            for i, subval in enumerate(val):
                dest_val[i] = subval
        else:
            try: setattr(dest, prop, val)
            except: print('Error set prop:', prop)

def copy_node_props_(source, dest, extras = []):
    #print()
    props = dir(source)
    filters = ['rna_type', 'name', 'location', 'parent']
    filters.extend(extras)
    #print()
    for prop in props:
        if prop.startswith('__'): continue
        if prop.startswith('bl_'): continue
        if prop in filters: continue
        val = getattr(source, prop)
        attr_type = str(type(val))
        if 'bpy_func' in attr_type: continue
        #if 'bpy_prop' in attr_type: continue
        #print(prop, str(type(getattr(source, prop))))
        # Copy stuff here

        #if 'bpy_prop_collection_idprop' in attr_type:
        #    dest_val = getattr(dest, prop)
        #    for subval in val:
        #        dest_subval = dest_val.add()
        #        copy_id_props(subval, dest_subval)

        if 'bpy_prop_array' in attr_type:
            dest_val = getattr(dest, prop)
            for i, subval in enumerate(val):
                try: 
                    dest_val[i] = subval
                    #print('SUCCESS:', prop, dest_val[i])
                except: 
                    #print('FAILED:', prop, dest_val[i])
                    pass
        else:
            try: 
                setattr(dest, prop, val)
                #print('SUCCESS:', prop, val)
            except: 
                #print('FAILED:', prop, val)
                pass

def copy_node_props(source, dest, extras = []):
    # Copy node props
    copy_node_props_(source, dest, extras)

    if source.type == 'CURVE_RGB':

        # Copy mapping props
        copy_node_props_(source.mapping, dest.mapping)
        
        # Copy curve props
        for i, curve in enumerate(source.mapping.curves):
            curve_copy = dest.mapping.curves[i]
            copy_node_props_(curve, curve_copy)
    
            # Copy point props
            for j, point in enumerate(curve.points):
                if j >= len(curve_copy.points):
                    point_copy = curve_copy.points.new(point.location[0], point.location[1])
                else: 
                    point_copy = curve_copy.points[j]
                    point_copy.location = (point.location[0], point.location[1])
                copy_node_props_(point, point_copy)
                
            # Copy selection
            for j, point in enumerate(curve.points):
                point_copy = curve_copy.points[j]
                point_copy.select = point.select
                
        # Update curve
        dest.mapping.update()
    
    elif source.type == 'VALTORGB':
    
        # Copy color ramp props
        copy_node_props_(source.color_ramp, dest.color_ramp)
        
        # Copy color ramp elements
        for i, elem in enumerate(source.color_ramp.elements):
            if i >= len(dest.color_ramp.elements):
                elem_copy = dest.color_ramp.elements.new(elem.position)
            else: elem_copy = dest.color_ramp.elements[i]
            copy_node_props_(elem, elem_copy)

    elif source.type in texture_node_types:

        # Copy texture mapping
        copy_node_props_(source.texture_mapping, dest.texture_mapping)

    # Copy inputs default value
    for i, inp in enumerate(source.inputs):
        socket_name = source.inputs[i].name
        if socket_name in dest.inputs and dest.inputs[i].name == socket_name:
            dest.inputs[i].default_value = inp.default_value

    # Copy outputs default value
    for i, outp in enumerate(source.outputs):
        dest.outputs[i].default_value = outp.default_value 

def update_image_editor_image(context, image):
    obj = context.object
    scene = context.scene

    if obj.mode == 'EDIT':
        space = get_edit_image_editor_space(context)
        if space:
            space.use_image_pin = True
            space.image = image
    else:
        space = get_first_unpinned_image_editor_space(context)
        if space: 
            space.image = image
            # Hack for Blender 2.8 which keep pinning image automatically
            space.use_image_pin = False

def get_edit_image_editor_space(context):
    scene = context.scene
    area_index = scene.yp.edit_image_editor_area_index
    if area_index >= 0 and area_index < len(context.screen.areas):
        area = context.screen.areas[area_index]
        if area.type == 'IMAGE_EDITOR':
            return area.spaces[0]

    return None

def get_first_unpinned_image_editor_space(context, return_index=False):
    space = None
    index = -1
    for i, area in enumerate(context.screen.areas):
        if area.type == 'IMAGE_EDITOR':
            if not area.spaces[0].use_image_pin:
                space = area.spaces[0]
                index = i
                break

    if return_index:
        return space, index

    return space

def get_first_image_editor_image(context):
    space = get_first_unpinned_image_editor_space(context)
    if space: return space.image
    return None

def update_tool_canvas_image(context, image):
    # HACK: Remember unpinned images to avoid all image editor images being updated
    unpinned_spaces = []
    unpinned_images = []
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR' and not area.spaces[0].use_image_pin: #and area.spaces[0].image != image:
            unpinned_spaces.append(area.spaces[0])
            unpinned_images.append(area.spaces[0].image)

    # Update canvas image
    context.scene.tool_settings.image_paint.canvas = image

    # Restore original images except for the first index
    for i, space in enumerate(unpinned_spaces):
        if i > 0:
            space.image = unpinned_images[i]
            # Hack for Blender 2.8 which keep pinning image automatically
            space.use_image_pin = False

# Check if name already available on the list
def get_unique_name(name, items, surname = ''):

    if surname != '':
        unique_name = name + ' ' + surname
    else: unique_name = name

    name_found = [item for item in items if item.name == unique_name]
    if name_found:

        m = re.match(r'^(.+)\s(\d*)$', name)
        if m:
            name = m.group(1)
            i = int(m.group(2))
        else:
            i = 1

        while True:

            if surname != '':
                new_name = name + ' ' + str(i) + ' ' + surname
            else: new_name = name + ' ' + str(i)

            name_found = [item for item in items if item.name == new_name]
            if not name_found:
                unique_name = new_name
                break
            i += 1

    return unique_name

def get_active_node():
    mat = get_active_material()
    if not mat or not mat.node_tree: return None
    node = mat.node_tree.nodes.active
    return node

# Specific methods for this addon

def get_active_ypaint_node():
    ypui = bpy.context.window_manager.ypui

    # Get material UI prop
    mat = get_active_material()
    if not mat or not mat.node_tree: 
        ypui.active_mat = ''
        return None

    # Search for its name first
    mui = ypui.materials.get(mat.name)

    # Flag for indicate new mui just created
    change_name = False

    # If still not found, create one
    if not mui:

        if ypui.active_mat != '':
            prev_mat = bpy.data.materials.get(ypui.active_mat)
            if not prev_mat:
                #print(ypui.active_mat)
                change_name = True
                # Remove prev mui
                prev_idx = [i for i, m in enumerate(ypui.materials) if m.name == ypui.active_mat]
                if prev_idx:
                    ypui.materials.remove(prev_idx[0])
                    #print('Removed!')

        mui = ypui.materials.add()
        mui.name = mat.name
        #print('New MUI!', mui.name)

    if ypui.active_mat != mat.name:
        ypui.active_mat = mat.name

    # Try to get yp node
    node = get_active_node()
    if node and node.type == 'GROUP' and node.node_tree and node.node_tree.yp.is_ypaint_node:
        # Update node name
        if mui.active_ypaint_node != node.name:
            #print('From:', mui.active_ypaint_node)
            mui.active_ypaint_node = node.name
            #print('To:', node.name)
        if ypui.active_ypaint_node != node.name:
            ypui.active_ypaint_node = node.name
        return node

    # If not active node isn't a group node
    # New mui possibly means material name just changed, try to get previous active node
    if change_name: 
        node = mat.node_tree.nodes.get(ypui.active_ypaint_node)
        if node:
            #print(mui.name, 'Change name from:', mui.active_ypaint_node)
            mui.active_ypaint_node = node.name
            #print(mui.name, 'Change name to', mui.active_ypaint_node)
            return node

    node = mat.node_tree.nodes.get(mui.active_ypaint_node)
    #print(mui.active_ypaint_node, node)
    if node: return node

    # If node still not found
    for node in mat.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree and node.node_tree.yp.is_ypaint_node:
            #print('Last resort!', mui.name, mui.active_ypaint_node)
            mui.active_ypaint_node = node.name
            return node

    return None

def is_yp_on_material(yp, mat):
    if not mat.use_nodes: return False
    for node in mat.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree and node.node_tree.yp == yp:
            return True
    
    return False

def get_materials_using_yp(yp):
    mats = []
    for mat in bpy.data.materials:
        if not mat.use_nodes: continue
        for node in mat.node_tree.nodes:
            if node.type == 'GROUP' and node.node_tree and node.node_tree.yp == yp and mat not in mats:
                mats.append(mat)
    return mats

def get_nodes_using_yp(mat, yp):
    if not mat.use_nodes: return []
    yp_nodes = []
    for node in mat.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree and node.node_tree.yp == yp:
            yp_nodes.append(node)
    return yp_nodes

#def remove_tree_data_recursive(node):
#
#    try: tree = node.node_tree
#    except: return
#    
#    for n in tree.nodes:
#        if n.type == 'GROUP' and n.node_tree:
#            remove_tree_data_recursive(n)
#            n.node_tree = None
#
#    node.node_tree = None
#
#    if tree.users == 0:
#        bpy.data.node_groups.remove(tree)

def safe_remove_image(image):
    scene = bpy.context.scene

    if ((scene.tool_settings.image_paint.canvas == image and image.users == 2) or
        (scene.tool_settings.image_paint.canvas != image and image.users == 1) or
        image.users == 0):
        bpy.data.images.remove(image)

def simple_remove_node(tree, node, remove_data=True, passthrough_links=False):
    #if not node: return
    scene = bpy.context.scene

    # Reconneect links if input and output has same name
    if passthrough_links:
        for inp in node.inputs:
            if len(inp.links) == 0: continue
            outp = node.outputs.get(inp.name)
            if not outp: continue
            for link in outp.links:
                tree.links.new(inp.links[0].from_socket, link.to_socket)

    if remove_data:
        if node.bl_idname == 'ShaderNodeTexImage':
            image = node.image
            if image: safe_remove_image(image)

        elif node.bl_idname == 'ShaderNodeGroup':
            if node.node_tree and node.node_tree.users == 1:

                # Recursive remove
                for n in node.node_tree.nodes:
                    if n.bl_idname in {'ShaderNodeTexImage', 'ShaderNodeGroup'}:
                        simple_remove_node(node.node_tree, n, remove_data)

                bpy.data.node_groups.remove(node.node_tree)

            #remove_tree_data_recursive(node)

    tree.nodes.remove(node)

def is_vcol_being_used(tree, vcol_name, exception_node=None):
    for node in tree.nodes:
        if node.type == 'VERTEX_COLOR' and node.layer_name == vcol_name and node != exception_node:
            return True
        elif node.type == 'ATTRIBUTE' and node.attribute_name == vcol_name and node != exception_node:
            return True
        elif node.type == 'GROUP' and is_vcol_being_used(node.node_tree, vcol_name, exception_node):
            return True

    return False

def remove_node(tree, entity, prop, remove_data=True, parent=None):
    if not hasattr(entity, prop): return
    if not tree: return
    #if prop not in entity: return


    scene = bpy.context.scene
    node = tree.nodes.get(getattr(entity, prop))
    #node = tree.nodes.get(entity[prop])

    if node: 

        if parent and node.parent != parent:
            setattr(entity, prop, '')
            return

        if remove_data:
            # Remove image data if the node is the only user
            if node.bl_idname == 'ShaderNodeTexImage':

                image = node.image
                if image: safe_remove_image(image)

            elif node.bl_idname == 'ShaderNodeGroup':

                if node.node_tree and node.node_tree.users == 1:
                    remove_tree_inside_tree(node.node_tree)
                    bpy.data.node_groups.remove(node.node_tree)

            elif hasattr(entity, 'type') and entity.type == 'VCOL' and node.bl_idname == get_vcol_bl_idname():
                
                mat = get_active_material()
                objs = get_all_objects_with_same_materials(mat)

                for obj in objs:
                    if obj.type != 'MESH': continue

                    mat = obj.active_material
                    vcol_name = get_source_vcol_name(node)
                    vcols = get_vertex_colors(obj)
                    vcol = vcols.get(vcol_name)

                    if vcol:

                        # Check if vcol is being used somewhere else
                        obs = get_all_objects_with_same_materials(mat, True)
                        for o in obs:
                            other_users_found = False
                            for m in o.data.materials:
                                if m.node_tree and is_vcol_being_used(m.node_tree, vcol_name, node):
                                    other_users_found = True
                                    break
                            if not other_users_found:
                                vc = vcols.get(vcol_name)
                                if vc: vcols.remove(vc)

        # Remove the node itself
        #print('Node ' + prop + ' from ' + str(entity) + ' removed!')
        tree.nodes.remove(node)

    setattr(entity, prop, '')
    #entity[prop] = ''

def create_essential_nodes(tree, solid_value=False, texcoord=False, geometry=False):

    # Start
    node = tree.nodes.new('NodeGroupInput')
    node.name = TREE_START
    node.label = 'Start'

    # End
    node = tree.nodes.new('NodeGroupOutput')
    node.name = TREE_END
    node.label = 'End'

    # Create solid value node
    if solid_value:
        node = tree.nodes.new('ShaderNodeValue')
        node.name = ONE_VALUE
        node.label = 'One Value'
        node.outputs[0].default_value = 1.0

        node = tree.nodes.new('ShaderNodeValue')
        node.name = ZERO_VALUE
        node.label = 'Zero Value'
        node.outputs[0].default_value = 0.0

    if geometry:
        node = tree.nodes.new('ShaderNodeNewGeometry')
        node.name = GEOMETRY

    if texcoord:
        node = tree.nodes.new('ShaderNodeTexCoord')
        node.name = TEXCOORD

def get_active_mat_output_node(tree):
    # Search for output
    for node in tree.nodes:
        if node.bl_idname == 'ShaderNodeOutputMaterial' and node.is_active_output:
            return node

    return None

def get_all_image_users(image):
    users = []

    # Materials
    for mat in bpy.data.materials:
        if mat.node_tree:
            for node in mat.node_tree.nodes:
                if node.type == 'TEX_IMAGE' and node.image == image:
                    users.append(node)

    # Node groups
    for ng in bpy.data.node_groups:
        for node in ng.nodes:
            if node.type == 'TEX_IMAGE' and node.image == image:
                users.append(node)

    # Textures
    for tex in bpy.data.textures:
        if tex.type == 'IMAGE' and tex.image == image:
            users.append(tex)

    return users

def get_layer_ids_with_specific_image(yp, image):

    ids = []

    for i, layer in enumerate(yp.layers):
        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            if source.image and source.image == image:
                ids.append(i)

    return ids

def get_entities_with_specific_image(yp, image):

    entities = []

    layer_ids = get_layer_ids_with_specific_image(yp, image)
    for li in layer_ids:
        layer = yp.layers[li]
        entities.append(layer)

    for layer in yp.layers:
        masks = get_masks_with_specific_image(layer, image)
        entities.extend(masks)

    return entities

def get_layer_ids_with_specific_segment(yp, segment):

    ids = []

    for i, layer in enumerate(yp.layers):
        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            if not source or not source.image: continue
            image = source.image
            if ((image.yia.is_image_atlas and any([s for s in image.yia.segments if s == segment]) and segment.name == layer.segment_name) or
                (image.yua.is_udim_atlas and any([s for s in image.yua.segments if s == segment]) and segment.name == layer.segment_name)
                ):
                ids.append(i)

    return ids

def get_masks_with_specific_image(layer, image):
    masks = []

    for m in layer.masks:
        if m.type == 'IMAGE':
            source = get_mask_source(m)
            if source.image and source.image == image:
                masks.append(m)

    return masks

def get_masks_with_specific_segment(layer, segment):
    masks = []

    for m in layer.masks:
        if m.type == 'IMAGE':
            source = get_mask_source(m)
            if not source or not source.image: continue
            image = source.image
            if ((image.yia.is_image_atlas and any([s for s in image.yia.segments if s == segment]) and segment.name == m.segment_name) or
                (image.yua.is_udim_atlas and any([s for s in image.yua.segments if s == segment]) and segment.name == m.segment_name)
                ):
                masks.append(m)

    return masks

def replace_image(old_image, new_image, yp=None, uv_name = ''):

    if old_image == new_image: return

    # Rename
    if not new_image.yia.is_image_atlas:
        old_name = old_image.name
        old_image.name = '_____temp'
        new_image.name = old_name

        # Set filepath
        if new_image.filepath == '' and old_image.filepath != '' and not old_image.packed_file:
            new_image.filepath = old_image.filepath

    # Check entities using old image
    entities = []
    if yp:
        entities = get_entities_with_specific_image(yp, old_image)

    # Replace all users
    users = get_all_image_users(old_image)
    for user in users:
        #print(user)
        user.image = new_image

    # Replace uv_map of layers and masks
    if yp and uv_name != '':

        # Disable temp uv update
        #ypui = bpy.context.window_manager.ypui
        #ori_disable_temp_uv = ypui.disable_auto_temp_uv_update

        for entity in entities:
            if entity.type == 'IMAGE':
                source = get_entity_source(entity)
                if entity.uv_name != uv_name:
                    entity.uv_name = uv_name

        # Recover temp uv update
        #ypui.disable_auto_temp_uv_update = ori_disable_temp_uv

    # Remove old image
    bpy.data.images.remove(old_image)

    return entities

def mute_node(tree, entity, prop):
    if not hasattr(entity, prop): return
    node = tree.nodes.get(getattr(entity, prop))
    if node: node.mute = True

def unmute_node(tree, entity, prop):
    if not hasattr(entity, prop): return
    node = tree.nodes.get(getattr(entity, prop))
    if node: node.mute = False

def set_default_value(node, input_name_or_index, value):

    # HACK: Sometimes Blender bug will cause node with no inputs
    # So try to reload the group again
    # Tested on Blender 3.6.2
    counter = 0
    while node.type == 'GROUP' and len(node.inputs) == 0 and counter < 64:
        print("HACK: Trying to set group '" + node.node_tree.name + "' again!")
        tree_name = node.node_tree.name
        node.node_tree = bpy.data.node_groups.get(tree_name)
        counter += 1

    inp = None

    if type(input_name_or_index) == int:
        if input_name_or_index < len(node.inputs):
            inp = node.inputs[input_name_or_index]
    else: inp = node.inputs.get(input_name_or_index)

    if inp: inp.default_value = value
    else: 
        debug_name = node.node_tree.name if node.type == 'GROUP' and node.node_tree else node.name
        print("WARNING: Input '" + str(input_name_or_index) + "' in '" + debug_name + "' is not found!")

def new_node(tree, entity, prop, node_id_name, label=''):
    ''' Create new node '''
    if not hasattr(entity, prop): return
    
    # Create new node
    node = tree.nodes.new(node_id_name)

    # Set node name to object attribute
    setattr(entity, prop, node.name)

    # Set label
    node.label = label

    return node

def check_new_node(tree, entity, prop, node_id_name, label='', return_dirty=False):
    ''' Check if node is available, if not, create one '''

    dirty = False

    # Try to get the node first
    try: node = tree.nodes.get(getattr(entity, prop))
    except: 
        if return_dirty:
            return None, dirty
        return None

    # Create new node if not found
    if not node:
        node = new_node(tree, entity, prop, node_id_name, label)
        dirty = True

    if return_dirty:
        return node, dirty

    return node

def create_info_nodes(tree):
    yp = tree.yp
    nodes = tree.nodes

    if yp.is_ypaint_node:
        tree_type = 'ROOT'
    elif yp.is_ypaint_layer_node:
        tree_type = 'LAYER'
    else: tree_type = 'LIB'

    # Delete previous info nodes
    for node in nodes:
        if node.name.startswith(INFO_PREFIX):
            nodes.remove(node)

    # Create info nodes
    infos = []

    info = nodes.new('NodeFrame')

    if tree_type == 'LAYER':
        info.label = 'Part of ' + get_addon_title() + ' addon version ' + yp.version
        info.width = 390.0
    elif tree_type == 'ROOT':
        info.label = 'Created using ' + get_addon_title() + ' addon version ' + yp.version
        info.width = 460.0
    else:
        info.label = 'Part of ' + get_addon_title() + ' addon'
        info.width = 250.0

    info.use_custom_color = True
    info.color = (0.5, 0.5, 0.5)
    info.height = 60.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'Get the addon from github.com/ucupumar/ucupaint'
    info.use_custom_color = True
    info.color = (0.5, 0.5, 0.5)
    info.width = 520.0
    info.height = 60.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'WARNING: Do NOT edit this group manually!'
    info.use_custom_color = True
    info.color = (1.0, 0.5, 0.5)
    info.width = 450.0
    info.height = 60.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'Please use this panel: Node Editor > Properties > ' + get_addon_title()
    #info.label = 'Please use this panel: Node Editor > Tools > Misc'
    info.use_custom_color = True
    info.color = (1.0, 0.5, 0.5)
    info.width = 580.0
    info.height = 60.0
    infos.append(info)

    if tree_type in {'LAYER', 'ROOT'}:

        loc = Vector((0, 70))

        for info in reversed(infos):
            info.name = INFO_PREFIX + info.name

            loc.y += 80
            info.location = loc
    else:

        # Get group input node
        try: 
            inp = [n for n in nodes if n.type == 'GROUP_INPUT'][0]
            loc = Vector((inp.location[0] - 620, inp.location[1]))
        except: loc = Vector((-620, 0))

        for info in infos:
            info.name = INFO_PREFIX + info.name

            loc.y -= 40
            info.location = loc

def check_duplicated_node_group(node_group, duplicated_trees = []):

    info_frame_found = False

    for node in node_group.nodes:

        # Check if info frame is found in this tree
        if node.type == 'FRAME' and node.name.startswith(INFO_PREFIX):
            info_frame_found = True

        if node.type == 'GROUP' and node.node_tree:

            # Check if its node tree duplicated
            m = re.match(r'^(.+)\.\d{3}$', node.node_tree.name)
            if m:
                ng = bpy.data.node_groups.get(m.group(1))
                if ng:
                    #print(node.name, node.node_tree.name, ng.name)
                    #print('p:', node_group.name, 'm:', m.group(1), 'name:', node.node_tree.name)

                    # Remember current tree
                    prev_tree = node.node_tree

                    # Replace new node
                    node.node_tree = ng

                    if prev_tree not in duplicated_trees:
                        duplicated_trees.append(prev_tree)

                    # Remove previous tree
                    #if prev_tree.users == 0:
                    #    #print(node_group.name + ' -> ' + prev_tree.name + ' removed!')
                    #    bpy.data.node_groups.remove(prev_tree)

            check_duplicated_node_group(node.node_tree, duplicated_trees)

    # Create info frame if not found
    if not info_frame_found:
        create_info_nodes(node_group)

def get_node_tree_lib(name):

    # Try to get from local lib first
    node_tree = bpy.data.node_groups.get(name)
    if node_tree: return node_tree

    # Node groups necessary are in nodegroups_lib.blend
    filepath = get_addon_filepath() + "lib.blend"

    #appended = False
    with bpy.data.libraries.load(filepath) as (data_from, data_to):

        # Load node groups
        exist_groups = [ng.name for ng in bpy.data.node_groups]
        from_ngs = data_from.node_groups if hasattr(data_from, 'node_groups') else getattr(data_from, 'node groups')
        to_ngs = data_to.node_groups if hasattr(data_to, 'node_groups') else getattr(data_to, 'node groups')
        for ng in from_ngs:
            if ng == name: # and ng not in exist_groups:
                to_ngs.append(ng)
                #appended = True
                break

    node_tree = bpy.data.node_groups.get(name)

    # Check if another group is exists inside the group
    if node_tree: # and appended:
        duplicated_trees = []
        check_duplicated_node_group(node_tree, duplicated_trees)

        #print('dub', duplicated_trees)

        # Remove duplicated trees
        for t in duplicated_trees:
            bpy.data.node_groups.remove(t)
        #print(duplicated_trees)
        #print(node_tree.name + ' is loaded!')

    return node_tree

def remove_tree_inside_tree(tree):
    for node in tree.nodes:
        if node.type == 'GROUP':
            if node.node_tree and node.node_tree.users == 1:
                remove_tree_inside_tree(node.node_tree)
                bpy.data.node_groups.remove(node.node_tree)
            else: node.node_tree = None

def simple_replace_new_node(tree, node_name, node_id_name, label='', group_name='', return_status=False, hard_replace=False, dirty=False):
    ''' Check if node is available, replace if available '''

    # Try to get the node first
    node = tree.nodes.get(node_name)

    # Remove node if found and has different id name
    if node and node.bl_idname != node_id_name:
        simple_remove_node(tree, node)
        node = None
        dirty = True

    # Create new node
    if not node:
        node = tree.nodes.new(node_id_name)
        node.name = node_name
        node.label = label
        dirty = True

    if node.type == 'GROUP':

        # Get previous tree
        prev_tree = node.node_tree

        # Check if group is copied
        if prev_tree:
            m = re.match(r'^' + group_name + '_Copy\.*\d{0,3}$', prev_tree.name)
        else: m = None

        #print(prev_tree)

        if not prev_tree or (prev_tree.name != group_name and not m):

            if hard_replace:
                tree.nodes.remove(node)
                node = tree.nodes.new(node_id_name)
                node.name = node_name
                node.label = label
                dirty = True

            # Replace group tree
            node.node_tree = get_node_tree_lib(group_name)

            if not prev_tree:
                dirty = True

            else:
                # Compare previous group inputs with current group inputs
                if len(get_tree_inputs(prev_tree)) != len(node.inputs):
                    dirty = True
                else:
                    for i, inp in enumerate(node.inputs):
                        if inp.name != get_tree_inputs(prev_tree)[i].name:
                            dirty = True
                            break

                # Remove previous tree if it has no user
                if prev_tree.users == 0:
                    remove_tree_inside_tree(prev_tree)
                    bpy.data.node_groups.remove(prev_tree)

    if return_status:
        return node, dirty

    return node

def replace_new_node(tree, entity, prop, node_id_name, label='', group_name='', return_status=False, hard_replace=False, dirty=False, force_replace=False):
    ''' Check if node is available, replace if available '''

    # Try to get the node first
    try: node = tree.nodes.get(getattr(entity, prop))
    except: return None, False

    #dirty = False

    # Remove node if found and has different id name
    if node and node.bl_idname != node_id_name:
        remove_node(tree, entity, prop)
        node = None
        dirty = True

    # Create new node
    if not node:
        node = new_node(tree, entity, prop, node_id_name, label)
        dirty = True

    if node.type == 'GROUP':

        # Get previous tree
        prev_tree = node.node_tree

        # Check if group is copied
        if prev_tree:
            m = re.match(r'^' + group_name + '_Copy\.*\d{0,3}$', prev_tree.name)
        else: m = None

        #print(prev_tree)

        if not prev_tree or force_replace or (prev_tree.name != group_name and not m):

            if hard_replace or force_replace:
                tree.nodes.remove(node)
                node = new_node(tree, entity, prop, node_id_name, label)
                dirty = True

            # Replace group tree
            node.node_tree = get_node_tree_lib(group_name)

            if not prev_tree:
                dirty = True

            else:
                # Compare previous group inputs with current group inputs
                if len(get_tree_inputs(prev_tree)) != len(node.inputs):
                    dirty = True
                else:
                    for i, inp in enumerate(node.inputs):
                        if inp.name != get_tree_inputs(prev_tree)[i].name:
                            dirty = True
                            break

                # Remove previous tree if it has no user
                if prev_tree.users == 0:
                    remove_tree_inside_tree(prev_tree)
                    bpy.data.node_groups.remove(prev_tree)

    if return_status:
        return node, dirty

    return node

def get_tree(entity):

    #m = re.match(r'yp\.layers\[(\d+)\]', entity.path_from_id())
    #if not m: return None
    #if not hasattr(entity.id_data, 'yp') or not hasattr(entity, 'group_node'): return None

    #try:

    # Search inside yp tree
    tree = entity.id_data
    yp = tree.yp
    group_node = None

    if entity.trash_group_node != '':
        trash = tree.nodes.get(yp.trash)
        if trash: group_node = trash.node_tree.nodes.get(entity.trash_group_node)
    else:
        group_node = tree.nodes.get(entity.group_node)

    if not group_node or group_node.type != 'GROUP': return None
    return group_node.node_tree

    #except: 
    #    return None

def get_mod_tree(entity):

    yp = entity.id_data.yp

    m = re.match(r'^yp\.channels\[(\d+)\].*', entity.path_from_id())
    if m:
        return entity.id_data

    m = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\].*', entity.path_from_id())
    if m:
        layer = yp.layers[int(m.group(1))]
        ch = layer.channels[int(m.group(2))]
        tree = get_tree(layer)

        mod_group = tree.nodes.get(ch.mod_group)
        if mod_group and mod_group.type == 'GROUP':
            return mod_group.node_tree

        return tree

    m = re.match(r'^yp\.layers\[(\d+)\].*', entity.path_from_id())
    if m:
        layer = yp.layers[int(m.group(1))]
        tree = get_tree(layer)

        source_group = tree.nodes.get(layer.source_group)
        if source_group and source_group.type == 'GROUP': 
            tree = source_group.node_tree

        mod_group = tree.nodes.get(layer.mod_group)
        if mod_group and mod_group.type == 'GROUP':
            return mod_group.node_tree

        return tree

def get_mask_tree(mask, ignore_group=False):

    m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
    if not m : return None

    yp = mask.id_data.yp
    layer = yp.layers[int(m.group(1))]
    layer_tree = get_tree(layer)

    if ignore_group:
        return layer_tree

    if layer_tree:
        group_node = layer_tree.nodes.get(mask.group_node)
    else: return None

    if not group_node or group_node.type != 'GROUP': return layer_tree
    return group_node.node_tree

def get_mask_source(mask):
    tree = get_mask_tree(mask)
    if tree:
        return tree.nodes.get(mask.source)
    return None

def get_mask_mapping(mask):
    tree = get_mask_tree(mask, True)
    return tree.nodes.get(mask.mapping)

def get_channel_source_tree(ch, layer=None, tree=None):
    yp = ch.id_data.yp

    if not layer:
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
        if not m : return None
        layer = yp.layers[int(m.group(1))]

    if not tree: tree = get_tree(layer)
    if not tree: return None

    if ch.source_group != '':
        source_group = tree.nodes.get(ch.source_group)
        return source_group.node_tree

    return tree

def get_channel_source(ch, layer=None, tree=None):
    #if not layer:
    #    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
    #    if not m : return None
    #    layer = yp.layers[int(m.group(1))]

    #if not tree: tree = get_tree(layer)

    source_tree = get_channel_source_tree(ch, layer, tree)
    if source_tree: return source_tree.nodes.get(ch.source)
    #if tree: return tree.nodes.get(ch.source)

    return None

def get_channel_source_1(ch, layer=None, tree=None):
    yp = ch.id_data.yp
    if not layer:
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
        if not m : return None
        layer = yp.layers[int(m.group(1))]

    if not tree: tree = get_tree(layer)
    if tree: return tree.nodes.get(ch.source_1)

    #source_tree = get_channel_source_tree(ch, layer, tree)
    #if source_tree: return source_tree.nodes.get(ch.source)
    #if tree: return tree.nodes.get(ch.source)

    return None

def get_source_tree(layer, tree=None):
    if not tree: tree = get_tree(layer)
    if not tree: return None

    if layer.source_group != '':
        source_group = tree.nodes.get(layer.source_group)
        return source_group.node_tree

    return tree

def get_layer_source(layer, tree=None):
    if not tree: tree = get_tree(layer)

    source_tree = get_source_tree(layer, tree)
    if source_tree: return source_tree.nodes.get(layer.source)
    if tree: return tree.nodes.get(layer.source)

    return None

def get_layer_mapping(layer):
    #tree = get_source_tree(layer)
    tree = get_tree(layer)
    return tree.nodes.get(layer.mapping)

def get_entity_source(entity):

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: return get_layer_source(entity)
    elif m2: return get_mask_source(entity)

    return None

def get_entity_mapping(entity):

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: return get_layer_mapping(entity)
    elif m2: return get_mask_mapping(entity)

    return None

def get_neighbor_uv_space_input(texcoord_type):
    if texcoord_type == 'UV':
        return 0.0 # Tangent Space
    if texcoord_type in {'Generated', 'Normal', 'Object'}:
        return 1.0 # Object Space
    if texcoord_type in {'Camera', 'Window', 'Reflection'}: 
        return 2.0 # View Space

def change_vcol_name(yp, obj, src, new_name, layer=None):

    # Get vertex color from node
    ori_name = get_source_vcol_name(src)
    vcols = get_vertex_colors(obj)
    vcol = vcols.get(get_source_vcol_name(src))

    if layer:
        # Temporarily change its name to temp name so it won't affect unique name
        vcol.name = '___TEMP___'

        # Get unique name
        layer.name = get_unique_name(new_name, vcols) 
        new_name = layer.name

    # Set vertex color name and attribute node
    vcol.name = new_name
    set_source_vcol_name(src, new_name)

    # Replace vertex color name on other objects too
    objs = get_all_objects_with_same_materials(obj.active_material, True)
    for o in objs:
        if o != obj:
            ovcols = get_vertex_colors(o)
            other_v = ovcols.get(ori_name)
            if other_v: other_v.name = new_name

    # Also replace vertex color name on another entity
    for l in yp.layers:

        if l.type == 'VCOL':
            lsrc = get_layer_source(l)
            vname = get_source_vcol_name(lsrc)
            if ori_name == vname:
                ori_halt_update = yp.halt_update
                yp.halt_update = True
                l.name = new_name
                yp.halt_update = ori_halt_update
                set_source_vcol_name(lsrc, new_name)

        for m in l.masks:
            if m.type == 'VCOL':
                msrc = get_mask_source(m)
                vname = get_source_vcol_name(msrc)
                if ori_name == vname:
                    ori_halt_update = yp.halt_update
                    yp.halt_update = True
                    m.name = new_name
                    yp.halt_update = ori_halt_update
                    set_source_vcol_name(msrc, new_name)

        for c in l.channels:
            if c.override and c.override_type == 'VCOL':
                csrc = get_channel_source(c)
                vname = get_source_vcol_name(csrc)
                if ori_name == vname:
                    set_source_vcol_name(csrc, new_name)

def change_layer_name(yp, obj, src, layer, texes):
    if yp.halt_update: return

    yp.halt_update = True

    if layer.type == 'VCOL' and obj.type == 'MESH':

        change_vcol_name(yp, obj, src, layer.name, layer)
        
    elif layer.type == 'IMAGE':
        src.image.name = '___TEMP___'
        layer.name = get_unique_name(layer.name, bpy.data.images) 
        src.image.name = layer.name

    else:
        name = layer.name
        layer.name = '___TEMP___'
        layer.name = get_unique_name(name, texes) 

    # Update node group label
    m1 = re.match(r'^yp\.layers\[(\d+)\]$', layer.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', layer.path_from_id())
    if m1:
        group_tree = yp.id_data
        layer_group = group_tree.nodes.get(layer.group_node)
        layer_group.label = layer.name

    yp.halt_update = False

def set_obj_vertex_colors(obj, vcol_name, color):
    if obj.type != 'MESH': return

    ori_mode = None
    if obj.mode != 'OBJECT':
        ori_mode = obj.mode
        bpy.ops.object.mode_set(mode='OBJECT')

    vcols = get_vertex_colors(obj)
    vcol = vcols.get(vcol_name)
    if not vcol: return

    ones = numpy.ones(len(vcol.data))

    if is_greater_than_280():
        vcol.data.foreach_set( "color",
            numpy.array((color[0] * ones, color[1] * ones, color[2] * ones, color[3] * ones)).T.ravel())
    else:
        vcol.data.foreach_set( "color",
            numpy.array((color[0] * ones, color[1] * ones, color[2] * ones)).T.ravel())

    if ori_mode:
        bpy.ops.object.mode_set(mode=ori_mode)

def force_bump_base_value(tree, ch, value):
    col = (value, value, value, 1.0)

    bump_base = tree.nodes.get(ch.bump_base)
    if bump_base: bump_base.inputs[1].default_value = col

    neighbor_directions = ['n', 's', 'e', 'w']
    for d in neighbor_directions:
        b = tree.nodes.get(getattr(ch, 'bump_base_' + d))
        if b: b.inputs[1].default_value = col

    #for mod in ch.modifiers:
    #    if mod.type == 'OVERRIDE_COLOR' and mod.oc_use_normal_base:
    #        mod.oc_col = col

def update_bump_base_value_(tree, ch):
    force_bump_base_value(tree, ch, ch.bump_base_value)
    
def get_transition_bump_channel(layer):
    yp = layer.id_data.yp

    bump_ch = None
    for i, ch in enumerate(layer.channels):
        if yp.channels[i].type == 'NORMAL' and ch.enable and ch.enable_transition_bump:
            bump_ch = ch
            break

    return bump_ch

def get_showed_transition_bump_channel(layer):

    yp = layer.id_data.yp

    bump_ch = None
    for i, ch in enumerate(layer.channels):
        if yp.channels[i].type == 'NORMAL' and ch.show_transition_bump:
            bump_ch = ch
            break

    return bump_ch

# BLENDER_28_GROUP_INPUT_HACK
def duplicate_lib_node_tree(node): #, duplicate_group_inside=False):
    node.node_tree.name += '_Copy'
    if node.node_tree.users > 1:
        node.node_tree = node.node_tree.copy()

    #if duplicate_group_inside:
    #    for n in node.node_tree.nodes:
    #        if n.type == 'GROUP':
    #            duplicate_lib_node_tree(n, True)

    # Make sure input match to actual node its connected to
    #for n in node.node_tree.nodes:
    #    if n.type == 'GROUP_INPUT':
    #        for i, inp in enumerate(node.inputs):
    #            for link in n.outputs[i].links:
    #                try: link.to_socket.default_value = node.inputs[i].default_value
    #                except: pass

def match_group_input(node, key=None, extra_node_names=[]):

    input_node_names = ['Group Input']
    input_node_names.extend(extra_node_names)

    for name in input_node_names:
        try:
            n = node.node_tree.nodes.get(name)
            if not key: outputs = n.outputs
            else: outputs = [n.outputs[key]]
        except: continue

        for outp in outputs:
            for link in outp.links:
                try: 
                    if link.to_socket.default_value != node.inputs[outp.name].default_value:
                        link.to_socket.default_value = node.inputs[outp.name].default_value
                except: pass

def get_tree_inputs(tree):
    if not is_greater_than_400():
        return tree.inputs

    return [ui for ui in tree.interface.items_tree if ui.in_out in {'INPUT', 'BOTH'}]

def get_tree_outputs(tree):
    if not is_greater_than_400():
        return tree.outputs

    return [ui for ui in tree.interface.items_tree if ui.in_out in {'OUTPUT', 'BOTH'}]

def get_tree_input_by_name(tree, name):
    if not is_greater_than_400():
        return tree.inputs.get(name)

    inp = [ui for ui in tree.interface.items_tree if ui.name == name and ui.in_out in {'INPUT', 'BOTH'}]
    if inp: return inp[0]

    return None

def get_tree_output_by_name(tree, name):
    if not is_greater_than_400():
        return tree.outputs.get(name)

    outp = [ui for ui in tree.interface.items_tree if ui.name == name and ui.in_out in {'OUTPUT', 'BOTH'}]
    if outp: return outp[0]

    return None

def new_tree_input(tree, name, socket_type, description='', use_both=False):
    if not is_greater_than_400():
        return tree.inputs.new(socket_type, name)

    # There's no longer NodeSocketFloatFactor
    subtype = 'NONE'
    if socket_type == 'NodeSocketFloatFactor': 
        socket_type = 'NodeSocketFloat'
        subtype = 'FACTOR'

    inp = None

    # NOTE: Used to be working on Blender 4.0 Alpha, 'BOTH' in_out is no longer supported
    # Keep the code just in case it will work again someday
    if use_both and False:
        # Check if output with same name already exists
        items = [it for it in tree.interface.items_tree if it.name == name and it.socket_type == socket_type and it.in_out == 'OUTPUT']
        if items:
            inp = items[0]
            inp.in_out = 'BOTH'

    if not inp: 
        inp =  tree.interface.new_socket(name, description=description, in_out='INPUT', socket_type=socket_type)

    if hasattr(inp, 'subtype'): inp.subtype = subtype
    return inp

def new_tree_output(tree, name, socket_type, description='', use_both=False):
    if not is_greater_than_400():
        return tree.outputs.new(socket_type, name)

    # There's no longer NodeSocketFloatFactor
    if socket_type == 'NodeSocketFloatFactor': socket_type = 'NodeSocketFloat'

    outp = None

    # NOTE: Used to be working on Blender 4.0 Alpha, 'BOTH' in_out is no longer supported
    # Keep the code just in case it will work again someday
    if use_both and False:
        # Check if input with same name already exists
        items = [it for it in tree.interface.items_tree if it.name == name and it.socket_type == socket_type and it.in_out == 'INPUT']
        if items:
            outp = items[0]
            outp.in_out = 'BOTH'

    if not outp: 
        outp = tree.interface.new_socket(name, description=description, in_out='OUTPUT', socket_type=socket_type)

    return outp

def remove_tree_input(tree, item):
    if not is_greater_than_400():
        tree.inputs.remove(item)
        return

    if item.in_out == 'BOTH':
        item.in_out = 'OUTPUT'
    elif item.in_out == 'INPUT':
        tree.interface.remove(item)

def remove_tree_output(tree, item):
    if not is_greater_than_400():
        tree.outputs.remove(item)
        return

    if item.in_out == 'BOTH':
        item.in_out = 'INPUT'
    elif item.in_out == 'OUTPUT':
        tree.interface.remove(item)

def get_tree_input_by_index(tree, index):
    if not is_greater_than_400():
        return tree.inputs[index]

    i = -1
    for item in tree.interface.items_tree:
        if item.in_out in {'INPUT', 'BOTH'}:
            i += 1

        if i == index:
            return item

    return None

def get_tree_output_by_index(tree, index):
    if not is_greater_than_400():
        return tree.outputs[index]

    i = -1
    for item in tree.interface.items_tree:
        if item.in_out in {'OUTPUT', 'BOTH'}:
            i += 1

        if i == index:
            return item

    return None

def get_output_index(root_ch):
    yp = root_ch.id_data.yp

    output_index = root_ch.io_index

    # Check if there's normal channel above current channel because it has extra output
    for ch in yp.channels:
        if ch.type == 'NORMAL' and ch != root_ch:
            output_index += 1
        if ch == root_ch:
            break

    return output_index

def get_layer_depth(layer):

    yp = layer.id_data.yp

    upmost_found = False
    depth = 0
    cur = layer
    parent = layer

    while True:
        if cur.parent_idx != -1:

            try: layer = yp.layers[cur.parent_idx]
            except: break

            if layer.type == 'GROUP':
                parent = layer
                depth += 1

        if parent == cur:
            break

        cur = parent

    return depth

def is_top_member(layer, enabled_only=False):
    
    if layer.parent_idx == -1:
        return False

    yp = layer.id_data.yp

    for i, t in enumerate(yp.layers):
        if enabled_only and not t.enable: continue
        if t == layer:
            if layer.parent_idx == i-1:
                return True
            else: return False

    return False

def is_bottom_member(layer, enabled_only=False):

    if layer.parent_idx == -1:
        return False

    yp = layer.id_data.yp

    layer_idx = -1
    last_member_idx = -1
    for i, t in enumerate(yp.layers):
        if enabled_only and not t.enable: continue
        if t == layer:
            layer_idx = i
        if t.parent_idx == layer.parent_idx:
            last_member_idx = i

    if layer_idx == last_member_idx:
        return True

    return False

#def get_upmost_parent_idx(layer, idx_limit = -1):
#
#    yp = layer.id_data.yp
#
#    cur = layer
#    parent = layer
#    parent_idx = -1
#
#    while True:
#        if cur.parent_idx != -1 and cur.parent_idx != idx_limit:
#
#            try: layer = yp.layers[cur.parent_idx]
#            except: break
#
#            if layer.type == 'GROUP':
#                parent = layer
#                parent_idx = cur.parent_idx
#
#        if parent == cur:
#            break
#
#        cur = parent
#
#    return parent_idx

def get_layer_index(layer):
    yp = layer.id_data.yp

    for i, t in enumerate(yp.layers):
        if layer == t:
            return i

def get_layer_index_by_name(yp, name):

    for i, t in enumerate(yp.layers):
        if name == t.name:
            return i

    return -1

def get_parent_dict(yp):
    parent_dict = {}
    for t in yp.layers:
        if t.parent_idx != -1:
            try: parent_dict[t.name] = yp.layers[t.parent_idx].name
            except: parent_dict[t.name] = None
        else: parent_dict[t.name] = None

    return parent_dict

def get_index_dict(yp):
    index_dict = {}
    for i, t in enumerate(yp.layers):
        index_dict[t.name] = i

    return index_dict

def get_parent(layer):

    yp = layer.id_data.yp
    
    if layer.parent_idx == -1:
        return None

    return yp.layers[layer.parent_idx]

def is_parent_hidden(layer):

    yp = layer.id_data.yp

    hidden = False
    
    cur = layer
    parent = layer

    while True:
        if cur.parent_idx != -1:

            try: layer = yp.layers[cur.parent_idx]
            except: break

            if layer.type == 'GROUP':
                parent = layer
                if not parent.enable:
                    hidden = True
                    break

        if parent == cur:
            break

        cur = parent

    return hidden

def set_parent_dict_val(yp, parent_dict, name, target_idx):

    if target_idx != -1:
        parent_dict[name] = yp.layers[target_idx].name
    else: parent_dict[name] = None

    return parent_dict

def get_list_of_direct_child_ids(layer):
    yp = layer.id_data.yp

    if layer.type != 'GROUP':
        return []

    layer_idx = get_layer_index(layer)

    childs = []
    for i, t in enumerate(yp.layers):
        if t.parent_idx == layer_idx:
            childs.append(i)

    return childs

def get_list_of_direct_childrens(layer):
    yp = layer.id_data.yp

    if layer.type != 'GROUP':
        return []

    layer_idx = get_layer_index(layer)

    childs = []
    for t in yp.layers:
        if t.parent_idx == layer_idx:
            childs.append(t)

    return childs

def get_list_of_all_childs_and_child_ids(layer):
    yp = layer.id_data.yp

    if layer.type != 'GROUP':
        return [], []

    layer_idx = get_layer_index(layer)

    childs = []
    child_ids = []
    for i, t in enumerate(yp.layers):
        if t.parent_idx == layer_idx or t.parent_idx in child_ids:
            childs.append(t)
            child_ids.append(i)

    return childs, child_ids

def get_list_of_parent_ids(layer):

    yp = layer.id_data.yp

    cur = layer
    parent = layer
    parent_list = []

    while True:
        if cur.parent_idx != -1:

            try: layer = yp.layers[cur.parent_idx]
            except: break

            if layer.type == 'GROUP':
                parent = layer
                parent_list.append(cur.parent_idx)

        if parent == cur:
            break

        cur = parent

    return parent_list

def get_last_chained_up_layer_ids(layer, idx_limit):

    yp = layer.id_data.yp
    layer_idx = get_layer_index(layer)

    cur = layer
    parent = layer
    parent_idx = layer_idx

    while True:
        if cur.parent_idx != -1 and cur.parent_idx != idx_limit:

            try: layer = yp.layers[cur.parent_idx]
            except: break

            if layer.type == 'GROUP':
                parent = layer
                parent_idx = cur.parent_idx

        if parent == cur:
            break

        cur = parent

    return parent_idx

def has_childrens(layer):

    yp = layer.id_data.yp

    if layer.type != 'GROUP':
        return False

    layer_idx = get_layer_index(layer)

    if layer_idx < len(yp.layers)-1:
        neighbor = yp.layers[layer_idx+1]
        if neighbor.parent_idx == layer_idx:
            return True

    return False

def has_channel_childrens(layer, root_ch):

    yp = layer.id_data.yp

    if layer.type != 'GROUP':
        return False

    ch_idx = get_channel_index(root_ch)
    childs = get_list_of_direct_childrens(layer)

    for child in childs:
        if not child.enable: continue
        for i, ch in enumerate(child.channels):
            if i == ch_idx and ch.enable:
                return True

    return False

def has_previous_layer_channels(layer, root_ch):
    yp = layer.id_data.yp

    if layer.parent_idx == -1:
        return True

    ch_idx = get_channel_index(root_ch)
    layer_idx = get_layer_index(layer)

    for i, t in reversed(list(enumerate(yp.layers))):
        if i > layer_idx and layer.parent_idx == t.parent_idx:
            for j, c in enumerate(t.channels):
                if ch_idx == j and c.enable:
                    return True

    return False

def get_last_child_idx(layer): #, very_last=False):

    yp = layer.id_data.yp
    layer_idx = get_layer_index(layer)

    if layer.type != 'GROUP': 
        return layer_idx

    for i, t in reversed(list(enumerate(yp.layers))):
        if i > layer_idx and layer_idx in get_list_of_parent_ids(t):
            return i

    return layer_idx

def get_upper_neighbor(layer):

    yp = layer.id_data.yp
    layer_idx = get_layer_index(layer)

    if layer_idx == 0:
        return None, None

    if layer.parent_idx == layer_idx-1:
        return layer_idx-1, yp.layers[layer_idx-1]

    upper_layer = yp.layers[layer_idx-1]

    neighbor_idx = get_last_chained_up_layer_ids(upper_layer, layer.parent_idx)
    neighbor = yp.layers[neighbor_idx]

    return neighbor_idx, neighbor

def get_lower_neighbor(layer):

    yp = layer.id_data.yp
    layer_idx = get_layer_index(layer)
    last_index = len(yp.layers)-1

    if layer_idx == last_index:
        return None, None

    if layer.type == 'GROUP':
        last_child_idx = get_last_child_idx(layer)

        if last_child_idx == last_index:
            return None, None

        neighbor_idx = last_child_idx + 1
    else:
        neighbor_idx = layer_idx+1

    neighbor = yp.layers[neighbor_idx]

    return neighbor_idx, neighbor

def is_valid_to_remove_bump_nodes(layer, ch):

    if layer.type == 'COLOR' and ((ch.enable_transition_bump and ch.enable) or len(layer.masks) == 0 or ch.transition_bump_chain == 0):
        return True

    return False

def get_correct_uv_neighbor_resolution(ch, image=None):

    res_x = image.size[0] if image else 1000
    res_y = image.size[1] if image else 1000

    res_x /= ch.bump_smooth_multiplier
    res_y /= ch.bump_smooth_multiplier

    return res_x, res_y

def set_uv_neighbor_resolution(entity, uv_neighbor=None, source=None):

    yp = entity.id_data.yp
    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())
    m3 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', entity.path_from_id())

    if m1: 
        layer = yp.layers[int(m1.group(1))]
        tree = get_tree(entity)
        if not source: source = get_layer_source(entity)
        entity_type = entity.type
        scale = entity.scale
    elif m2: 
        layer = yp.layers[int(m2.group(1))]
        tree = get_tree(layer)
        if not source: source = get_mask_source(entity)
        entity_type = entity.type
        scale = entity.scale
    elif m3: 
        layer = yp.layers[int(m3.group(1))]
        tree = get_tree(layer)
        if not source: source = get_channel_source(entity, layer, tree)
        entity_type = entity.override_type
        scale = layer.scale
    else: return

    if not uv_neighbor: uv_neighbor = tree.nodes.get(entity.uv_neighbor)
    if not uv_neighbor: return

    if 'ResX' not in uv_neighbor.inputs: return

    # Get height channel
    height_ch = get_height_channel(layer)
    if not height_ch: return

    # Get Image
    image = source.image if entity_type == 'IMAGE' else None
    
    # Get correct resolution
    res_x, res_y = get_correct_uv_neighbor_resolution(height_ch, image)

    # Set UV Neighbor resolution
    uv_neighbor.inputs['ResX'].default_value = res_x
    uv_neighbor.inputs['ResY'].default_value = res_y

def get_tilenums_height(tilenums):
    min_y = int(min(tilenums) / 10)
    max_y = int(max(tilenums) / 10)

    return max_y - min_y + 1

def get_udim_segment_tiles_height(segment):
    tilenums = [btile.number for btile in segment.base_tiles]
    return get_tilenums_height(tilenums)

def get_udim_segment_mapping_offset(segment):
    image = segment.id_data

    offset_y = 0 
    for i, seg in enumerate(image.yua.segments):
        if seg == segment:
            return offset_y
        tiles_height = get_udim_segment_tiles_height(seg)
        offset_y += tiles_height + 1

def clear_mapping(entity):

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: mapping = get_layer_mapping(entity)
    else: mapping = get_mask_mapping(entity)

    if is_greater_than_281():
        mapping.inputs[1].default_value = (0.0, 0.0, 0.0)
        mapping.inputs[2].default_value = (0.0, 0.0, 0.0)
        mapping.inputs[3].default_value = (1.0, 1.0, 1.0)
    else:
        mapping.translation = (0.0, 0.0, 0.0)
        mapping.rotation = (0.0, 0.0, 0.0)
        mapping.scale = (1.0, 1.0, 1.0)

def update_mapping(entity):

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    # Get source
    if m1: 
        source = get_layer_source(entity)
        mapping = get_layer_mapping(entity)
    elif m2: 
        source = get_mask_source(entity)
        mapping = get_mask_mapping(entity)
    else: return

    if not mapping: return

    yp = entity.id_data.yp

    offset_x = entity.translation[0]
    offset_y = entity.translation[1]
    offset_z = entity.translation[2]

    scale_x = entity.scale[0]
    scale_y = entity.scale[1]
    scale_z = entity.scale[2]

    if entity.type == 'IMAGE' and entity.segment_name != '':
        image = source.image
        if image.source == 'TILED':
            segment = image.yua.segments.get(entity.segment_name)
            offset_y = get_udim_segment_mapping_offset(segment) 
        else:
            segment = image.yia.segments.get(entity.segment_name)

            scale_x = segment.width/image.size[0] * scale_x
            scale_y = segment.height/image.size[1] * scale_y

            offset_x = scale_x * segment.tile_x + offset_x * scale_x
            offset_y = scale_y * segment.tile_y + offset_y * scale_y

    if is_greater_than_281():
        mapping.inputs[1].default_value = (offset_x, offset_y, offset_z)
        mapping.inputs[2].default_value = entity.rotation
        mapping.inputs[3].default_value = (scale_x, scale_y, scale_z)
    else:
        mapping.translation = (offset_x, offset_y, offset_z)
        mapping.rotation = entity.rotation
        mapping.scale = (scale_x, scale_y, scale_z)

    # Setting UV neighbor resolution probably isn't important right now
    #set_uv_neighbor_resolution(entity, source=source, mapping=mapping)

    #if m1: 
    #    for i, ch in enumerate(entity.channels):
    #        root_ch = yp.channels[i]
    #        if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump and ch.enable and ch.override and ch.override_type == 'IMAGE':
    #            set_uv_neighbor_resolution(ch, mapping=mapping)

    if entity.type == 'IMAGE' and entity.texcoord_type == 'UV':
        if m1 or (m2 and entity.active_edit):
            if bpy.context.object and bpy.context.object.mode == 'TEXTURE_PAINT':
                yp.need_temp_uv_refresh = True

def is_active_uv_map_match_entity(obj, entity):

    m = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())

    #if entity.type != 'IMAGE' or entity.texcoord_type != 'UV': return False
    if (m and not is_layer_using_vector(entity)) or entity.texcoord_type != 'UV': return False
    mapping = get_entity_mapping(entity)

    uv_layers = get_uv_layers(obj)
    uv_layer = uv_layers.active

    if mapping and is_transformed(mapping) and obj.mode == 'TEXTURE_PAINT':
        if uv_layer.name != TEMP_UV:
            return True

    elif entity.uv_name in uv_layers and entity.uv_name != uv_layer.name:
        return True

    return False

def is_active_uv_map_match_active_entity(obj, layer):

    active_mask = None
    for mask in layer.masks:
        if mask.active_edit == True:
            active_mask = mask

    if active_mask: entity = active_mask
    else: entity = layer

    return is_active_uv_map_match_entity(obj, entity)

def is_transformed(mapping):
    if is_greater_than_281():
        if (mapping.inputs[1].default_value[0] != 0.0 or
            mapping.inputs[1].default_value[1] != 0.0 or
            mapping.inputs[1].default_value[2] != 0.0 or
            mapping.inputs[2].default_value[0] != 0.0 or
            mapping.inputs[2].default_value[1] != 0.0 or
            mapping.inputs[2].default_value[2] != 0.0 or
            mapping.inputs[3].default_value[0] != 1.0 or
            mapping.inputs[3].default_value[1] != 1.0 or
            mapping.inputs[3].default_value[2] != 1.0
            ):
            return True
        return False
    else:
        if (mapping.translation[0] != 0.0 or
            mapping.translation[1] != 0.0 or
            mapping.translation[2] != 0.0 or
            mapping.rotation[0] != 0.0 or
            mapping.rotation[1] != 0.0 or
            mapping.rotation[2] != 0.0 or
            mapping.scale[0] != 1.0 or
            mapping.scale[1] != 1.0 or
            mapping.scale[2] != 1.0
            ):
            return True
        return False

def check_uvmap_on_other_objects_with_same_mat(mat, uv_name, set_active=True):

    if mat.users > 1 and uv_name != '':
        for ob in get_scene_objects():
            if ob.type != 'MESH': continue
            if mat.name in ob.data.materials:
                uvls = get_uv_layers(ob)
                if uv_name not in uvls:
                    uvl = uvls.new(name=uv_name)
                    if set_active:
                        uvls.active = uvl

def set_uv_mirror_offsets(obj, matrix):

    mirror = get_first_mirror_modifier(obj)
    if not mirror: return

    movec = Vector((mirror.mirror_offset_u/2, mirror.mirror_offset_v/2, 0.0))
    if is_greater_than_280():
        movec = matrix @ movec
    else: movec = matrix * movec

    if mirror.use_mirror_u:
        obj.yp.ori_mirror_offset_u = mirror.mirror_offset_u
        mirror.mirror_offset_u = movec.x * 2 - (1.0 - matrix[0][0])

    if mirror.use_mirror_v:
        obj.yp.ori_mirror_offset_v = mirror.mirror_offset_v
        mirror.mirror_offset_v = movec.y * 2 - (1.0 - matrix[1][1])

    if is_greater_than_280():
        obj.yp.ori_offset_u = mirror.offset_u
        mirror.offset_u *= matrix[0][0]

        obj.yp.ori_offset_v = mirror.offset_v
        mirror.offset_v *= matrix[1][1]

def remove_temp_uv(obj, entity):
    uv_layers = get_uv_layers(obj)
    
    if uv_layers:
        for uv in uv_layers:
            if uv.name == TEMP_UV or uv.name.startswith(TEMP_UV):
                uv_layers.remove(uv)
                #break

    if not entity: return

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if not m1 and not m2:
        return

    # Remove uv mirror offsets for entity with image atlas
    mirror = get_first_mirror_modifier(obj)
    if mirror and entity.type == 'IMAGE'  and (
            entity.segment_name != '' or 
            # Because sometimes you want to tweak mirror offsets in texture paint mode,
            # quitting texture paint while using standard image will not reset mirror offsets
            # But unfortunately, it will still reset if you are changing active layer
            # even if the layer is not using image atlas
            # Better solution will requires storing last active layer
            (entity.segment_name == '' and obj.mode == 'TEXTURE_PAINT')
            ):
        if mirror.use_mirror_u:
            mirror.mirror_offset_u = obj.yp.ori_mirror_offset_u

        if mirror.use_mirror_v:
            mirror.mirror_offset_v = obj.yp.ori_mirror_offset_v

        if is_greater_than_280():
            mirror.offset_u = obj.yp.ori_offset_u
            mirror.offset_v = obj.yp.ori_offset_v

def refresh_temp_uv(obj, entity): 

    if obj.type != 'MESH':
        return False

    if not entity:
        remove_temp_uv(obj, entity)
        return False

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())
    m3 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', entity.path_from_id())

    if m1 or m2 or m3: 

        # Get exact match
        if m1: m = m1
        elif m2: m = m2
        elif m3: m = m3

        # Get layer tree
        yp = entity.id_data.yp
        layer = yp.layers[int(m.group(1))]
        layer_tree = get_tree(layer)

    else: return False

    uv_layers = get_uv_layers(obj)

    if m3:
        layer_uv = uv_layers.get(layer.uv_name)
    else:
        layer_uv = uv_layers.get(entity.uv_name)
        if not layer_uv: 
            return False

    # Set active uv
    if uv_layers.active != layer_uv:
        uv_layers.active = layer_uv
        layer_uv.active_render = True

    if m3 and entity.override_type != 'IMAGE':
        remove_temp_uv(obj, entity)
        return False

    if (m1 or m2) and entity.type != 'IMAGE':
        remove_temp_uv(obj, entity)
        return False

    # Delete previous temp uv
    remove_temp_uv(obj, entity)

    # Only set actual uv if not in texture paint mode
    if obj.mode not in {'TEXTURE_PAINT', 'EDIT'}:
        return False

    #yp.need_temp_uv_refresh = False

    # Get source
    if m1: 
        source = get_layer_source(entity)
        mapping = get_layer_mapping(entity)
        #print('Layer!')
    elif m2: 
        source = get_mask_source(entity)
        mapping = get_mask_mapping(entity)
        #print('Mask!')
    elif m3: 
        source = layer_tree.nodes.get(entity.source)
        mapping = get_layer_mapping(layer)
        #print('Channel!')
    else: return False

    if not hasattr(source, 'image'): return False

    img = source.image
    if not img or not is_transformed(mapping):
        return False

    set_active_object(obj)

    # Cannot do this on edit mode
    ori_mode = obj.mode
    if ori_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # New uv layers
    temp_uv_layer = uv_layers.new(name=TEMP_UV)
    #temp_uv_layer = obj.data.uv_layers.new(name=TEMP_UV)
    uv_layers.active = temp_uv_layer
    temp_uv_layer.active_render = True

    if not is_greater_than_280():
        temp_uv_layer = obj.data.uv_layers.get(TEMP_UV)

    # Create transformation matrix
    # Scale
    if not is_greater_than_281():
        m = Matrix((
            (mapping.scale[0], 0, 0),
            (0, mapping.scale[1], 0),
            (0, 0, mapping.scale[2])
            ))

        # Rotate
        m.rotate(Euler((mapping.rotation[0], mapping.rotation[1], mapping.rotation[2])))

        # Translate
        m = m.to_4x4()
        m[0][3] = mapping.translation[0]
        m[1][3] = mapping.translation[1]
        m[2][3] = mapping.translation[2]
    else:
        m = Matrix((
            (mapping.inputs[3].default_value[0], 0, 0),
            (0, mapping.inputs[3].default_value[1], 0),
            (0, 0, mapping.inputs[3].default_value[2])
            ))

        # Rotate
        m.rotate(Euler((mapping.inputs[2].default_value[0], mapping.inputs[2].default_value[1], mapping.inputs[2].default_value[2])))

        # Translate
        m = m.to_4x4()
        m[0][3] = mapping.inputs[1].default_value[0]
        m[1][3] = mapping.inputs[1].default_value[1]
        m[2][3] = mapping.inputs[1].default_value[2]

    # Create numpy array to store uv coordinates
    arr = numpy.zeros(len(obj.data.loops)*2, dtype=numpy.float32)
    #obj.data.uv_layers.active.data.foreach_get('uv', arr)
    temp_uv_layer.data.foreach_get('uv', arr)
    arr.shape = (arr.shape[0]//2, 2)

    # Matrix transformation for each uv coordinates
    if is_greater_than_280():
        for uv in arr:
            vec = Vector((uv[0], uv[1], 0.0)) #, 1.0))
            vec = m @ vec
            uv[0] = vec[0]
            uv[1] = vec[1]
    else:
        for uv in arr:
            vec = Vector((uv[0], uv[1], 0.0)) #, 1.0))
            vec = m * vec
            uv[0] = vec[0]
            uv[1] = vec[1]

    # Set back uv coordinates
    #obj.data.uv_layers.active.data.foreach_set('uv', arr.ravel())
    temp_uv_layer.data.foreach_set('uv', arr.ravel())

    # Set UV mirror offset
    if ori_mode != 'EDIT':
        set_uv_mirror_offsets(obj, m)

    # Back to edit mode if originally from there
    if ori_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='EDIT')

    return True

def set_bump_backface_flip(node, flip_backface):
    node.mute = False
    if flip_backface:
        node.inputs['Eevee'].default_value = 1.0
        node.inputs['Cycles'].default_value = 1.0
        node.inputs['Blender 2.7 Viewport'].default_value = 0.0
    else:
        node.inputs['Eevee'].default_value = 0.0
        node.inputs['Cycles'].default_value = 0.0
        node.inputs['Blender 2.7 Viewport'].default_value = 1.0

def set_normal_backface_flip(node, flip_backface):
    node.mute = False
    if flip_backface:
        node.inputs['Flip'].default_value = 1.0
    else:
        node.inputs['Flip'].default_value = 0.0

def set_tangent_backface_flip(node, flip_backface):
    node.mute = False
    if flip_backface:
        node.inputs['Eevee'].default_value = 1.0
        node.inputs['Cycles'].default_value = 1.0
        node.inputs['Blender 2.7 Viewport'].default_value = 0.0
    else:
        node.inputs['Eevee'].default_value = 0.0
        node.inputs['Cycles'].default_value = 0.0
        node.inputs['Blender 2.7 Viewport'].default_value = 1.0

def set_bitangent_backface_flip(node, flip_backface):
    if flip_backface:
        node.mute = False
    else:
        node.mute = True

def is_parallax_enabled(root_ch):
    if not root_ch: return False

    yp = root_ch.id_data.yp
    ypup = get_user_preferences()

    parallax_enabled = root_ch.enable_parallax if root_ch.type == 'NORMAL' else False

    if not ypup.parallax_without_baked and not yp.use_baked:
        parallax_enabled = False

    return parallax_enabled

def get_root_parallax_channel(yp):
    for ch in yp.channels:
        if ch.type == 'NORMAL' and is_parallax_enabled(ch):
            return ch

    return None

def get_root_height_channel(yp):
    for ch in yp.channels:
        if ch.type == 'NORMAL':
            return ch

    return None

def get_height_channel(layer):

    yp = layer.id_data.yp

    for i, ch in enumerate(layer.channels):
        root_ch = yp.channels[i]
        if root_ch.type == 'NORMAL':
            return ch

    return None

def match_io_between_node_tree(source, target):

    valid_inputs = []
    valid_outputs = []

    # Copy inputs
    for inp in get_tree_inputs(source):
        #target_inp = target.inputs.get(inp.name)
        target_inp = get_tree_input_by_name(target, inp.name)

        if target_inp and target_inp.bl_socket_idname != inp.bl_socket_idname:
            #target.inputs.remove(target_inp)
            remove_tree_input(target, target_inp)
            target_inp = None

        if not target_inp:
            #target_inp = target.inputs.new(inp.bl_socket_idname, inp.name)
            target_inp = new_tree_input(target, inp.name, inp.bl_socket_idname)
            target_inp.default_value = inp.default_value

        valid_inputs.append(target_inp)

    # Copy outputs
    for outp in get_tree_outputs(source):
        #target_outp = target.outputs.get(outp.name)
        target_outp = get_tree_output_by_name(target, outp.name)

        if target_outp and target_outp.bl_socket_idname != outp.bl_socket_idname:
            #target.outputs.remove(target_outp)
            remove_tree_output(target, target_outp)
            target_outp = None

        if not target_outp:
            #target_outp = target.outputs.new(outp.bl_socket_idname, outp.name)
            target_outp = new_tree_output(target, outp.name, outp.bl_socket_idname)
            target_outp.default_value = outp.default_value

        valid_outputs.append(target_outp)

    # Remove invalid inputs
    for inp in get_tree_inputs(target):
        if inp not in valid_inputs:
            #target.inputs.remove(inp)
            remove_tree_input(target, inp)

    # Remove invalid outputs
    for outp in get_tree_outputs(target):
        if outp not in valid_outputs:
            #target.outputs.remove(outp)
            remove_tree_output(target, outp)

def create_iterate_group_nodes(iter_tree, match_io=False):

    group_tree = bpy.data.node_groups.new(ITERATE_GROUP, 'ShaderNodeTree')
    create_essential_nodes(group_tree)

    for i in range(PARALLAX_DIVIDER):
        it = group_tree.nodes.new('ShaderNodeGroup')
        it.name = '_iterate_' + str(i)
        it.node_tree = iter_tree

    if match_io:
        match_io_between_node_tree(iter_tree, group_tree)

    return group_tree

def calculate_group_needed(num_of_iteration):
    return int(num_of_iteration/PARALLAX_DIVIDER)

def calculate_parallax_group_depth(num_of_iteration):
    #iter_inside = 1
    #depth = 1
    #while True:
    #    divider = iter_inside * PARALLAX_DIVIDER
    #    if (num_of_iteration / divider) < 1.0:
    #        break
    #    depth += 1
    #return depth
    return int(math.log(num_of_iteration, PARALLAX_DIVIDER))

def calculate_parallax_top_level_count(num_of_iteration):
    return int(num_of_iteration / pow(PARALLAX_DIVIDER, calculate_parallax_group_depth(num_of_iteration)))

def create_delete_iterate_nodes__(tree, num_of_iteration):
    iter_tree = tree.nodes.get('_iterate').node_tree

    # Get group depth
    depth = calculate_parallax_group_depth(num_of_iteration)
    #print(depth)

    # Top level group needed
    #top_level_count = int(num_of_iteration / pow(PARALLAX_DIVIDER, depth))
    top_level_count = calculate_parallax_top_level_count(num_of_iteration)

    # Create group depth node
    counter = 0
    while True:
        ig = tree.nodes.get('_iterate_depth_' + str(counter))

        ig_found = False
        if ig: ig_found = True

        if not ig and counter < depth:
            ig = tree.nodes.new('ShaderNodeGroup')
            ig.name = '_iterate_depth_' + str(counter)
            #ig.node_tree = iter_group.node_tree

        if ig and counter >= depth:
            if ig.node_tree:
                bpy.data.node_groups.remove(ig.node_tree)
            tree.nodes.remove(ig)

        if not ig_found and counter >= depth:
            break

        counter += 1

    # Fill group depth
    cur_tree = iter_tree
    for i in range(depth):
        ig = tree.nodes.get('_iterate_depth_' + str(i))
        if ig and not ig.node_tree:
            ig.node_tree = create_iterate_group_nodes(cur_tree, True)

        if ig and ig.node_tree:
            cur_tree = ig.node_tree

    # Create top level group
    top_level = tree.nodes.get('_iterate_depth_' + str(depth-1))
    if top_level:
        top_level_tree = top_level.node_tree
    else: top_level_tree = iter_tree

    counter = 0
    while True:
        it = tree.nodes.get('_iterate_' + str(counter))

        it_found = False
        if it: it_found = True

        if not it and counter < top_level_count:
            it = tree.nodes.new('ShaderNodeGroup')
            it.name = '_iterate_' + str(counter)

        if it:
            if counter >= top_level_count:
                tree.nodes.remove(it)
            elif it.node_tree != top_level_tree:
                it.node_tree = top_level_tree

        if not it_found and counter >= top_level_count:
            break

        counter += 1

def create_delete_iterate_nodes_(tree, num_of_iteration):
    iter_tree = tree.nodes.get('_iterate').node_tree
    
    # Calculate group needed
    group_needed = calculate_group_needed(num_of_iteration)

    # Create group
    iter_group = tree.nodes.get('_iterate_group_0')
    if not iter_group:
        iter_group = tree.nodes.new('ShaderNodeGroup')
        iter_group.node_tree = create_iterate_group_nodes(iter_tree, True)
        iter_group.name = '_iterate_group_0'

    counter = 0
    while True:
        ig = tree.nodes.get('_iterate_group_' + str(counter))

        ig_found = False
        if ig: ig_found = True

        if not ig and counter < group_needed:
            ig = tree.nodes.new('ShaderNodeGroup')
            ig.name = '_iterate_group_' + str(counter)
            ig.node_tree = iter_group.node_tree

        if ig and counter >= group_needed:
            tree.nodes.remove(ig)

        if not ig_found and counter >= group_needed:
            break

        counter += 1

def create_delete_iterate_nodes(tree, num_of_iteration):
    iter_tree = tree.nodes.get('_iterate').node_tree

    counter = 0
    while True:
        it = tree.nodes.get('_iterate_' + str(counter))

        it_found = False
        if it: it_found = True

        if not it and counter < num_of_iteration:
            it = tree.nodes.new('ShaderNodeGroup')
            it.name = '_iterate_' + str(counter)
            it.node_tree = iter_tree

        if it and counter >= num_of_iteration:
            tree.nodes.remove(it)

        if not it_found and counter >= num_of_iteration:
            break

        counter += 1

def set_relief_mapping_nodes(yp, node, img=None):
    ch = get_root_parallax_channel(yp)

    # Set node parameters
    #node.inputs[0].default_value = ch.displacement_height_ratio
    node.inputs[0].default_value = get_displacement_max_height(ch)
    node.inputs[1].default_value = ch.parallax_ref_plane

    tree = node.node_tree

    linear_steps = tree.nodes.get('_linear_search_steps')
    linear_steps.outputs[0].default_value = float(ch.parallax_num_of_linear_samples)

    binary_steps = tree.nodes.get('_binary_search_steps')
    binary_steps.outputs[0].default_value = float(ch.parallax_num_of_binary_samples)

    if img:
        depth_source = tree.nodes.get('_depth_source')
        depth_from_tex = depth_source.node_tree.nodes.get('_depth_from_tex')
        depth_from_tex.image = img

    linear_loop = tree.nodes.get('_linear_search')
    create_delete_iterate_nodes(linear_loop.node_tree, ch.parallax_num_of_linear_samples)

    binary_loop = tree.nodes.get('_binary_search')
    create_delete_iterate_nodes(binary_loop.node_tree, ch.parallax_num_of_binary_samples)

def get_channel_index(root_ch):
    yp = root_ch.id_data.yp

    for i, c in enumerate(yp.channels):
        if c == root_ch:
            return i

def get_channel_index_by_name(yp, name):
    for i, ch in enumerate(yp.channels):
        if ch.name == name:
            return i

    return None

def get_layer_channel_index(layer, ch):
    for i, c in enumerate(layer.channels):
        if c == ch:
            return i

def is_bump_distance_relevant(layer, ch):
    if layer.type in {'COLOR', 'BACKGROUND'} and ch.enable_transition_bump:
        return False
    return True

def get_layer_channel_bump_distance(layer, ch):
    # Some layer will have bump distance of 0.0, ignoring the prop value
    if not is_bump_distance_relevant(layer, ch):
        return 0.0
    return ch.bump_distance

def get_layer_channel_max_height(layer, ch, ch_idx=None):

    if layer.type == 'GROUP':

        if ch_idx == None: ch_idx = [i for i, c in enumerate(layer.channels) if c == ch][0]
        childs = get_list_of_direct_childrens(layer)
        if len(childs) == 0: return 0.0

        # Check all of its childrens
        base_distance = None
        for child in childs:
            for i, c in enumerate(child.channels):
                if i != ch_idx: continue

                h = get_layer_channel_max_height(child, c)

                if base_distance == None or h > base_distance:
                    base_distance = h

    else: 
        base_distance = abs(ch.normal_bump_distance) if ch.normal_map_type == 'NORMAL_MAP' else abs(get_layer_channel_bump_distance(layer, ch))

    if ch.enable_transition_bump:
        if ch.normal_map_type == 'NORMAL_MAP' and layer.type != 'GROUP':
            #max_height = ch.transition_bump_distance
            max_height = abs(get_transition_bump_max_distance_with_crease(ch))
        else:
            if ch.transition_bump_flip:
                max_height = abs(get_transition_bump_max_distance_with_crease(ch)) + base_distance*2

            else: 
                max_height = abs(get_transition_bump_max_distance_with_crease(ch)) + base_distance

    else: 
        max_height = base_distance if base_distance != None else 0.0

    # Multiply by intensity value
    max_height *= ch.intensity_value

    return max_height

def get_transition_bump_max_distance(ch):
    return ch.transition_bump_distance if not ch.transition_bump_flip else -ch.transition_bump_distance

def get_transition_bump_max_distance_with_crease(ch):
    if ch.transition_bump_flip:
        return -ch.transition_bump_distance

    if not ch.transition_bump_crease:
        return ch.transition_bump_distance

    tb = ch.transition_bump_distance
    fac = ch.transition_bump_crease_factor

    if fac <= 0.5:
        return (1 - fac) * tb 

    return fac * tb

def get_max_childs_heights(layer, ch_idx):

    # Get childrens
    childs = get_list_of_direct_childrens(layer)

    if len(childs) == 0: return 0.0

    max_child_heights = None
    for child in childs:
        for i, c in enumerate(child.channels):
            if i != ch_idx: continue

            # Do recursive the children is a group
            if child.type == 'GROUP':
                h = get_max_childs_heights(child, ch_idx)
            else: 
                h = get_layer_channel_max_height(child, c, ch_idx)

            if max_child_heights == None or h > max_child_heights:
                max_child_heights = h

    return max_child_heights

def get_transition_disp_delta(layer, ch):
    if layer.type == 'GROUP':

        # Get channel index
        ch_idx = [i for i, c in enumerate(layer.channels) if c == ch][0]

        max_child_heights = get_max_childs_heights(layer, ch_idx)
        delta = get_transition_bump_max_distance(ch) - max_child_heights

    else:
        bump_distance = ch.normal_bump_distance if ch.normal_blend_type else get_layer_channel_bump_distance(layer, ch)
        delta = get_transition_bump_max_distance(ch) - abs(bump_distance)

    return delta

def get_max_height_from_list_of_layers(layers, ch_index, layer=None, top_layers_only=False):

    max_height = 0.0

    for l in reversed(layers):
        if ch_index > len(l.channels)-1: continue
        if top_layers_only and l.parent_idx != -1: continue
        c = l.channels[ch_index]
        write_height = get_write_height(c)
        ch_max_height = get_layer_channel_max_height(l, c)
        if (l.enable and c.enable and 
                (write_height or (not write_height and l == layer)) and
                c.normal_blend_type in {'MIX', 'COMPARE'} and max_height < ch_max_height
                ):
            max_height = ch_max_height
        if l == layer:
            break

    for l in reversed(layers):
        if ch_index > len(l.channels)-1: continue
        if top_layers_only and l.parent_idx != -1: continue
        c = l.channels[ch_index]
        write_height = get_write_height(c)
        ch_max_height = get_layer_channel_max_height(l, c)
        if (l.enable and c.enable and 
                (write_height or (not write_height and l == layer)) and
                c.normal_blend_type == 'OVERLAY'
                ):
            max_height += ch_max_height
        if l == layer:
            break

    return max_height

def get_displacement_max_height(root_ch, layer=None):
    yp = root_ch.id_data.yp
    ch_index = get_channel_index(root_ch)

    if layer and layer.parent_idx != -1:
        parent = get_parent(layer)
        layers = get_list_of_direct_childrens(parent)
        max_height = get_max_height_from_list_of_layers(layers, ch_index, layer, top_layers_only=False)
    else:
        max_height = get_max_height_from_list_of_layers(yp.layers, ch_index, layer, top_layers_only=True)

    return max_height

def get_smooth_bump_channel(layer):

    yp = layer.id_data.yp

    for i, root_ch in enumerate(yp.channels):
        if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump:
            return layer.channels[i]

    return None

def get_smooth_bump_channels(layer):

    yp = layer.id_data.yp

    channels = []

    for i, root_ch in enumerate(yp.channels):
        if root_ch.type == 'NORMAL' and root_ch.enable_smooth_bump:
            channels.append(layer.channels[i])

    return channels

def get_write_height_normal_channels(layer):
    yp = layer.id_data.yp

    channels = []

    for i, root_ch in enumerate(yp.channels):
        if root_ch.type == 'NORMAL':
            ch = layer.channels[i]
            write_height = get_write_height(ch)
            if write_height:
                channels.append(ch)

    return channels

def get_write_height_normal_channel(layer):
    yp = layer.id_data.yp

    for i, root_ch in enumerate(yp.channels):
        if root_ch.type == 'NORMAL':
            ch = layer.channels[i]
            write_height = get_write_height(ch)
            if write_height:
                return ch

    return None

def update_layer_bump_distance(height_ch, height_root_ch, layer, tree=None):

    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)

    height_proc = tree.nodes.get(height_ch.height_proc)
    if height_proc and layer.type != 'GROUP':

        if height_ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:
            inp = height_proc.inputs.get('Value Max Height')
            if inp: inp.default_value = get_layer_channel_bump_distance(layer, height_ch)
            inp = height_proc.inputs.get('Transition Max Height')
            if inp: inp.default_value = get_transition_bump_max_distance(height_ch)
            inp = height_proc.inputs.get('Delta')
            if inp: inp.default_value = get_transition_disp_delta(layer, height_ch)
        elif height_ch.normal_map_type == 'NORMAL_MAP':
            inp = height_proc.inputs.get('Bump Height')
            if inp:
                if height_ch.enable_transition_bump:
                    inp.default_value = get_transition_bump_max_distance(height_ch)
                else: inp.default_value = height_ch.normal_bump_distance

    normal_proc = tree.nodes.get(height_ch.normal_proc)
    if normal_proc:

        max_height = get_displacement_max_height(height_root_ch, layer)

        if height_root_ch.enable_smooth_bump: 
            inp = normal_proc.inputs.get('Bump Height Scale')
            if inp: inp.default_value = get_fine_bump_distance(max_height)

        if 'Max Height' in normal_proc.inputs:
            normal_proc.inputs['Max Height'].default_value = max_height

def update_layer_bump_process_max_height(height_root_ch, layer, tree=None):

    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)
    if not tree: return

    bump_process = tree.nodes.get(layer.bump_process)
    if not bump_process: return

    #height_root_ch = get_root_height_channel(yp)

    prev_idx, prev_layer = get_lower_neighbor(layer)
    if prev_layer: 
        max_height = get_displacement_max_height(height_root_ch, prev_layer)
    else: max_height = 0.0

    bump_process.inputs['Max Height'].default_value = max_height

    if height_root_ch.enable_smooth_bump:
        if 'Bump Height Scale' in bump_process.inputs:
            bump_process.inputs['Bump Height Scale'].default_value = get_fine_bump_distance(max_height)
    #else:
    #    bump_process.inputs['Tweak'].default_value = 5.0

def update_displacement_height_ratio(root_ch, max_height=None):

    group_tree = root_ch.id_data
    yp = group_tree.yp

    if not max_height: max_height = get_displacement_max_height(root_ch)
    #max_height = root_ch.displacement_height_ratio

    baked_parallax = group_tree.nodes.get(BAKED_PARALLAX)
    if baked_parallax:
        #baked_parallax.inputs['depth_scale'].default_value = max_height
        depth_source_0 = baked_parallax.node_tree.nodes.get('_depth_source_0')
        if depth_source_0:
            pack = depth_source_0.node_tree.nodes.get('_normalize')
            if pack:
                if max_height != 0.0:
                    pack.inputs['Max Height'].default_value = max_height
                else: pack.inputs['Max Height'].default_value = 1.0

    parallax = group_tree.nodes.get(PARALLAX)
    if parallax:
        depth_source_0 = parallax.node_tree.nodes.get('_depth_source_0')
        if depth_source_0:
            pack = depth_source_0.node_tree.nodes.get('_normalize')
            if pack:
                if max_height != 0.0:
                    pack.inputs['Max Height'].default_value = max_height
                else: pack.inputs['Max Height'].default_value = 1.0

    end_linear = group_tree.nodes.get(root_ch.end_linear)
    if end_linear:
        if max_height != 0.0:
            end_linear.inputs['Max Height'].default_value = max_height
        else: end_linear.inputs['Max Height'].default_value = 1.0

        if root_ch.enable_smooth_bump:
            end_linear.inputs['Bump Height Scale'].default_value = get_fine_bump_distance(max_height)

    end_max_height = group_tree.nodes.get(root_ch.end_max_height)
    if end_max_height:
        if max_height != 0.0:
            end_max_height.outputs[0].default_value = max_height
        else: end_max_height.outputs[0].default_value = 1.0

    for uv in yp.uvs:
        parallax_prep = group_tree.nodes.get(uv.parallax_prep)
        if parallax_prep:
            parallax_prep.inputs['depth_scale'].default_value = max_height * root_ch.parallax_height_tweak

    # Update layer bump process
    for layer in reversed(yp.layers):
        update_layer_bump_process_max_height(root_ch, layer)
        height_ch = get_height_channel(layer)
        if height_ch:
            update_layer_bump_distance(height_ch, root_ch, layer)

def get_fine_bump_distance(distance):
    scale = 400
    #if layer.type == 'IMAGE':
    #    source = get_layer_source(layer)
    #    image = source.image
    #    if image: scale = image.size[0] / 10

    #return -1.0 * distance * scale
    return distance * scale

def get_bump_chain(layer, ch=None):

    yp = layer.id_data.yp

    chain = -1

    height_ch = get_height_channel(layer)
    if height_ch:
        chain = height_ch.transition_bump_chain

    # Try to get transition bump
    #trans_bump = get_transition_bump_channel(layer)

    #if trans_bump:
    #    chain = trans_bump.transition_bump_chain 
    #else:

    #    # Try to standard smooth bump if transition bump is not found
    #    for i, c in enumerate(layer.channels):

    #        if ch and c != ch: continue

    #        if yp.channels[i].type == 'NORMAL':
    #            chain_local = min(c.transition_bump_chain, len(layer.masks))
    #            if chain_local > chain:
    #                chain = chain_local

    return min(chain, len(layer.masks))

def get_transition_bump_falloff_emulated_curve_value(ch):
    if ch.transition_bump_flip:
        return -ch.transition_bump_falloff_emulated_curve_fac * 0.5 + 0.5
    else:
        return ch.transition_bump_falloff_emulated_curve_fac * 0.5 + 0.5

def check_if_node_is_duplicated_from_lib(node, lib_name):
    if not node or node.type != 'GROUP': return False
    m = re.match(r'^' + lib_name + '_Copy\.*\d{0,3}$', node.node_tree.name)
    if m: return True
    return False

def get_subsurf_modifier(obj, keyword=''):
    for mod in obj.modifiers:
        if mod.type == 'SUBSURF': # and mod.show_render and mod.show_viewport:
            if keyword != '' and keyword != mod.name: continue
            return mod

    return None

def get_displace_modifier(obj, keyword=''):
    for mod in obj.modifiers:
        if mod.type == 'DISPLACE': # and mod.show_render and mod.show_viewport:
            if keyword != '' and keyword != mod.name: continue
            return mod

    return None

def get_multires_modifier(obj, keyword=''):
    for mod in obj.modifiers:
        if mod.type == 'MULTIRES' and mod.total_levels > 0 and mod.show_viewport:
            if keyword != '' and keyword != mod.name: continue
            return mod

    return None

def get_uv_layers(obj):
    if obj.type != 'MESH': return []

    if not is_greater_than_280():
        uv_layers = obj.data.uv_textures
    else: uv_layers = obj.data.uv_layers

    return uv_layers

def get_vcol_index(obj, vcol_name):
    vcols = obj.data.vertex_colors
    for i, vc in enumerate(vcols):
        if vc.name == vcol_name:
            return i

    return -1

def get_uv_layer_index(obj, uv_name):
    uv_layers = get_uv_layers(obj)
    for i, ul in enumerate(uv_layers):
        if ul.name == uv_name:
            return i

    return -1

def move_vcol_to_bottom(obj, index):
    set_active_object(obj)
    vcols = obj.data.vertex_colors

    # Get original uv name
    vcols.active_index = index
    ori_name = vcols.active.name

    # Duplicate vcol
    if is_greater_than_330():
        bpy.ops.geometry.color_attribute_duplicate()
    else: bpy.ops.mesh.vertex_color_add()

    # Delete old vcol
    vcols.active_index = index

    if is_greater_than_330():
        bpy.ops.geometry.color_attribute_remove()
    else: bpy.ops.mesh.vertex_color_remove()

    # Set original name to newly created uv
    vcols[-1].name = ori_name

def move_vcol(obj, from_index, to_index):
    vcols = obj.data.vertex_colors
    
    if from_index == to_index or from_index < 0 or from_index >= len(vcols) or to_index < 0 or to_index >= len(vcols):
        #print("Invalid indices")
        return

    # Move the UV map down to the target index
    if from_index < to_index:
        move_vcol_to_bottom(obj, from_index)
        for i in range(len(vcols)-1-to_index):
            move_vcol_to_bottom(obj, to_index)
            
    # Move the UV map up to the target index
    elif from_index > to_index:
        for i in range(from_index-to_index):
            move_vcol_to_bottom(obj, to_index)
        for i in range(len(vcols)-1-from_index):
            move_vcol_to_bottom(obj, to_index+1)
    
    vcols.active_index = to_index

def move_uv_to_bottom(obj, index):
    set_active_object(obj)
    uv_layers = get_uv_layers(obj)

    # Get original uv name
    uv_layers.active_index = index
    ori_name = uv_layers.active.name

    # Duplicate uv
    bpy.ops.mesh.uv_texture_add()

    # Delete old uv
    uv_layers.active_index = index
    bpy.ops.mesh.uv_texture_remove()

    # Set original name to newly created uv
    uv_layers[-1].name = ori_name
    
def move_uv(obj, from_index, to_index):
    uv_layers = get_uv_layers(obj)
    
    if from_index == to_index or from_index < 0 or from_index >= len(uv_layers) or to_index < 0 or to_index >= len(uv_layers):
        #print("Invalid indices")
        return
    
    # Move the UV map down to the target index
    if from_index < to_index:
        move_uv_to_bottom(obj, from_index)
        for i in range(len(uv_layers)-1-to_index):
            move_uv_to_bottom(obj, to_index)
            
    # Move the UV map up to the target index
    elif from_index > to_index:
        for i in range(from_index-to_index):
            move_uv_to_bottom(obj, to_index)
        for i in range(len(uv_layers)-1-from_index):
            move_uv_to_bottom(obj, to_index+1)
    
    uv_layers.active_index = to_index

def get_vertex_colors(obj):
    if not obj or obj.type != 'MESH': return []

    if not is_greater_than_320():
        return obj.data.vertex_colors

    return obj.data.color_attributes

def get_active_vertex_color(obj):
    if not obj or obj.type != 'MESH': return None

    if not is_greater_than_320():
        return obj.data.vertex_colors.active

    return obj.data.color_attributes.active_color

def set_active_vertex_color(obj, vcol):
    try:
        if is_greater_than_320():
            obj.data.color_attributes.active_color = vcol
            # HACK: Baking to vertex color still use active legacy vertex colors data
            if hasattr(obj.data, 'vertex_colors'):
                v = obj.data.vertex_colors.get(vcol.name)
                obj.data.vertex_colors.active = v
        else: obj.data.vertex_colors.active = vcol
    except Exception as e: print(e)

def new_vertex_color(obj, name, data_type='BYTE_COLOR', domain='CORNER'):
    if not obj or obj.type != 'MESH': return None

    if not is_greater_than_320():
        return obj.data.vertex_colors.new(name=name)

    return obj.data.color_attributes.new(name, data_type, domain)

def get_default_uv_name(obj, yp=None):
    uv_layers = get_uv_layers(obj)
    uv_name = ''

    if obj.type == 'MESH' and len(uv_layers) > 0:
        active_name = uv_layers.active.name
        if active_name == TEMP_UV:
            if yp and len(yp.layers) > 0:
                uv_name = yp.layers[yp.active_layer_index].uv_name
            else:
                for uv_layer in uv_layers:
                    if uv_layer.name != TEMP_UV:
                        uv_name = uv_layer.name
        else: uv_name = uv_layers.active.name

    return uv_name

def get_relevant_uv(obj, yp):
    try: layer = yp.layers[yp.active_layer_index]
    except: return None

    uv_name = layer.uv_name

    for mask in layer.masks:
        if mask.active_edit:
            if mask.type == 'IMAGE':
                active_mask = mask
                uv_name = mask.uv_name

    return uv_name 

def get_active_image_and_stuffs(obj, yp):

    image = None
    uv_name = ''
    vcol = None
    src_of_img = None
    mapping = None

    vcols = get_vertex_colors(obj)

    layer = yp.layers[yp.active_layer_index]
    tree = get_tree(layer)

    for mask in layer.masks:
        if mask.active_edit:
            source = get_mask_source(mask)

            if mask.type == 'IMAGE':
                uv_name = mask.uv_name
                image = source.image
                src_of_img = mask
                mapping = get_mask_mapping(mask)
            elif mask.type == 'VCOL' and obj.type == 'MESH':
                # If source is empty, still try to get vertex color
                if get_source_vcol_name(source) == '':
                    vcol = vcols.get(mask.name)
                    if vcol: set_source_vcol_name(source, vcol.name)
                else: vcol = vcols.get(get_source_vcol_name(source))
            elif mask.type == 'COLOR_ID' and obj.type == 'MESH':
                vcol = vcols.get(COLOR_ID_VCOL_NAME)

    for ch in layer.channels:
        if ch.active_edit and ch.override and ch.override_type != 'DEFAULT':
            #source = tree.nodes.get(ch.source)
            source = get_channel_source(ch, layer)

            if ch.override_type == 'IMAGE':
                uv_name = layer.uv_name
                image = source.image
                src_of_img = ch
                mapping = get_layer_mapping(layer)

            elif ch.override_type == 'VCOL' and obj.type == 'MESH':
                vcol = vcols.get(get_source_vcol_name(source))

        if ch.active_edit_1 and ch.override_1 and ch.override_1_type != 'DEFAULT':
            source = tree.nodes.get(ch.source_1)

            if ch.override_1_type == 'IMAGE':
                uv_name = layer.uv_name
                source_1 = get_channel_source_1(ch)
                image = source_1.image
                src_of_img = ch
                mapping = get_layer_mapping(layer)

    if not image and layer.type == 'IMAGE':
        uv_name = layer.uv_name
        source = get_layer_source(layer, tree)
        image = source.image
        src_of_img = layer
        mapping = get_layer_mapping(layer)

    if not vcol and layer.type == 'VCOL' and obj.type == 'MESH':
        source = get_layer_source(layer, tree)
        vcol = vcols.get(get_source_vcol_name(source))

    return image, uv_name, src_of_img, mapping, vcol

def set_active_uv_layer(obj, uv_name):
    uv_layers = get_uv_layers(obj)

    for i, uv in enumerate(uv_layers):
        if uv.name == uv_name:
            if uv_layers.active_index != i:
                uv_layers.active_index = i

def is_any_layer_using_channel(root_ch, node=None):

    yp = root_ch.id_data.yp
    ch_idx = get_channel_index(root_ch)

    # Check node inputs
    if node:
        inp = node.inputs.get(root_ch.name)
        if inp and len(inp.links):
            return True
        inp = node.inputs.get(root_ch.name + io_suffix['ALPHA'])
        if inp and len(inp.links):
            return True
        inp = node.inputs.get(root_ch.name + io_suffix['HEIGHT'])
        if inp and len(inp.links):
            return True

    for layer in yp.layers:
        if layer.channels[ch_idx].enable:
            return True

    return False

def get_layer_type_icon(layer_type):

    if layer_type == 'IMAGE':
        return 'IMAGE_DATA'
    elif layer_type == 'VCOL':
        return 'GROUP_VCOL'
    elif layer_type == 'BACKGROUND':
        return 'IMAGE_RGB_ALPHA'
    elif layer_type == 'GROUP':
        return 'FILE_FOLDER'
    elif layer_type == 'COLOR':
        return 'COLOR'
    elif layer_type == 'HEMI':
        if is_greater_than_280(): return 'LIGHT'
        return 'LAMP'

    return 'TEXTURE'

def save_hemi_props(layer, source):
    norm = source.node_tree.nodes.get('Normal')
    if norm: layer.hemi_vector = norm.outputs[0].default_value

def get_scene_objects():
    if is_greater_than_280():
        return bpy.context.view_layer.objects
    else: return bpy.context.scene.objects

def is_mesh_flat_shaded(mesh):

    for i, f in enumerate(mesh.polygons):
        if not f.use_smooth:
            return True

        # Only check first 10 polygons to improve performance
        if i > 10:
            break

    return False

def get_all_materials_with_yp_nodes(mesh_only=True):
    mats = []

    for obj in get_scene_objects():
        if mesh_only and obj.type != 'MESH': continue
        if not hasattr(obj, 'data') or not hasattr(obj.data, 'materials'): continue
        for mat in obj.data.materials:
            if any([n for n in mat.node_tree.nodes if n.type == 'GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node]):
                if mat not in mats:
                    mats.append(mat)

    return mats

def get_all_objects_with_same_materials(mat, mesh_only=False, uv_name='', selected_only=False):
    objs = []

    if selected_only:
        if len(bpy.context.selected_objects) > 0:
            objects = bpy.context.selected_objects
        else: objects = [bpy.context.object]
    else: objects = get_scene_objects()

    for obj in objects:

        if uv_name != '':
            uv_layers = get_uv_layers(obj)
            if not uv_layers or not uv_layers.get(uv_name): continue

        if hasattr(obj.data, 'polygons') and len(obj.data.polygons) == 0: continue

        if mesh_only:
            if obj.type != 'MESH': continue
            #if is_greater_than_280() and obj.hide_viewport: continue
            #if obj.hide_render: continue
            #if len(get_uv_layers(obj)) == 0: continue
            if len(obj.data.polygons) == 0: continue
        if not obj.data or not hasattr(obj.data, 'materials'): continue
        for m in obj.data.materials:
            if m == mat: # and obj not in objs:
                objs.append(obj)
                break

    return objs

def get_yp_images(yp, udim_only=False):

    images = []

    for layer in yp.layers:

        for mask in layer.masks:
            if mask.type == 'IMAGE':
                source = get_mask_source(mask)
                if not source or not source.image: continue
                image = source.image
                if udim_only and image.source != 'TILED': continue
                if image not in images:
                    images.append(source.image)

        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            if not source or not source.image: continue
            image = source.image
            if udim_only and image.source != 'TILED': continue
            if image not in images:
                images.append(source.image)

    return images

def get_yp_entites_using_same_image(yp, image):
    entities = []

    for layer in yp.layers:

        for mask in layer.masks:
            if mask.type == 'IMAGE':
                source = get_mask_source(mask)
                if source and source.image == image:
                    entities.append(mask)

        for ch in layer.channels:
            if ch.override and ch.override_type == 'IMAGE':
                source = get_channel_source(ch, layer)
                if source and source.image == image:
                    entities.append(ch)
            elif ch.override_1 and ch.override_1_type == 'IMAGE':
                source = get_channel_source_1(ch, layer)
                if source and source.image == image:
                    entities.append(ch)

        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            if source and source.image == image:
                entities.append(layer)

    return entities 

def get_yp_entities_images_and_segments(yp):
    entities = []
    images = []
    segment_names = []

    for layer in yp.layers:
        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            if source and source.image:
                image = source.image
                if image.yia.is_image_atlas or image.yua.is_udim_atlas:
                    if image.yia.is_image_atlas:
                        segment = image.yia.segments.get(layer.segment_name)
                    else: segment = image.yua.segments.get(layer.segment_name)
                    if segment.name not in segment_names:
                        images.append(image)
                        segment_names.append(segment.name)
                        entities.append([layer])
                    else:
                        idx = [i for i, s in enumerate(segment_names) if s == segment.name][0]
                        entities[idx].append(layer)
                else:
                    if image not in images:
                        images.append(image)
                        segment_names.append('')
                        entities.append([layer])
                    else:
                        idx = [i for i, img in enumerate(images) if img == image][0]
                        entities[idx].append(layer)
        for mask in layer.masks:
            if mask.type == 'IMAGE':
                source = get_mask_source(mask)
                if source and source.image:
                    image = source.image
                    if image.yia.is_image_atlas or image.yua.is_udim_atlas:
                        if image.yia.is_image_atlas:
                            segment = image.yia.segments.get(mask.segment_name)
                        else: segment = image.yua.segments.get(mask.segment_name)
                        if segment.name not in segment_names:
                            images.append(image)
                            segment_names.append(segment.name)
                            entities.append([mask])
                        else:
                            idx = [i for i, s in enumerate(segment_names) if s == segment.name][0]
                            entities[idx].append(mask)
                    else:
                        if image not in images:
                            images.append(image)
                            segment_names.append('')
                            entities.append([mask])
                        else:
                            idx = [i for i, img in enumerate(images) if img == image][0]
                            entities[idx].append(mask)

    return entities, images, segment_names

def check_need_prev_normal(layer):

    yp = layer.id_data.yp
    height_root_ch = get_root_height_channel(yp)

    # Check if previous normal is needed
    need_prev_normal = False
    if layer.type == 'HEMI' and layer.hemi_use_prev_normal and height_root_ch:
        need_prev_normal = True

    # Also check mask
    if not need_prev_normal:
        for mask in layer.masks:
            if mask.type == 'HEMI' and mask.hemi_use_prev_normal and height_root_ch:
                need_prev_normal = True
                break

    return need_prev_normal

def get_all_baked_channel_images(tree):

    if not tree.yp.is_ypaint_node: return
    yp = tree.yp

    images = []

    for ch in yp.channels:

        baked = tree.nodes.get(ch.baked)
        if baked and baked.image:
            images.append(baked.image)

        if ch.type == 'NORMAL':
            baked_disp = tree.nodes.get(ch.baked_disp)
            if baked_disp and baked_disp.image:
                images.append(baked_disp.image)

            baked_normal_overlay = tree.nodes.get(ch.baked_normal_overlay)
            if baked_normal_overlay and baked_normal_overlay.image:
                images.append(baked_normal_overlay.image)

    return images

def is_layer_using_vector(layer):
    if layer.type not in {'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX'}:
        return True

    for ch in layer.channels:
        if ch.override and ch.override_type not in {'VCOL', 'DEFAULT'}:
            return True

    return False

def get_node(tree, name, parent=None):
    node = tree.nodes.get(name)

    if node and parent and node.parent != parent:
        return None

    return node

def is_overlay_normal_empty(yp):

    for l in yp.layers:
        c = get_height_channel(l)
        if not l.enable or not c.enable: continue
        if c.normal_map_type == 'NORMAL_MAP' or (c.normal_map_type == 'BUMP_MAP' and not c.write_height):
            return False

    return True

# ShaderNodeVertexColor can't use bump map, so ShaderNodeAttribute will be used for now
def get_vcol_bl_idname():
    #if is_greater_than_281():
    #    return 'ShaderNodeVertexColor'
    return 'ShaderNodeAttribute'

def set_source_vcol_name(src, name):
    #if is_greater_than_281():
    #    src.layer_name = name
    #else: 
    src.attribute_name = name

def get_source_vcol_name(src):
    #if is_greater_than_281():
    #    return src.layer_name
    return src.attribute_name

def get_vcol_from_source(obj, src):
    name = get_source_vcol_name(src)
    vcols = get_vertex_colors(obj)
    return vcols.get(name)

def get_layer_vcol(obj, layer):
    src = get_layer_source(layer)
    return get_vcol_from_source(obj, src)

def check_colorid_vcol(objs):
    for o in objs:
        vcols = get_vertex_colors(o)
        if COLOR_ID_VCOL_NAME not in vcols:
            try:
                vcol = new_vertex_color(o, COLOR_ID_VCOL_NAME)
                set_obj_vertex_colors(o, vcol.name, (0.0, 0.0, 0.0, 1.0))
                #set_active_vertex_color(o, vcol)
            except Exception as e: print(e)

def is_colorid_already_being_used(yp, color_id):
    for l in yp.layers:
        for m in l.masks:
            if abs(m.color_id[0]-color_id[0]) < COLORID_TOLERANCE and abs(m.color_id[1]-color_id[1]) < COLORID_TOLERANCE and abs(m.color_id[2]-color_id[2]) < COLORID_TOLERANCE:
                return True
    return False

def is_colorid_vcol_still_being_used(objs):

    for o in objs:
        for m in o.data.materials:
            for n in m.node_tree.nodes:
                if n.type == 'GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node:
                    for l in n.node_tree.yp.layers:
                        for ma in l.masks:
                            if ma.type == 'COLOR_ID':
                                return True

    return False

def is_image_source_srgb(image, source, root_ch=None):
    if not is_greater_than_280():
        return source.color_space == 'COLOR'

    # HACK: Sometimes just loaded UDIM images has empty colorspace settings name
    if image.source == 'TILED' and image.colorspace_settings.name == '':
        return True

    # Float images is behaving like srgb for some reason in blender
    if root_ch and root_ch.colorspace == 'SRGB' and image.is_float and image.colorspace_settings.name != 'sRGB':
        return True

    return image.colorspace_settings.name == 'sRGB'

def any_linear_images_problem(yp):
    for layer in yp.layers:
        layer_tree = get_tree(layer)

        for i, ch in enumerate(layer.channels):
            root_ch = yp.channels[i]
            if ch.override_type == 'IMAGE':
                source_tree = get_channel_source_tree(ch)
                linear = source_tree.nodes.get(ch.linear)
                source = source_tree.nodes.get(ch.source)
                if not source: continue

                image = source.image
                if not image: continue
                if (
                    (is_image_source_srgb(image, source, root_ch) and not linear) or
                    (not is_image_source_srgb(image, source, root_ch) and linear)
                    ):
                    return True

        for ch in layer.channels:
            if ch.override_1_type == 'IMAGE':
                linear_1 = layer_tree.nodes.get(ch.linear_1)
                source_1 = layer_tree.nodes.get(ch.source_1)
                if not source_1: continue

                image = source_1.image
                if not image: continue
                if (
                    (is_image_source_srgb(image, source_1) and not linear_1) or
                    (not is_image_source_srgb(image, source_1) and linear_1)
                    ):
                    return True

        for mask in layer.masks:
            if mask.type == 'IMAGE':
                source_tree = get_mask_tree(mask)
                linear = source_tree.nodes.get(mask.linear)
                source = source_tree.nodes.get(mask.source)
                if not source: continue
                image = source.image
                if not image: continue
                if (
                    (is_image_source_srgb(image, source) and not linear) or
                    (not is_image_source_srgb(image, source) and linear)
                    ):
                    return True

        if layer.type == 'IMAGE':
            source_tree = get_source_tree(layer)
            linear = source_tree.nodes.get(layer.linear)
            source = source_tree.nodes.get(layer.source)
            if not source: continue
            image = source.image
            if not image: continue
            if (
                (is_image_source_srgb(image, source) and not linear) or
                (not is_image_source_srgb(image, source) and linear)
                ):
                return True

    return False

def get_write_height(ch):
    if ch.normal_map_type == 'NORMAL_MAP':
        return ch.normal_write_height
    #if ch.normal_map_type == 'BUMP_MAP':
    return ch.write_height

    # BUMP_NORMAL_MAP currently always write height
    #return True 

def get_flow_vcol(obj, uv0, uv1):

    vcols = get_vertex_colors(obj)
    vcol = vcols.get(FLOW_VCOL)
    if not vcol:
        vcol = new_vertex_color(obj, FLOW_VCOL, data_type='BYTE_COLOR', domain='CORNER')

    # Orientation of straight uv
    main_vec = Vector((0, -1))

    # To store each variation of corners for each vertices
    corner_vecs = []
    corner_locs = []
    
    for i in range(len(obj.data.vertices)):
        corner_locs.append([])
        corner_vecs.append([])
        
    # Store unique corners based on uv0 locations
    for i in range(len(obj.data.vertices)):
        
        locs0 = [uv0.data[li].uv for li, l in enumerate(obj.data.loops) if l.vertex_index == i]
        
        for loc in locs0:
            if loc not in corner_locs[i]:
                corner_locs[i].append(loc)
                corner_vecs[i].append(Vector((0, 0)))
    
    # Add uv edge vector to each unique corner
    for poly in obj.data.polygons:
        for ek in poly.edge_keys:
            # Get loop index
            li0 = [li for li in poly.loop_indices if obj.data.loops[li].vertex_index == ek[0]][0]
            li1 = [li for li in poly.loop_indices if obj.data.loops[li].vertex_index == ek[1]][0]
            vec1 = uv1.data[li0].uv - uv1.data[li1].uv
            vec1.normalize()
            dot = main_vec.dot(vec1)
            
            vec0 = uv0.data[li0].uv - uv0.data[li1].uv
            
            # Add vector to stored corner data
            for i, cl in enumerate(corner_locs[ek[0]]):
                if cl == uv0.data[li0].uv:
                    corner_vecs[ek[0]][i] += vec0 * dot
            for i, cl in enumerate(corner_locs[ek[1]]):
                if cl == uv0.data[li1].uv:
                    corner_vecs[ek[1]][i] += vec0 * dot
        
    # Normalize the vector and store it to vertex color
    for i, cl in enumerate(corner_locs):
        
        for j, cll in enumerate(cl):
            cv = corner_vecs[i][j]
            cv.normalize()
            cv /= 2.0
            cv += Vector((0.5, 0.5))
        
            lis = [li for li, l in enumerate(obj.data.loops) if uv0.data[li].uv == cll]
            
            for li in lis:
                if is_greater_than_280():
                    vcol.data[li].color = (cv.x, cv.y, 0.0, 1.0)
                else:
                    vcol.data[li].color = (cv.x, cv.y, 0.0)

    return vcol

def new_mix_node(tree, entity, prop, label='', data_type='RGBA'):
    ''' Create new mix node '''
    if not hasattr(entity, prop): return

    node_id_name = 'ShaderNodeMix' if is_greater_than_340() else 'ShaderNodeMixRGB'

    node = new_node(tree, entity, prop, node_id_name, label)

    if is_greater_than_340():
        node.data_type = data_type

    return node

def simple_new_mix_node(tree, data_type='RGBA', label=''):
    ''' Create simple new mix node '''

    if is_greater_than_340():
        node = tree.nodes.new('ShaderNodeMix')
        node.data_type = data_type
    else: node = tree.nodes.new('ShaderNodeMixRGB')

    if label != '': node.label = label

    return node

def check_new_mix_node(tree, entity, prop, label='', return_dirty=False, data_type='RGBA'):
    ''' Check if mix node is available, if not, create one '''

    dirty = False

    # Try to get the node first
    try: node = tree.nodes.get(getattr(entity, prop))
    except: 
        if return_dirty:
            return None, dirty
        return None

    # Create new node if not found
    if not node:
        node = new_mix_node(tree, entity, prop, label, data_type)
        dirty = True

    if return_dirty:
        return node, dirty

    return node

def replace_new_mix_node(tree, entity, prop, label='', return_status=False, hard_replace=False, dirty=False, force_replace=False, data_type='RGBA'):

    if is_greater_than_340():
        node_id_name = 'ShaderNodeMix'
    else: node_id_name = 'ShaderNodeMixRGB'

    group_name = ''

    node, dirty = replace_new_node(tree, entity, prop, node_id_name, label, group_name, 
            return_status=True, hard_replace=hard_replace, dirty=dirty, force_replace=force_replace)

    if is_greater_than_340():
        node.data_type = data_type

    if return_status:
        return node, dirty

    return node

def set_mix_clamp(mix, bool_val):
    if hasattr(mix, 'clamp_result'):
        mix.clamp_result = bool_val
    elif hasattr(mix, 'use_clamp'):
        mix.use_clamp = bool_val

def get_mix_color_indices(mix):
    if mix == None: return 0, 0, 0

    if mix.bl_idname == 'ShaderNodeMix':
        if mix.data_type == 'FLOAT':
            return 2, 3, 0
        elif mix.data_type == 'VECTOR':
            return 4, 5, 1
        return 6, 7, 2

    # Check for Color1 input name
    idx0 = [i for i, inp in enumerate(mix.inputs) if inp.name == 'Color1']
    if len(idx0) > 0: 
        idx0 = idx0[0]
    else: idx0 = 1

    idx1 = [i for i, inp in enumerate(mix.inputs) if inp.name == 'Color2']
    if len(idx1) > 0: 
        idx1 = idx1[0]
    else: idx1 = 2

    outidx = 0

    return idx0, idx1, outidx

def get_yp_fcurves(yp):

    tree = yp.id_data

    fcurves = []

    if tree.animation_data and tree.animation_data.action:
        for fc in tree.animation_data.action.fcurves:
            if fc.data_path.startswith('yp.'):
                fcurves.append(fc)

    return fcurves

def remap_layer_fcurves(yp, index_dict):

    fcurves = get_yp_fcurves(yp)
    swapped_fcurves = []

    for i, lay in enumerate(yp.layers):
        if lay.name not in index_dict: continue
        original_index = index_dict[lay.name]
        if original_index == i: continue

        for fc in fcurves:
            if fc in swapped_fcurves: continue
            m = re.match(r'^yp\.layers\[(\d+)\].*', fc.data_path)
            if m:
                index = int(m.group(1))

                if index == original_index:
                    fc.data_path = fc.data_path.replace('yp.layers[' + str(original_index) + ']', 'yp.layers[' + str(i) + ']')
                    swapped_fcurves.append(fc)

def swap_channel_fcurves(yp, idx0, idx1):
    fcurves = get_yp_fcurves(yp)

    for fc in fcurves:
        m = re.match(r'^yp\.channels\[(\d+)\].*', fc.data_path)
        if m:
            index = int(m.group(1))

            if index == idx0:
                fc.data_path = fc.data_path.replace('yp.channels[' + str(idx0) + ']', 'yp.channels[' + str(idx1) + ']')

            elif index == idx1:
                fc.data_path = fc.data_path.replace('yp.channels[' + str(idx1) + ']', 'yp.channels[' + str(idx0) + ']')

def swap_layer_channel_fcurves(layer, idx0, idx1):
    yp = layer.id_data.yp
    fcurves = get_yp_fcurves(yp)

    for fc in fcurves:
        if layer.path_from_id() not in fc.data_path: continue
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\].*', fc.data_path)
        if m:
            index = int(m.group(2))

            if index == idx0:
                fc.data_path = fc.data_path.replace('.channels[' + str(idx0) + ']', '.channels[' + str(idx1) + ']')

            elif index == idx1:
                fc.data_path = fc.data_path.replace('.channels[' + str(idx1) + ']', '.channels[' + str(idx0) + ']')

def swap_mask_fcurves(layer, idx0, idx1):
    yp = layer.id_data.yp
    fcurves = get_yp_fcurves(yp)

    for fc in fcurves:
        if layer.path_from_id() not in fc.data_path: continue
        m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\].*', fc.data_path)
        if m:
            index = int(m.group(2))

            if index == idx0:
                fc.data_path = fc.data_path.replace('.masks[' + str(idx0) + ']', '.masks[' + str(idx1) + ']')

            elif index == idx1:
                fc.data_path = fc.data_path.replace('.masks[' + str(idx1) + ']', '.masks[' + str(idx0) + ']')

def swap_mask_channel_fcurves(mask, idx0, idx1):
    yp = mask.id_data.yp
    fcurves = get_yp_fcurves(yp)

    for fc in fcurves:
        if mask.path_from_id() not in fc.data_path: continue
        m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]\.channels\[(\d+)\].*', fc.data_path)
        if m:
            index = int(m.group(3))

            if index == idx0:
                fc.data_path = fc.data_path.replace('.channels[' + str(idx0) + ']', '.channels[' + str(idx1) + ']')

            elif index == idx1:
                fc.data_path = fc.data_path.replace('.channels[' + str(idx1) + ']', '.channels[' + str(idx0) + ']')

def swap_modifier_fcurves(parent, idx0, idx1):
    yp = parent.id_data.yp
    fcurves = get_yp_fcurves(yp)

    for fc in fcurves:
        if parent.path_from_id() not in fc.data_path: continue
        m = re.match(r'.*\.modifiers\[(\d+)\].*', fc.data_path)
        if m:
            index = int(m.group(1))

            if index == idx0:
                fc.data_path = fc.data_path.replace('.modifiers[' + str(idx0) + ']', '.modifiers[' + str(idx1) + ']')

            elif index == idx1:
                fc.data_path = fc.data_path.replace('.modifiers[' + str(idx1) + ']', '.modifiers[' + str(idx0) + ']')

def swap_normal_modifier_fcurves(modifier, idx0, idx1):
    yp = modifier.id_data.yp
    fcurves = get_yp_fcurves(yp)

    for fc in fcurves:
        if modifier.path_from_id() not in fc.data_path: continue
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.modifiers_1\[(\d+)\].*', fc.data_path)

        if m:
            index = int(m.group(3))

            if index == idx0:
                fc.data_path = fc.data_path.replace('.modifiers_1[' + str(idx0) + ']', '.modifiers_1[' + str(idx1) + ']')

            elif index == idx1:
                fc.data_path = fc.data_path.replace('.modifiers_1[' + str(idx1) + ']', '.modifiers_1[' + str(idx0) + ']')

def remove_entity_fcurves(entity):
    tree = entity.id_data
    yp = tree.yp
    fcurves = get_yp_fcurves(yp)

    for fc in reversed(fcurves):
        if entity.path_from_id() in fc.data_path:
            tree.animation_data.action.fcurves.remove(fc)

def remove_channel_fcurves(root_ch):
    tree = root_ch.id_data
    yp = tree.yp
    fcurves = get_yp_fcurves(yp)

    index = get_channel_index(root_ch)

    for fc in reversed(fcurves):
        m = re.match(r'.*\.channels\[(\d+)\].*', fc.data_path)
        if m and index == int(m.group(1)):
            tree.animation_data.action.fcurves.remove(fc)

def shift_modifier_fcurves_down(parent):
    yp = parent.id_data.yp
    fcurves = get_yp_fcurves(yp)

    for i, mod in reversed(list(enumerate(parent.modifiers))):
        for fc in fcurves:
            if parent.path_from_id() not in fc.data_path: continue
            m = re.match(r'.*\.modifiers\[(\d+)\].*', fc.data_path)
            if m and int(m.group(1)) == i:
                fc.data_path = fc.data_path.replace('.modifiers[' + str(i) + ']', '.modifiers[' + str(i+1) + ']')

def shift_normal_modifier_fcurves_down(parent):
    yp = parent.id_data.yp
    fcurves = get_yp_fcurves(yp)

    for i, mod in reversed(list(enumerate(parent.modifiers_1))):
        for fc in fcurves:
            if parent.path_from_id() not in fc.data_path: continue
            m = re.match(r'.*\.modifiers_1\[(\d+)\].*', fc.data_path)
            if m and int(m.group(1)) == i:
                fc.data_path = fc.data_path.replace('.modifiers_1[' + str(i) + ']', '.modifiers_1[' + str(i+1) + ']')

def shift_modifier_fcurves_up(parent, start_index=1):
    tree = parent.id_data
    yp = tree.yp
    fcurves = get_yp_fcurves(yp)

    for i, mod in enumerate(parent.modifiers):
        if i < start_index: continue
        for fc in fcurves:
            if parent.path_from_id() not in fc.data_path: continue
            m = re.match(r'.*\.modifiers\[(\d+)\].*', fc.data_path)
            if m and int(m.group(1)) == i:
                fc.data_path = fc.data_path.replace('.modifiers[' + str(i) + ']', '.modifiers[' + str(i-1) + ']')

def shift_normal_modifier_fcurves_up(parent, start_index=1):
    tree = parent.id_data
    yp = tree.yp
    fcurves = get_yp_fcurves(yp)

    for i, mod in enumerate(parent.modifiers_1):
        if i < start_index: continue
        for fc in fcurves:
            if parent.path_from_id() not in fc.data_path: continue
            m = re.match(r'.*\.modifiers_1\[(\d+)\].*', fc.data_path)
            if m and int(m.group(1)) == i:
                fc.data_path = fc.data_path.replace('.modifiers_1[' + str(i) + ']', '.modifiers_1[' + str(i-1) + ']')

def shift_channel_fcurves_up(yp, start_index=1):
    fcurves = get_yp_fcurves(yp)

    for i, root_ch in enumerate(yp.channels):
        if i < start_index: continue
        for fc in fcurves:
            m = re.match(r'.*\.channels\[(\d+)\].*', fc.data_path)
            if m and int(m.group(1)) == i:
                fc.data_path = fc.data_path.replace('.channels[' + str(i) + ']', '.channels[' + str(i-1) + ']')

def shift_mask_fcurves_up(layer, start_index=1):
    tree = layer.id_data
    yp = tree.yp
    fcurves = get_yp_fcurves(yp)

    for i, mask in enumerate(layer.masks):
        if i < start_index: continue
        for fc in fcurves:
            if layer.path_from_id() not in fc.data_path: continue
            m = re.match(r'.*\.masks\[(\d+)\].*', fc.data_path)
            if m and int(m.group(1)) == i:
                fc.data_path = fc.data_path.replace('.masks[' + str(i) + ']', '.masks[' + str(i-1) + ']')

def is_tangent_sign_hacks_needed(yp):
    return yp.enable_tangent_sign_hacks and is_greater_than_280() and not is_greater_than_300()

def is_root_ch_prop_node_unique(root_ch, prop):
    yp = root_ch.id_data.yp

    for ch in yp.channels:
        try:
            if ch != root_ch and getattr(ch, prop) == getattr(root_ch, prop):
                return False
        except Exception as e: print(e)

    return True

def get_first_mirror_modifier(obj):
    for m in obj.modifiers:
        if m.type == 'MIRROR':
            return m

    return None

def copy_image_channel_pixels(src, dest, src_idx=0, dest_idx=0, segment=None, segment_src=None):

    start_x = 0
    start_y = 0

    src_start_x = 0
    src_start_y = 0

    width = src.size[0]
    height = src.size[1]

    if segment:
        start_x = width * segment.tile_x
        start_y = height * segment.tile_y

    if segment_src:
        width = segment_src.width
        height = segment_src.height

        src_start_x = width * segment_src.tile_x
        src_start_y = height * segment_src.tile_y

    if is_greater_than_283():

        # Store pixels to numpy
        dest_pxs = numpy.empty(shape=dest.size[0]*dest.size[1]*4, dtype=numpy.float32)
        src_pxs = numpy.empty(shape=src.size[0]*src.size[1]*4, dtype=numpy.float32)
        dest.pixels.foreach_get(dest_pxs)
        src.pixels.foreach_get(src_pxs)

        # Set array to 3d
        dest_pxs.shape = (-1, dest.size[0], 4)
        src_pxs.shape = (-1, src.size[0], 4)

        # Copy to selected channel
        #dest_pxs[dest_idx::4] = src_pxs[src_idx::4]
        dest_pxs[start_y:start_y+height, start_x:start_x+width][::, ::, dest_idx] = src_pxs[src_start_y:src_start_y+height, src_start_x:src_start_x+width][::, ::, src_idx]
        dest.pixels.foreach_set(dest_pxs.ravel())

    else:
        # Get image pixels
        src_pxs = list(src.pixels)
        dest_pxs = list(dest.pixels)

        # Copy to selected channel
        for y in range(height):
            source_offset_y = width * 4 * (y + src_start_y)
            offset_y = dest.size[0] * 4 * (y + start_y)
            for x in range(width):
                source_offset_x = 4 * (x + src_start_x)
                offset_x = 4 * (x + start_x)
                dest_pxs[offset_y + offset_x + dest_idx] = src_pxs[source_offset_y + source_offset_x + src_idx]

        dest.pixels = dest_pxs

def copy_image_pixels(src, dest, segment=None, segment_src=None):

    start_x = 0
    start_y = 0

    src_start_x = 0
    src_start_y = 0

    width = src.size[0]
    height = src.size[1]

    if segment:
        start_x = width * segment.tile_x
        start_y = height * segment.tile_y

    if segment_src:
        width = segment_src.width
        height = segment_src.height

        src_start_x = width * segment_src.tile_x
        src_start_y = height * segment_src.tile_y

    if is_greater_than_283():
        target_pxs = numpy.empty(shape=dest.size[0]*dest.size[1]*4, dtype=numpy.float32)
        source_pxs = numpy.empty(shape=src.size[0]*src.size[1]*4, dtype=numpy.float32)
        dest.pixels.foreach_get(target_pxs)
        src.pixels.foreach_get(source_pxs)

        # Set array to 3d
        target_pxs.shape = (-1, dest.size[0], 4)
        source_pxs.shape = (-1, src.size[0], 4)

        target_pxs[start_y:start_y+height, start_x:start_x+width] = source_pxs[src_start_y:src_start_y+height, src_start_x:src_start_x+width]

        dest.pixels.foreach_set(target_pxs.ravel())

    else:
        target_pxs = list(dest.pixels)
        source_pxs = list(src.pixels)

        for y in range(height):
            source_offset_y = src.size[0] * 4 * (y + src_start_y)
            offset_y = dest.size[0] * 4 * (y + start_y)
            for x in range(width):
                source_offset_x = 4 * (x + src_start_x)
                offset_x = 4 * (x + start_x)
                for i in range(4):
                    target_pxs[offset_y + offset_x + i] = source_pxs[source_offset_y + source_offset_x + i]

        dest.pixels = target_pxs

def set_image_pixels(image, color, segment=None):

    start_x = 0
    start_y = 0

    width = image.size[0]
    height = image.size[1]

    if segment:
        start_x = width * segment.tile_x
        start_y = height * segment.tile_y

        width = segment.width
        height = segment.height

    if is_greater_than_283():
        pxs = numpy.empty(shape=image.size[0]*image.size[1]*4, dtype=numpy.float32)
        image.pixels.foreach_get(pxs)

        # Set array to 3d
        pxs.shape = (-1, image.size[0], 4)

        pxs[start_y:start_y+height, start_x:start_x+width] = color
        image.pixels.foreach_set(pxs.ravel())

    else:
        pxs = list(image.pixels)

        for y in range(height):
            source_offset_y = width * 4 * y
            offset_y = image.size[0] * 4 * (y + start_y)
            for x in range(width):
                source_offset_x = 4 * x
                offset_x = 4 * (x + start_x)
                for i in range(4):
                    pxs[offset_y + offset_x + i] = color[i]

        image.pixels = pxs

def is_image_filepath_unique(image):
    abspath = bpy.path.abspath(image.filepath)
    for img in bpy.data.images:
        if img != image and bpy.path.abspath(img.filepath) == abspath:
            return False
    return True

def duplicate_image(image):
    # Make sure UDIM image is updated
    if image.source == 'TILED' and image.is_dirty:
        if image.packed_file:
            image.pack()
        else: image.save()

    # Get new name
    new_name = get_unique_name(image.name, bpy.data.images)

    # Copy image
    new_image = image.copy()
    new_image.name = new_name

    if image.source == 'TILED'  or (not image.packed_file and image.filepath != ''):

        # NOTE: Duplicated image will always be packed for now
        if not image.packed_file:
            if is_greater_than_280():
                new_image.pack()
            else: new_image.pack(as_png=True)

        directory = os.path.dirname(bpy.path.abspath(image.filepath))
        filename = bpy.path.basename(new_image.filepath)

        # Get base name
        if image.source == 'TILED':
            splits = filename.split('.<UDIM>.')
            infix = '.<UDIM>.'
        else: 
            splits = os.path.splitext(filename)
            infix = ''

        basename = new_name
        extension = splits[1]

        # Try to get the counter
        m = re.match(r'^(.+)\s(\d*)$', basename)
        if m:
            basename = m.group(1)
            counter = int(m.group(2))
        else: counter = 1

        # Try to set the image filepath with added counter
        while True:
            new_name = basename + ' ' + str(counter)
            new_path = os.path.join(directory, new_name + infix + extension)
            new_image.filepath = new_path
            if is_image_filepath_unique(new_image):
                break
            counter += 1

        # Trying to set the filepath to relative
        try: new_image.filepath = bpy.path.relpath(new_image.filepath)
        except: pass

    # Copied image is not updated by default if it's dirty,
    # So copy the pixels
    if new_image.source != 'TILED':
        new_image.pixels = list(image.pixels)

    return new_image

def is_valid_bsdf_node(node, valid_types=[]):
    if not valid_types:
        return node.type == 'EMISSION' or node.type.startswith('BSDF_') or node.type.endswith('_SHADER')
    
    return node.type in valid_types

def get_closest_yp_node_backward(node):
    for inp in node.inputs:
        for link in inp.links:
            n = link.from_node
            if n.type == 'GROUP' and n.node_tree and n.node_tree.yp.is_ypaint_node:
                return n
            else:
                n = get_closest_yp_node_backward(n)
                if n: return n

    return None

def get_closest_bsdf_backward(node, valid_types=[]):
    for inp in node.inputs:
        for link in inp.links:
            if is_valid_bsdf_node(link.from_node, valid_types):
                return link.from_node
            else:
                n = get_closest_bsdf_backward(link.from_node, valid_types)
                if n: return n

    return None

def get_closest_bsdf_forward(node, valid_types=[]):
    for outp in node.outputs:
        for link in outp.links:
            if is_valid_bsdf_node(link.to_node, valid_types):
                return link.to_node
            else:
                n = get_closest_bsdf_forward(link.to_node, valid_types)
                if n: return n

    return None

