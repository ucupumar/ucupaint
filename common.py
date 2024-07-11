import bpy, os, sys, re, time, numpy, math
from mathutils import *
from bpy.app.handlers import persistent
from bpy_types import bpy_types

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
	             ("LINEAR_LIGHT", "Linear Light", ""),
	             ("DODGE", "Dodge", ""),
	             ("BURN", "Burn", ""))


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
	             ("LINEAR_LIGHT", "Linear Light", ""),
	             ("DODGE", "Dodge", ""),
	             ("BURN", "Burn", ""))

voronoi_feature_items = (("F1", "F1", "Compute and return the distance to the closest feature point as well as its position and color"),
	             ("F2", "F2", "Compute and return the distance to the second closest feature point as well as its position and color."),
	             ("SMOOTH_F1", "Smooth F1", "Compute and return a smooth version of F1."), 
	             ("DISTANCE_TO_EDGE", "Distance to Edge", "Compute and return the distance to the edges of the Voronoi cells."), 
	             ("N_SPHERE_RADIUS", "N-Sphere Radius", "Compute and return the radius of the n-sphere inscribed in the Voronoi cells. In other words, it is half the distance between the closest feature point and the feature point closest to it."))

def entity_input_items(self, context):
    yp = self.id_data.yp
    entity = self

    m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', entity.path_from_id())
    if m: entity = yp.layers[int(m.group(1))]

    items = []

    if entity.type not in layer_type_labels:
        items.append(('RGB', 'RGB',  ''))
        items.append(('ALPHA', 'Alpha',  ''))
    else:
        label = layer_type_labels[entity.type]

        if is_greater_than_281() and entity.type == 'VORONOI':
            items.append(('RGB', label + ' Color',  ''))
            items.append(('ALPHA', label + ' Distance',  ''))
        elif entity.type == 'VCOL':
            items.append(('RGB', label,  ''))
            items.append(('ALPHA', label + ' Alpha',  ''))
        elif entity.type == 'IMAGE':
            items.append(('RGB', label + ' Color',  ''))
            items.append(('ALPHA', label + ' Alpha',  ''))
        else:
            items.append(('RGB', label + ' Color',  ''))
            items.append(('ALPHA', label + ' Factor',  ''))
        
    return items

COLORID_TOLERANCE = 0.003906 # 1/256

TEMP_UV = '~TL Temp Paint UV'

TANGENT_SIGN_PREFIX = '__tsign_'

neighbor_directions = ['n', 's', 'e', 'w']

normal_blend_items = (
        ('MIX', 'Mix', ''),
        #('VECTOR_MIX', 'Vector Mix', ''),
        ('OVERLAY', 'Add', ''),
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
        ('COLOR_ID', 'Color ID', ''),
        ('BACKFACE', 'Backface', ''),
        ('EDGE_DETECT', 'Edge Detect', ''),
        ('MODIFIER', 'Modifier', ''),
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

channel_override_type_items_410 = (
        ('DEFAULT', 'Default', ''),
        ('IMAGE', 'Image', ''),
        ('BRICK', 'Brick', ''),
        ('CHECKER', 'Checker', ''),
        ('GRADIENT', 'Gradient', ''),
        ('MAGIC', 'Magic', ''),
        ('NOISE', 'Noise', ''),
        ('VORONOI', 'Voronoi', ''),
        ('WAVE', 'Wave', ''),
        ('VCOL', 'Vertex Color', ''),
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

interpolation_type_items = (
        ('Linear', 'Linear', 'Linear interpolation.'),
        ('Closest', 'Closest', 'No interpolation (sample closest texel).'),
        ('Cubic', 'Cubic', 'Cubic interpolation.'),
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
        'BACKFACE' : 'ShaderNodeNewGeometry',
        'EDGE_DETECT' : 'ShaderNodeGroup',
        }

io_suffix = {
        'GROUP' : ' Group',
        'BACKGROUND' : ' Background',
        'ALPHA' : ' Alpha',
        'DISPLACEMENT' : ' Displacement',
        'HEIGHT' : ' Height',
        'MAX_HEIGHT' : ' Max Height',
        'VDISP' : ' Vector Displacement',
        'HEIGHT_ONS' : ' Height ONS',
        'HEIGHT_EW' : ' Height EW',
        'UV' : ' UV',
        'TANGENT' : ' Tangent',
        'BITANGENT' : ' Bitangent',
        'HEIGHT_N' : ' Height N',
        'HEIGHT_S' : ' Height S',
        'HEIGHT_E' : ' Height E',
        'HEIGHT_W' : ' Height W',
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

eraser_names = {
        'TEXTURE_PAINT' : 'Eraser Tex',
        'VERTEX_PAINT' : 'Eraser Vcol',
        'SCULPT' : 'Eraser Paint',
        }

rgba_letters = ['r', 'g', 'b', 'a']
nsew_letters = ['n', 's', 'e', 'w']

TEXCOORD_IO_PREFIX = 'Texcoord '
PARALLAX_MIX_PREFIX = 'Parallax Mix '
PARALLAX_DELTA_PREFIX = 'Parallax Delta '
PARALLAX_CURRENT_PREFIX = 'Parallax Current '
PARALLAX_CURRENT_MIX_PREFIX = 'Parallax Current Mix '

GAMMA = 2.2

def versiontuple(v):
    return tuple(map(int, (v.split("."))))

def get_manifest():
    import toml
    # Load manifest file
    with open(get_addon_filepath() + 'blender_manifest.toml', 'r') as f:
        manifest = toml.load(f)
    return manifest

def get_addon_name():
    return os.path.basename(os.path.dirname(bpy.path.abspath(__file__)))

def get_addon_title():
    if not is_greater_than_420():
        bl_info = sys.modules[get_addon_name()].bl_info
        return bl_info['name']

    manifest = get_manifest()
    return manifest['name']

def get_addon_warning():
    if not is_greater_than_420():
        bl_info = sys.modules[get_addon_name()].bl_info
        return bl_info['warning']

    return ''

def get_alpha_suffix():
    if not is_greater_than_420():
        bl_info = sys.modules[get_addon_name()].bl_info
        if 'Alpha' in bl_info['warning']:
            return ' Alpha'
        elif 'Beta' in bl_info['warning']:
            return ' Beta'

    return ''

def get_current_version_str():
    if not is_greater_than_420():
        bl_info = sys.modules[get_addon_name()].bl_info
        return str(bl_info['version']).replace(', ', '.').replace('(','').replace(')','')

    manifest = get_manifest()
    return manifest['version']

def get_current_blender_version_str():
    return str(bpy.app.version).replace(', ', '.').replace('(','').replace(')','')

def get_current_version():
    if not is_greater_than_420():
        bl_info = sys.modules[get_addon_name()].bl_info
        return bl_info['version']

    manifest = get_manifest()
    return tuple(map(int, manifest['version'].split('.')))

def is_online():
    return not is_greater_than_420() or bpy.app.online_access

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

def is_greater_than_290():
    if bpy.app.version >= (2, 90, 0):
        return True
    return False

def is_greater_than_292():
    if bpy.app.version >= (2, 92, 0):
        return True
    return False

def is_greater_than_293():
    if bpy.app.version >= (2, 93, 0):
        return True
    return False

def is_greater_than_300():
    if bpy.app.version >= (3, 0, 0):
        return True
    return False

def is_greater_than_310():
    if bpy.app.version >= (3, 1, 0):
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

def is_greater_than_410():
    if bpy.app.version >= (4, 1, 0):
        return True
    return False

def is_greater_than_420():
    if bpy.app.version >= (4, 2, 0):
        return True
    return False

def is_created_using_279():
    if bpy.data.version[:2] == (2, 79):
        return True
    return False

def is_created_before_290():
    if bpy.data.version[:2] < (2, 90):
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

def is_created_before_410():
    if bpy.data.version < (4, 1, 0):
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

def remove_mesh_obj(obj):
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.meshes.remove(data)  

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

def get_active_material(obj=None):
    scene = bpy.context.scene
    engine = scene.render.engine

    if not obj:
        if hasattr(bpy.context, 'object'):
            obj = bpy.context.object
        elif is_greater_than_280():
            obj = bpy.context.view_layer.objects.active

    if not obj: return None

    mat = obj.active_material

    if engine in {'BLENDER_RENDER', 'BLENDER_GAME'}:
        return None

    return mat

def get_material_output(mat):
    if mat != None and mat.node_tree:
        output = [n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output]
        if output: return output[0]
    return None

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

def copy_id_props(source, dest, extras = [], reverse=False):
    props = dir(source)
    filters = ['bl_rna', 'rna_type']
    filters.extend(extras)

    if reverse: props.reverse()

    for prop in props:
        if prop.startswith('__'): continue
        if prop in filters: continue
        #if hasattr(prop, 'is_readonly'): continue
        try: val = getattr(source, prop)
        except:
            print('Error prop:', prop)
            continue
        attr_type = type(val)

        if 'bpy_prop_collection_idprop' in str(attr_type):
            dest_val = getattr(dest, prop)
            for subval in val:
                dest_subval = dest_val.add()
                copy_id_props(subval, dest_subval, reverse=reverse)

        elif attr_type == bpy_types.bpy_prop_collection:
            dest_val = getattr(dest, prop)
            for i, subval in enumerate(val):
                dest_subval = None

                if hasattr(dest_val, 'new'):
                    dest_subval = dest_val.new()

                if not dest_subval:
                    try: dest_subval = dest_val[i]
                    except: print('Error bpy_prop_collection get by index:', prop)

                if dest_subval:
                    copy_id_props(subval, dest_subval, reverse=reverse)

        elif attr_type == bpy_types.bpy_prop_array:
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
        attr_type = type(val)
        if 'bpy_func' in str(attr_type): continue
        #if 'bpy_prop' in attr_type: continue
        #print(prop, str(type(getattr(source, prop))))
        # Copy stuff here

        #if 'bpy_prop_collection_idprop' in str(attr_type):
        #    dest_val = getattr(dest, prop)
        #    for subval in val:
        #        dest_subval = dest_val.add()
        #        copy_id_props(subval, dest_subval)

        if attr_type == bpy_types.bpy_prop_array:
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

def copy_node_props(source, dest, extras=[]):
    if source.type != dest.type: return

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
        if i >= len(dest.inputs) or dest.inputs[i].name != inp.name: continue
        socket_name = source.inputs[i].name
        if socket_name in dest.inputs and dest.inputs[i].name == socket_name and dest.inputs[i].bl_idname not in {'NodeSocketVirtual'}:
            try: dest.inputs[i].default_value = inp.default_value
            except Exception as e: print(e)

    # Copy outputs default value
    for i, outp in enumerate(source.outputs):
        if i >= len(dest.outputs) or dest.outputs[i].bl_idname in {'NodeSocketVirtual'} or dest.outputs[i].name != outp.name: continue
        try: dest.outputs[i].default_value = outp.default_value 
        except Exception as e: print(e)

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
    ypwm = context.window_manager.ypprops
    area_index = ypwm.edit_image_editor_area_index
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

def get_active_paint_slot_image():
    scene = bpy.context.scene
    image = None
    if scene.tool_settings.image_paint.mode == 'IMAGE':
        image = scene.tool_settings.image_paint.canvas
    else:
        mat = get_active_material()
        if len(mat.texture_paint_images):
            image = mat.texture_paint_images[mat.paint_active_slot]

    return image

def set_image_paint_canvas(image):
    scene = bpy.context.scene
    try:
        scene.tool_settings.image_paint.mode = 'IMAGE'
        scene.tool_settings.image_paint.canvas = image
    except Exception as e: print(e)

# Check if name already available on the list
def get_unique_name(name, items, surname = ''):

    # Check if items is list of strings
    if len(items) > 0 and type(items[0]) == str:
        item_names = items
    else: item_names = [item.name for item in items]

    if surname != '':
        unique_name = name + ' ' + surname
    else: unique_name = name

    name_found = [item for item in item_names if item == unique_name]
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

            name_found = [item for item in item_names if item == new_name]
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

def get_active_ypaint_node(obj=None):
    ypui = bpy.context.window_manager.ypui

    # Get material UI prop
    mat = get_active_material(obj)
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

def safe_remove_image(image, yp_tree=None):
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

    dirty = False

    if not hasattr(entity, prop): return dirty
    if not tree: return dirty
    #if prop not in entity: return dirty

    scene = bpy.context.scene
    node = tree.nodes.get(getattr(entity, prop))
    #node = tree.nodes.get(entity[prop])

    if node: 

        dirty = True

        yp_tree = entity.id_data

        if parent and node.parent != parent:
            setattr(entity, prop, '')
            return dirty

        if remove_data:
            # Remove image data if the node is the only user
            if node.bl_idname == 'ShaderNodeTexImage':

                image = node.image
                if image: safe_remove_image(image, yp_tree)

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
                                if m and m.node_tree and is_vcol_being_used(m.node_tree, vcol_name, node):
                                    other_users_found = True
                                    break
                            if not other_users_found:
                                vc = vcols.get(vcol_name)
                                if vc: vcols.remove(vc)

        # Remove the node itself
        #print('Node ' + prop + ' from ' + str(entity) + ' removed!')
        tree.nodes.remove(node)
        dirty = True

    setattr(entity, prop, '')
    #entity[prop] = ''

    return dirty

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
        tree = get_tree(layer)
        baked_source = tree.nodes.get(layer.baked_source)
        if layer.use_baked and baked_source and baked_source.image:
            image = baked_source.image
            if ((image.yia.is_image_atlas and any([s for s in image.yia.segments if s == segment]) and segment.name == layer.baked_segment_name) or
                (image.yua.is_udim_atlas and any([s for s in image.yua.segments if s == segment]) and segment.name == layer.baked_segment_name)
                ):
                ids.append(i)
                continue

        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            if source and source.image:
                image = source.image
                if ((image.yia.is_image_atlas and any([s for s in image.yia.segments if s == segment]) and segment.name == layer.segment_name) or
                    (image.yua.is_udim_atlas and any([s for s in image.yua.segments if s == segment]) and segment.name == layer.segment_name)
                    ):
                    ids.append(i)
                    continue

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

        tree = get_mask_tree(m)
        baked_source = tree.nodes.get(m.baked_source)
        if m.use_baked and baked_source and baked_source.image:
            image = baked_source.image
            if ((image.yia.is_image_atlas and any([s for s in image.yia.segments if s == segment]) and segment.name == m.baked_segment_name) or
                (image.yua.is_udim_atlas and any([s for s in image.yua.segments if s == segment]) and segment.name == m.baked_segment_name)
                ):
                masks.append(m)
                continue

        if m.type == 'IMAGE':
            source = get_mask_source(m)
            if source and source.image:
                image = source.image
                if ((image.yia.is_image_atlas and any([s for s in image.yia.segments if s == segment]) and segment.name == m.segment_name) or
                    (image.yua.is_udim_atlas and any([s for s in image.yua.segments if s == segment]) and segment.name == m.segment_name)
                    ):
                    masks.append(m)
                    continue

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

    if node.type == 'GROUP' and not node.node_tree: return

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

    addon_link = 'github.com/ucupumar/ucupaint'

    if tree_type == 'ROOT':
        info.label = 'Created using ' + get_addon_title() + ' ' + yp.version + ' (' + addon_link + ')'
        info.width = 620.0
    else:
        info.label = 'Part of ' + get_addon_title() + ' addon (' + addon_link + ')'
        info.width = 560.0

    info.use_custom_color = True
    info.color = (0.5, 0.5, 0.5)
    info.height = 60.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'WARNING: Do NOT edit this group manually!'
    info.use_custom_color = True
    info.color = (1.0, 0.5, 0.5)
    info.width = 450.0
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

            loc.y -= 80
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

                    # HACK: Remember links because sometime tree sockets are unlinked
                    from_nodes = []
                    from_sockets = []
                    to_sockets = []
                    for inp in node.inputs:
                        for l in inp.links:
                            from_nodes.append(l.from_node.name)
                            socket_index = [i for i, soc in enumerate(l.from_node.outputs) if soc == l.from_socket][0]
                            from_sockets.append(socket_index)
                            to_sockets.append(inp.name)

                    #print('FROM:', node.node_tree.name, len(node.inputs))

                    # Replace new node
                    node.node_tree = ng

                    #print('TO  :', node.node_tree.name, len(node.inputs))

                    # HACK: Recover the unlinkeds
                    for i, inp_name in enumerate(to_sockets):
                        inp = node.inputs.get(inp_name)
                        if not inp: continue
                        from_node = node_group.nodes.get(from_nodes[i])
                        if len(inp.links) == 0:
                            try: node_group.links.new(from_node.outputs[from_sockets[i]], inp)
                            except Exception as e: print(e)

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

def load_from_lib_blend(tree_name, filename):
    # Node groups necessary are in lib.blend
    filepath = get_addon_filepath() + filename

    # Load node groups
    lib_found = False
    with bpy.data.libraries.load(filepath) as (data_from, data_to):
        from_ngs = data_from.node_groups
        to_ngs = data_to.node_groups
        for ng in from_ngs:
            if ng == tree_name:
                to_ngs.append(ng)
                lib_found = True
                break

    return lib_found

def get_node_tree_lib(name):

    # Try to get from local lib first
    node_tree = bpy.data.node_groups.get(name)
    if node_tree: return node_tree

    # Load from library blend files
    lib_found = load_from_lib_blend(name, 'lib.blend')
    if not lib_found:
        lib_found = load_from_lib_blend(name, 'lib_281.blend')
    if not lib_found:
        lib_found = load_from_lib_blend(name, 'lib_282.blend')

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

def get_mask_source(mask, get_baked=False):
    tree = get_mask_tree(mask)
    if tree:
        if get_baked:
            return tree.nodes.get(mask.baked_source)
        return tree.nodes.get(mask.source)
    return None

def get_mask_mapping(mask, get_baked=False):
    tree = get_mask_tree(mask, True)
    return tree.nodes.get(mask.mapping) if not get_baked else tree.nodes.get(mask.baked_mapping)

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

def get_layer_source(layer, tree=None, get_baked=False):
    if not tree: tree = get_tree(layer)

    prop_name = 'source' if not get_baked else 'baked_source'

    source_tree = get_source_tree(layer, tree)
    if source_tree: return source_tree.nodes.get(getattr(layer, prop_name))
    if tree: return tree.nodes.get(getattr(layer, prop_name))

    return None

def get_layer_mapping(layer, get_baked=False):
    tree = get_tree(layer)
    return tree.nodes.get(layer.mapping) if not get_baked else tree.nodes.get(layer.baked_mapping)

def get_entity_source(entity, get_baked=False):

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: return get_layer_source(entity, get_baked)
    elif m2: return get_mask_source(entity, get_baked)

    return None

def get_entity_mapping(entity, get_baked=False):

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: return get_layer_mapping(entity, get_baked)
    elif m2: return get_mask_mapping(entity, get_baked)

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

    # HACK: Blender 3.2+ did not automatically update viewport after vertex color rename
    if is_greater_than_320():
        for o in objs:
            set_active_object(o)
            if o.mode == 'OBJECT':
                bpy.ops.object.mode_set(mode='SCULPT')
                bpy.ops.object.mode_set(mode='OBJECT')
            else:
                ori_mode = o.mode
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.mode_set(mode=ori_mode)

        set_active_object(obj)

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

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', layer.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', layer.path_from_id())
    if m1:
        group_tree = yp.id_data

        # Update node group label
        layer_group = group_tree.nodes.get(layer.group_node)
        layer_group.label = layer.name

        # Also update mask name if it's in certain pattern
        for mask in layer.masks:
            m = re.match(r'^Mask\s.*\((.+)\)$', mask.name)
            if m:
                old_layer_name = m.group(1)
                new_mask_name = mask.name.replace(old_layer_name, layer.name)
                if mask.type == 'IMAGE':
                    msrc = get_mask_source(mask)
                    if msrc.image: 
                        msrc.image.name = '___TEMP___'
                        msrc.image.name = get_unique_name(new_mask_name, bpy.data.images) 
                elif mask.type == 'VCOL':
                    msrc = get_mask_source(mask)
                    mask.name = '___TEMP___'
                    change_vcol_name(yp, obj, msrc, new_mask_name, mask)
                else:
                    mask.name = new_mask_name

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
    #for ch in yp.channels:
    #    if ch.type == 'NORMAL' and ch != root_ch:
    #        output_index += 1
    #    if ch == root_ch:
    #        break

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

def get_active_layer(yp):

    if yp.active_layer_index >= 0 and yp.active_layer_index < len(yp.layers):
        return yp.layers[yp.active_layer_index]

    return None

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
                if ch_idx == j and get_channel_enabled(c, t, yp.channels[ch_idx]):
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

    #res_x /= ch.bump_smooth_multiplier
    #res_y /= ch.bump_smooth_multiplier

    return res_x, res_y

def set_uv_neighbor_resolution(entity, uv_neighbor=None, source=None, use_baked=False):

    yp = entity.id_data.yp
    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())
    m3 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', entity.path_from_id())

    if m1: 
        layer = yp.layers[int(m1.group(1))]
        tree = get_tree(entity)
        if not source: source = get_layer_source(entity, get_baked=use_baked)
        entity_type = entity.type
        scale = entity.scale
    elif m2: 
        layer = yp.layers[int(m2.group(1))]
        tree = get_tree(layer)
        if not source: source = get_mask_source(entity, get_baked=use_baked)
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

def is_mapping_possible(entity_type):
    return entity_type not in {'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT', 'MODIFIER'} 

def clear_mapping(entity, use_baked=False):

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: mapping = get_layer_mapping(entity, use_baked)
    else: mapping = get_mask_mapping(entity, use_baked)

    if mapping:
        if is_greater_than_281():
            mapping.inputs[1].default_value = (0.0, 0.0, 0.0)
            mapping.inputs[2].default_value = (0.0, 0.0, 0.0)
            mapping.inputs[3].default_value = (1.0, 1.0, 1.0)
        else:
            mapping.translation = (0.0, 0.0, 0.0)
            mapping.rotation = (0.0, 0.0, 0.0)
            mapping.scale = (1.0, 1.0, 1.0)

def update_mapping(entity, use_baked=False):

    yp = entity.id_data.yp

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    # Get source
    layer = None
    mask = None
    if m1: 
        source = get_layer_source(entity, get_baked=use_baked)
        mapping = get_layer_mapping(entity, get_baked=use_baked)
        layer = entity
    elif m2: 
        source = get_mask_source(entity, get_baked=use_baked)
        mapping = get_mask_mapping(entity, get_baked=use_baked)
        layer = yp.layers[int(m2.group(1))]
        mask = entity
    else: return

    if not mapping: return

    segment_name = entity.segment_name if not use_baked else entity.baked_segment_name

    if use_baked:
        offset_x = offset_y = offset_z = 0.0
        scale_x = scale_y = scale_z = 1.0
    else:
        offset_x = entity.translation[0]
        offset_y = entity.translation[1]
        offset_z = entity.translation[2]

        scale_x = entity.scale[0]
        scale_y = entity.scale[1]
        scale_z = entity.scale[2]

    if (entity.type == 'IMAGE' or use_baked) and segment_name != '':

        # Atlas will only use point vector type for now
        mapping.vector_type = 'POINT'

        image = source.image
        if image.source == 'TILED':
            segment = image.yua.segments.get(segment_name)
            offset_y = get_udim_segment_mapping_offset(segment) 
        else:
            segment = image.yia.segments.get(segment_name)

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
        if hasattr(bpy.context, 'object') and bpy.context.object and bpy.context.object.mode == 'TEXTURE_PAINT':

            # Get active mask of layer
            active_mask = None
            for m in layer.masks:
                if m.active_edit:
                    active_mask = m

            # Only need to refersh if entity is the active one
            if not active_mask or (mask and active_mask == mask):
                yp.need_temp_uv_refresh = True

def is_active_uv_map_missmatch_entity(obj, entity):

    # Non image entity doesn't need matching UV
    if not entity.use_baked and entity.type != 'IMAGE':
        return False

    m = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())

    #if entity.type != 'IMAGE' or entity.texcoord_type != 'UV': return False
    if (m and not is_layer_using_vector(entity)) or entity.texcoord_type != 'UV': return False
    mapping = get_entity_mapping(entity, get_baked=entity.use_baked)

    uv_layers = get_uv_layers(obj)
    if not uv_layers: return False
    uv_layer = uv_layers.active

    uv_name = entity.uv_name if not entity.use_baked or entity.baked_uv_name == '' else entity.baked_uv_name

    if mapping and is_transformed(mapping) and obj.mode == 'TEXTURE_PAINT':
        if uv_layer.name != TEMP_UV:
            return True

    elif uv_name in uv_layers and uv_name != uv_layer.name:
        return True

    return False

def is_active_uv_map_missmatch_active_entity(obj, layer):

    active_mask = None
    for mask in layer.masks:
        if mask.active_edit == True:
            active_mask = mask

    if active_mask: entity = active_mask
    else: entity = layer

    return is_active_uv_map_missmatch_entity(obj, entity)

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
                try: uv_layers.remove(uv)
                except: print('EXCEPTIION: Cannot remove temp uv!')
                #break

    if not entity: 
        if uv_layers and len(uv_layers) > 0:
            try: uv_layers.active = uv_layers[0]
            except: print('EXCEPTIION: Cannot set active uv!')
        return

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
    layer_uv_name = layer.baked_uv_name if layer.use_baked and layer.baked_uv_name != '' else layer.uv_name
    layer_uv = uv_layers.get(layer_uv_name)

    if m1 or m3:
        entity_uv = layer_uv
    else:
        uv_name = entity.baked_uv_name if entity.use_baked and entity.baked_uv_name != '' else entity.uv_name
        entity_uv = uv_layers.get(uv_name)

        if not entity_uv: 
            entity_uv = layer_uv

    if not entity_uv: 
        return False

    # Set active uv
    if uv_layers.active != entity_uv:
        if uv_layers.active != entity_uv:
            try: uv_layers.active = entity_uv
            except: print('EXCEPTIION: Cannot set active uv!')
        if not entity_uv.active_render:
            try: entity_uv.active_render = True
            except: print('EXCEPTIION: Cannot set active uv render!')

    if m3 and entity.override_type != 'IMAGE':
        remove_temp_uv(obj, entity)
        return False

    if (m1 or m2) and (entity.type != 'IMAGE' and not entity.use_baked):
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
        if entity.use_baked:
            tree = get_tree(entity)
            source = tree.nodes.get(entity.baked_source)
        else:
            source = get_layer_source(entity)
        mapping = get_layer_mapping(entity, get_baked=entity.use_baked)
        #print('Layer!')
    elif m2: 
        if entity.use_baked:
            mask_tree = get_mask_tree(entity)
            source = mask_tree.nodes.get(entity.baked_source)
            layer_tree = get_mask_tree(entity, True)
        else:
            source = get_mask_source(entity)
        mapping = get_mask_mapping(entity, get_baked=entity.use_baked)
        #print('Mask!')
    elif m3: 
        source = layer_tree.nodes.get(entity.source)
        mapping = get_layer_mapping(layer)
        #print('Channel!')
    else: return False

    # Only point mapping are supported for now
    if mapping and mapping.vector_type not in {'POINT', 'TEXTURE'}:
        return False

    if not hasattr(source, 'image'): return False

    img = source.image
    if not img or not mapping or not is_transformed(mapping):
        return False

    set_active_object(obj)

    # Cannot do this on edit mode
    ori_mode = obj.mode
    if ori_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # New uv layers
    temp_uv_layer = uv_layers.new(name=TEMP_UV)
    uv_layers.active = temp_uv_layer
    temp_uv_layer.active_render = True

    if not is_greater_than_280():
        temp_uv_layer = obj.data.uv_layers.get(TEMP_UV)

    translation_x = mapping.inputs[1].default_value[0] if is_greater_than_281() else mapping.translation[0]
    translation_y = mapping.inputs[1].default_value[1] if is_greater_than_281() else mapping.translation[1]
    translation_z = mapping.inputs[1].default_value[2] if is_greater_than_281() else mapping.translation[2]

    rotation_x = mapping.inputs[2].default_value[0] if is_greater_than_281() else mapping.rotation[0]
    rotation_y = mapping.inputs[2].default_value[1] if is_greater_than_281() else mapping.rotation[1]
    rotation_z = mapping.inputs[2].default_value[2] if is_greater_than_281() else mapping.rotation[2]

    scale_x = mapping.inputs[3].default_value[0] if is_greater_than_281() else mapping.scale[0]
    scale_y = mapping.inputs[3].default_value[1] if is_greater_than_281() else mapping.scale[1]
    scale_z = mapping.inputs[3].default_value[2] if is_greater_than_281() else mapping.scale[2]

    # Create transformation matrix
    m1 = m2 = m3 = m4 = None
    if mapping.vector_type == 'POINT':

        # Scale
        m = Matrix((
            (scale_x, 0, 0),
            (0, scale_y, 0),
            (0, 0, scale_z)
            ))

        # Rotate
        m.rotate(Euler((rotation_x, rotation_y, rotation_z)))

        # Translate
        m = m.to_4x4()
        m[0][3] = translation_x
        m[1][3] = translation_y
        m[2][3] = translation_z

    elif mapping.vector_type == 'TEXTURE': 
        # Translate matrix
        m = Matrix((
            (1, 0, 0, -translation_x),
            (0, 1, 0, -translation_y),
            (0, 0, 1, -translation_z),
            (0, 0, 0, 1),
            ))

        # Rotate z matrix
        m1 = Matrix(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        m1.rotate(Euler((0, 0, -rotation_z)))

        # Rotate y matrix
        m2 = Matrix(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        m2.rotate(Euler((0, -rotation_y, 0)))

        # Rotate x matrix
        m3 = Matrix(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        m3.rotate(Euler((-rotation_x, 0, 0)))

        # Scale matrix
        m4 = Matrix((
            (1/scale_x, 0, 0),
            (0, 1/scale_y, 0),
            (0, 0, 1/scale_z)
            ))

    # Create numpy array to store uv coordinates
    arr = numpy.zeros(len(obj.data.loops)*2, dtype=numpy.float32)
    temp_uv_layer.data.foreach_get('uv', arr)
    arr.shape = (arr.shape[0]//2, 2)

    # Matrix transformation for each uv coordinates
    if is_greater_than_280():
        if mapping.vector_type == 'TEXTURE':
            for uv in arr:
                vec = Vector((uv[0], uv[1], 0.0)) #, 1.0))
                vec = m @ vec
                vec = m1 @ vec
                vec = m2 @ vec
                vec = m3 @ vec
                vec = m4 @ vec
                uv[0] = vec[0]
                uv[1] = vec[1]
        else:
            for uv in arr:
                vec = Vector((uv[0], uv[1], 0.0)) #, 1.0))
                vec = m @ vec
                uv[0] = vec[0]
                uv[1] = vec[1]
    else:
        if mapping.vector_type == 'TEXTURE':
            for uv in arr:
                vec = Vector((uv[0], uv[1], 0.0)) #, 1.0))
                vec = m * vec
                vec = m1 * vec
                vec = m2 * vec
                vec = m3 * vec
                vec = m4 * vec
                uv[0] = vec[0]
                uv[1] = vec[1]
        else:
            for uv in arr:
                vec = Vector((uv[0], uv[1], 0.0)) #, 1.0))
                vec = m * vec
                uv[0] = vec[0]
                uv[1] = vec[1]

    # Set back uv coordinates
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
    return None

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
        ##### REPLACED_BY_SHADERS

        bump_distance = ch.normal_bump_distance if ch.normal_map_type == 'NORMAL_MAP' else get_layer_channel_bump_distance(layer, ch)
        delta = get_transition_bump_max_distance(ch) - abs(bump_distance)

        #####

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
    tree = root_ch.id_data
    ch_index = get_channel_index(root_ch)

    #if layer and layer.parent_idx != -1:
    #    parent = get_parent(layer)
    #    layers = get_list_of_direct_childrens(parent)
    #    max_height = get_max_height_from_list_of_layers(layers, ch_index, layer, top_layers_only=False)
    #else:
    #    max_height = get_max_height_from_list_of_layers(yp.layers, ch_index, layer, top_layers_only=True)

    max_height = 1.0

    end_max_height = tree.nodes.get(root_ch.end_max_height)
    if end_max_height:
        max_height = end_max_height.outputs[0].default_value

    end_max_height_tweak = tree.nodes.get(root_ch.end_max_height_tweak)
    if end_max_height_tweak and 'Height Tweak' in end_max_height_tweak.inputs: 
        max_height *= end_max_height_tweak.inputs['Height Tweak'].default_value

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
    layer_node = layer.id_data.nodes.get(layer.group_node)

    height_proc = tree.nodes.get(height_ch.height_proc)
    if height_proc and layer.type != 'GROUP':

        #inp = layer_node.inputs.get(get_entity_input_name(height_ch, 'bump_distance'))
        #if inp: inp.default_value = height_ch.bump_distance

        #inp = layer_node.inputs.get(get_entity_input_name(height_ch, 'normal_bump_distance'))
        #if inp: inp.default_value = height_ch.normal_bump_distance

        #inp = layer_node.inputs.get(get_entity_input_name(height_ch, 'transition_bump_distance'))
        #if inp: inp.default_value = height_ch.transition_bump_distance

        if height_ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:

            ##### REPLACED_BY_SHADERS

            inp = height_proc.inputs.get('Value Max Height')
            if inp: inp.default_value = get_layer_channel_bump_distance(layer, height_ch)

            inp = height_proc.inputs.get('Transition Max Height')
            if inp: inp.default_value = get_transition_bump_max_distance(height_ch)

            #####

            ##### REPLACED_BY_SHADERS (PARTLY)

            inp = height_proc.inputs.get('Delta')
            if inp: inp.default_value = get_transition_disp_delta(layer, height_ch)

            #####

        elif height_ch.normal_map_type == 'NORMAL_MAP':

            ##### REPLACED_BY_SHADERS

            #inp = height_proc.inputs.get('Bump Height')
            #if inp:
            #    if height_ch.enable_transition_bump:
            #        inp.default_value = get_transition_bump_max_distance(height_ch)
            #    else: inp.default_value = height_ch.normal_bump_distance
            pass

            #####

    normal_proc = tree.nodes.get(height_ch.normal_proc)
    if normal_proc:

        max_height = get_displacement_max_height(height_root_ch, layer)

        #if height_root_ch.enable_smooth_bump: 
        #    inp = normal_proc.inputs.get('Bump Height Scale')
        #    if inp: inp.default_value = get_fine_bump_distance(max_height)

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

    if 'Max Height' in bump_process.inputs:
        bump_process.inputs['Max Height'].default_value = max_height

    #if height_root_ch.enable_smooth_bump:
    #    if 'Bump Height Scale' in bump_process.inputs:
    #        bump_process.inputs['Bump Height Scale'].default_value = get_fine_bump_distance(max_height)
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
        if 'Max Height' in end_linear.inputs:
            if max_height != 0.0:
                end_linear.inputs['Max Height'].default_value = max_height
            else: end_linear.inputs['Max Height'].default_value = 1.0

        #if root_ch.enable_smooth_bump and 'Bump Height Scale' in end_linear.inputs:
        #    end_linear.inputs['Bump Height Scale'].default_value = get_fine_bump_distance(max_height)

    #end_max_height = group_tree.nodes.get(root_ch.end_max_height)
    #if end_max_height:
    #    if max_height != 0.0:
    #        end_max_height.outputs[0].default_value = max_height
    #    else: end_max_height.outputs[0].default_value = 1.0

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

def get_multires_modifier(obj, keyword='', include_hidden=False):
    for mod in obj.modifiers:
        if mod.type == 'MULTIRES' and mod.total_levels > 0 and (mod.show_viewport or include_hidden):
            if keyword != '' and keyword != mod.name: continue
            return mod

    return None

def update_layer_images_interpolation(layer, interpolation='Linear', from_interpolation = ''):
    if layer.type == 'IMAGE':
        source = get_layer_source(layer)
        if source and source.image: 
            if from_interpolation == '' or source.interpolation == from_interpolation:
                source.interpolation = interpolation

        baked_source = get_layer_source(layer, get_baked=True)
        if baked_source and baked_source.image: 
            if from_interpolation == '' or baked_source.interpolation == from_interpolation:
                baked_source.interpolation = interpolation

    height_ch = get_height_channel(layer)
    if height_ch:
        source = get_channel_source(height_ch, layer)
        if source and source.bl_idname == 'ShaderNodeTexImage' and source.image: 
            if from_interpolation == '' or source.interpolation == from_interpolation:
                source.interpolation = interpolation

    for mask in layer.masks:
        if mask.type == 'IMAGE':
            source = get_mask_source(mask)
            if source and source.image: 
                if from_interpolation == '' or source.interpolation == from_interpolation:
                    source.interpolation = interpolation

        baked_source = get_mask_source(mask, get_baked=True)
        if baked_source and baked_source.image: 
            if from_interpolation == '' or baked_source.interpolation == from_interpolation:
                baked_source.interpolation = interpolation

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

def get_vertex_color_names_from_geonodes(obj):
    vcol_names = []

    for mod in obj.modifiers:
        if mod.type == 'NODES' and mod.node_group:
            outputs = get_tree_outputs(mod.node_group)
            for outp in outputs:
                if ((is_greater_than_400() and outp.socket_type == 'NodeSocketColor') or
                    (not is_greater_than_400() and outp.type == 'RGBA')):
                    name = mod[outp.identifier + '_attribute_name']
                    if name != '' and name not in vcol_names:
                        vcol_names.append(name)

    return vcol_names

def get_vertex_color_names(obj):
    if not obj: return []

    vcol_names = []

    # Check vertex colors / color attributes
    if not is_greater_than_320():
        if hasattr(obj.data, 'vertex_colors'):
            vcol_names = [v.name for v in obj.data.vertex_colors]
    else:
        if hasattr(obj.data, 'color_attributes'):
            vcol_names = [v.name for v in obj.data.color_attributes]

    # Check geometry nodes outputs
    vcol_names.extend(get_vertex_color_names_from_geonodes(obj))

    return vcol_names

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
                if obj.data.vertex_colors.active != v:
                    obj.data.vertex_colors.active = v
        else: 
            if obj.data.vertex_colors.active != vcol:
                obj.data.vertex_colors.active = vcol
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
    except: return ''

    uv_name = layer.baked_uv_name if layer.use_baked and layer.baked_uv_name != '' else layer.uv_name

    for mask in layer.masks:
        if mask.active_edit:
            if is_mask_using_vector(mask):
                active_mask = mask
                uv_name = mask.baked_uv_name if mask.use_baked and mask.baked_uv_name != '' else mask.uv_name

    return uv_name 

def set_active_paint_slot_entity(yp):
    image = None
    mat = get_active_material()
    node = get_active_ypaint_node()
    scene = bpy.context.scene
    root_tree = yp.id_data

    # Set material active node 
    node.select = True
    mat.node_tree.nodes.active = node

    if yp.use_baked and len(yp.channels) > 0:

        ch = yp.channels[yp.active_channel_index]
        baked = root_tree.nodes.get(ch.baked)
        if baked and baked.image:
            if ch.type == 'NORMAL':
                baked_disp = root_tree.nodes.get(ch.baked_disp)
                baked_normal_overlay = root_tree.nodes.get(ch.baked_normal_overlay)

                cur_image = get_active_paint_slot_image()

                if cur_image == baked.image and baked_disp:
                    baked_disp.select = True
                    root_tree.nodes.active = baked_disp
                    image = baked_disp.image
                elif baked_disp and cur_image == baked_disp.image and baked_normal_overlay:
                    baked_normal_overlay.select = True
                    root_tree.nodes.active = baked_normal_overlay
                    image = baked_normal_overlay.image
                else:
                    baked.select = True
                    root_tree.nodes.active = baked
                    image = baked.image

            else:
                baked.select = True
                root_tree.nodes.active = baked
                image = baked.image

    elif len(yp.layers) > 0:
        
        # Get layer tree
        layer = yp.layers[yp.active_layer_index]
        tree = get_tree(layer)

        # Set layer node tree as active
        layer_node = root_tree.nodes.get(layer.group_node)
        layer_node.select = True
        root_tree.nodes.active = layer_node
        layer_tree = layer_node.node_tree

        for mask in layer.masks:
            if mask.active_edit:
                source = get_mask_source(mask)
                baked_source = get_mask_source(mask, get_baked=True)

                if mask.type == 'IMAGE' or (mask.use_baked and baked_source):

                    if mask.use_baked and baked_source:
                        source = baked_source 

                    if mask.group_node != '':
                        mask_node = layer_tree.nodes.get(mask.group_node)
                        mask_node.select = True
                        layer_tree.nodes.active = mask_node

                        mask_tree = mask_node.node_tree
                        source.select = True
                        mask_tree.nodes.active = source
                    else:
                        source.select = True
                        layer_tree.nodes.active = source

                    image = source.image

        for ch in layer.channels:
            if ch.active_edit and ch.override and ch.override_type != 'DEFAULT' and ch.override_type == 'IMAGE':
                source = get_channel_source(ch, layer)

                if ch.source_group != '':
                    source_group = layer_tree.nodes.get(ch.source_group)
                    source_group.select = True
                    layer_tree.nodes.active = source_group

                    ch_tree = source_group.node_tree
                    source.select = True
                    ch_tree.nodes.active = source

                else:
                    source.select = True
                    layer_tree.nodes.active = source

                image = source.image

            if ch.active_edit_1 and ch.override_1 and ch.override_1_type != 'DEFAULT' and ch.override_1_type == 'IMAGE':
                source = tree.nodes.get(ch.source_1)
                source.select = True
                layer_tree.nodes.active = source
                image = source.image

        if not image:
            source = get_layer_source(layer, tree)
            baked_source = get_layer_source(layer, get_baked=True)

            if layer.type == 'IMAGE' or (layer.use_baked and baked_source):
                if layer.use_baked and baked_source:
                    source = baked_source 

                if layer.source_group != '':
                    source_group = layer_tree.nodes.get(layer.source_group)
                    source_group.select = True
                    layer_tree.nodes.active = source_group

                    source_tree = source_group.node_tree
                    source.select = True
                    source_tree.nodes.active = source
                else:
                    source.select = True
                    layer_tree.nodes.active = source

                image = source.image

    if image and is_greater_than_281():

        scene.tool_settings.image_paint.mode = 'MATERIAL'

        for idx, img in enumerate(mat.texture_paint_images):
            if img == None: continue
            if img.name == image.name:
                mat.paint_active_slot = idx
                break

    else:
        scene.tool_settings.image_paint.mode = 'IMAGE'
        scene.tool_settings.image_paint.canvas = image

    update_image_editor_image(bpy.context, image)

def get_active_image_and_stuffs(obj, yp):

    image = None
    uv_name = ''
    vcol = None
    src_of_img = None
    entity = None
    mapping = None

    vcols = get_vertex_colors(obj)

    layer = yp.layers[yp.active_layer_index]
    tree = get_tree(layer)

    for mask in layer.masks:
        if mask.active_edit:
            source = get_mask_source(mask)
            baked_source = get_mask_source(mask, get_baked=True)

            uv_name = mask.uv_name if not mask.use_baked or mask.baked_uv_name == '' else mask.baked_uv_name
            mapping = get_mask_mapping(mask, get_baked=mask.use_baked)
            entity = mask

            if mask.use_baked and baked_source:
                if baked_source.image:
                    image = baked_source.image
                    src_of_img = mask
            elif mask.type == 'IMAGE':
                image = source.image
                src_of_img = mask
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
            entity = ch

            if ch.override_type == 'IMAGE':
                uv_name = layer.uv_name
                image = source.image
                src_of_img = ch
                mapping = get_layer_mapping(layer)

            elif ch.override_type == 'VCOL' and obj.type == 'MESH':
                vcol = vcols.get(get_source_vcol_name(source))

        if ch.active_edit_1 and ch.override_1 and ch.override_1_type != 'DEFAULT':
            source = tree.nodes.get(ch.source_1)
            entity = ch

            if ch.override_1_type == 'IMAGE':
                uv_name = layer.uv_name
                source_1 = get_channel_source_1(ch)
                image = source_1.image
                src_of_img = ch
                mapping = get_layer_mapping(layer)

    if not entity: 
        entity = layer

    if not image and layer.type == 'IMAGE':
        uv_name = layer.uv_name
        source = get_layer_source(layer, tree)
        image = source.image
        src_of_img = layer
        mapping = get_layer_mapping(layer)

    if not vcol and layer.type == 'VCOL' and obj.type == 'MESH':
        source = get_layer_source(layer, tree)
        vcol = vcols.get(get_source_vcol_name(source))

    return image, uv_name, src_of_img, entity, mapping, vcol

def set_active_uv_layer(obj, uv_name):
    uv_layers = get_uv_layers(obj)

    for i, uv in enumerate(uv_layers):
        if uv.name == uv_name:
            if uv_layers.active_index != i:
                uv_layers.active_index = i

def is_uv_input_needed(layer, uv_name):
    yp = layer.id_data.yp

    if get_layer_enabled(layer):

        if layer.baked_source != '' and layer.use_baked and layer.baked_uv_name == uv_name:
            return True

            if layer.texcoord_type == 'UV' and layer.uv_name == uv_name:
                return True

        if layer.texcoord_type == 'UV' and layer.uv_name == uv_name:
            if layer.type not in {'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI'}:
                return True

            for i, ch in enumerate(layer.channels):
                if not ch.enable: continue
                root_ch = yp.channels[i]
                if root_ch.type != 'NORMAL':
                    if ch.override and ch.override_type not in {'DEFAULT', 'VCOL'}:
                        return True
                else:
                    if ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'} and ch.override and ch.override_type not in {'DEFAULT', 'VCOL'}:
                        return True

                    if ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'} and ch.override_1 and ch.override_1_type != 'DEFAULT':
                        return True
        
        for mask in layer.masks:
            if not get_mask_enabled(mask): continue
            if mask.use_baked and mask.baked_source != '' and mask.baked_uv_name == uv_name:
                return True
            if mask.type in {'VCOL', 'HEMI', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE', 'EDGE_DETECT'}: continue
            if (not mask.use_baked or mask.baked_source == '') and mask.texcoord_type == 'UV' and mask.uv_name == uv_name:
                return True

    return False

def is_entity_need_tangent_input(entity, uv_name):
    yp = entity.id_data.yp

    m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', entity.path_from_id())
    if m: 
        layer = yp.layers[int(m.group(1))]
        entity_enabled = get_mask_enabled(entity)
        is_mask = True
    else: 
        layer = entity
        entity_enabled = get_layer_enabled(entity)
        is_mask = False

    if entity_enabled and (entity.use_baked or entity.type not in {'BACKGROUND', 'COLOR', 'OBJECT_INDEX', 'COLOR_ID', 'BACKFACE'}):

        height_root_ch = get_root_height_channel(yp)
        height_ch = get_height_channel(layer)

        # Previous normal is calculated using normal process
        if height_root_ch and check_need_prev_normal(layer):
            return True

        if height_root_ch and height_ch and get_channel_enabled(height_ch, layer, height_root_ch):

            if entity.type == 'GROUP':

                if is_layer_using_normal_map(entity, height_root_ch):
                    return True

            elif uv_name == height_root_ch.main_uv:

                # Main UV tangent is needed for normal process
                if is_parallax_enabled(height_root_ch) and height_ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'} or yp.layer_preview_mode or not height_ch.write_height:
                    return True

                # Overlay blend and transition bump need tangent
                if height_ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'} and (height_ch.normal_blend_type == 'OVERLAY' or height_ch.enable_transition_bump):
                    return True

                # Main UV Tangent is needed if smooth bump is on and entity is using non-uv texcoord or have different UV
                if height_root_ch.enable_smooth_bump and (entity.texcoord_type != 'UV' or entity.uv_name != uv_name) and height_ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:
                    return True

                # Fake neighbor need tangent
                if height_root_ch.enable_smooth_bump and entity.type in {'VCOL', 'HEMI', 'EDGE_DETECT'} and not entity.use_baked:
                    return True

            elif entity.uv_name == uv_name and entity.texcoord_type == 'UV':

                # Entity UV tangent is needed if smooth bump is on and entity is using different UV than main UV
                if height_root_ch.enable_smooth_bump and height_root_ch.main_uv != uv_name and height_ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:
                    return True

    return False

def is_tangent_input_needed(layer, uv_name):

    if is_entity_need_tangent_input(layer, uv_name):
        return True

    for mask in layer.masks:
        if is_entity_need_tangent_input(mask, uv_name):
            return True

    return False

def is_tangent_process_needed(yp, uv_name):

    height_root_ch = get_root_height_channel(yp)
    if height_root_ch:

        if height_root_ch.main_uv == uv_name and (
                #(height_root_ch.enable_smooth_bump and any_layers_using_bump_map(height_root_ch)) or
                #(not height_root_ch.enable_smooth_bump and any_layers_using_bump_map(height_root_ch) and any_layers_using_normal_map(height_root_ch))
                any_layers_using_bump_map(height_root_ch) or
                (is_normal_height_input_connected(height_root_ch) and height_root_ch.enable_smooth_bump)
                ):
            return True

        for layer in yp.layers:
            if is_tangent_input_needed(layer, uv_name):
                return True

    return False

def is_height_process_needed(layer):
    yp = layer.id_data.yp
    height_root_ch = get_root_height_channel(yp)
    if not height_root_ch: return False

    height_ch = get_height_channel(layer)
    if not height_ch or not height_ch.enable: return False

    if yp.layer_preview_mode and height_ch.normal_map_type != 'VECTOR_DISPLACEMENT_MAP': return True

    if layer.type == 'GROUP': 
        if is_layer_using_bump_map(layer, height_root_ch):
            return True
    elif height_ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'} or height_ch.enable_transition_bump:
        return True

    return False

def is_normal_process_needed(layer):
    yp = layer.id_data.yp
    height_root_ch = get_root_height_channel(yp)
    if not height_root_ch: return False

    height_ch = get_height_channel(layer)
    if not height_ch or not height_ch.enable: return False

    if yp.layer_preview_mode and height_ch.normal_map_type != 'VECTOR_DISPLACEMENT_MAP': return True

    if layer.type == 'GROUP': 
        if is_layer_using_bump_map(layer, height_root_ch) and not height_ch.write_height:
            return True
    elif height_ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'} or not height_ch.write_height:
        return True

    return False

''' Check if layer is practically enabled or not '''
def get_layer_enabled(layer):
    yp = layer.id_data.yp

    # Check all parents enable
    parent_enable = True
    for parent_id in get_list_of_parent_ids(layer):
        parent = yp.layers[parent_id]
        if not parent.enable:
            parent_enable = False
            break

    # Check if no channel is enabled
    channel_enabled = False
    for ch in layer.channels:
        if ch.enable:
            channel_enabled = True
            break

    return layer.enable and parent_enable and channel_enabled
    #return (layer.enable and parent_enable) or yp.layer_preview_mode

''' Check if mask is practically enabled or not '''
def get_mask_enabled(mask, layer=None):
    if not layer:
        yp = mask.id_data.yp
        m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
        layer = yp.layers[int(m.group(1))]

    return get_layer_enabled(layer) and layer.enable_masks and mask.enable
    #return (get_layer_enabled(layer) and mask.enable) or yp.layer_preview_mode

''' Check if channel is practically enabled or not '''
def get_channel_enabled(ch, layer=None, root_ch=None):
    #print('Checking', layer.name, root_ch.name, "if it's enabled or not...")
    yp = ch.id_data.yp

    if not layer or not root_ch:
        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]', ch.path_from_id())
        layer = yp.layers[int(m.group(1))]
        root_ch = yp.channels[int(m.group(2))]

    if not get_layer_enabled(layer) or not ch.enable:
        return False

    channel_idx = get_channel_index(root_ch)

    if layer.type in {'BACKGROUND', 'GROUP'}:
        
        if layer.type == 'BACKGROUND':
            layer_idx = get_layer_index(layer)
            lays = [l for i, l in enumerate(yp.layers) if i > layer_idx and l.parent_idx == layer.parent_idx]
        else:
            lays = get_list_of_direct_childrens(layer)
        
        for l in lays:
            if not l.enable: continue
            if channel_idx >= len(l.channels): continue
            c = l.channels[channel_idx]

            if l.type not in {'GROUP', 'BACKGROUND'} and c.enable:
                return True

            if l.type == 'GROUP' and get_channel_enabled(l.channels[channel_idx], l, root_ch):
                return True

        return False

    else:
        for pid in get_list_of_parent_ids(layer):
            parent = yp.layers[pid]
            if len(parent.channels) > channel_idx and not parent.channels[channel_idx].enable:
                return False

    return True

def is_any_entity_using_uv(yp, uv_name):

    if yp.baked_uv_name != '' and yp.baked_uv_name == uv_name:
        return True

    for layer in yp.layers:
        if is_uv_input_needed(layer, uv_name):
            return True

    return False

def is_layer_using_bump_map(layer, root_ch=None):
    yp = layer.id_data.yp
    if not root_ch: root_ch = get_root_height_channel(yp)
    if not root_ch: return False

    channel_idx = get_channel_index(root_ch)
    try: ch = layer.channels[channel_idx]
    except: return False
    if get_channel_enabled(ch, layer, root_ch):
        if layer.type == 'GROUP':
            childs = get_list_of_direct_childrens(layer)
            for child in childs:
                if is_layer_using_bump_map(child):
                    return True
        elif ch.write_height and  (ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'} or ch.enable_transition_bump):
            return True

    return False

def is_layer_using_normal_map(layer, root_ch=None):
    yp = layer.id_data.yp
    if not root_ch: root_ch = get_root_height_channel(yp)
    if not root_ch: return False

    channel_idx = get_channel_index(root_ch)
    try: ch = layer.channels[channel_idx]
    except: return False
    if get_channel_enabled(ch, layer, root_ch):
        if layer.type == 'GROUP':
            childs = get_list_of_direct_childrens(layer)
            for child in childs:
                if is_layer_using_normal_map(child) or (not ch.write_height and is_layer_using_bump_map(child)):
                    return True
        elif not ch.write_height or ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'}:
            return True

    return False

def any_layers_using_bump_map(root_ch):
    if root_ch.type != 'NORMAL': return False
    yp = root_ch.id_data.yp

    for layer in yp.layers:
        if is_layer_using_bump_map(layer, root_ch):
            return True

    return False

def any_layers_using_normal_map(root_ch):
    if root_ch.type != 'NORMAL': return False
    yp = root_ch.id_data.yp
    channel_idx = get_channel_index(root_ch)

    for layer in yp.layers:
        if is_layer_using_normal_map(layer, root_ch):
            return True

    return False

def any_layers_using_channel(root_ch):
    yp = root_ch.id_data.yp
    channel_idx = get_channel_index(root_ch)

    for layer in yp.layers:
        try: ch = layer.channels[channel_idx]
        except: continue
        if get_channel_enabled(ch, layer, root_ch):
            return True

    return False

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
    # NOTE: This is just approximate way to know if the mesh is flat shaded or not

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

def get_all_materials_with_tree(tree):
    mats = []

    for mat in bpy.data.materials:
        if not mat.node_tree: continue
        for node in mat.node_tree.nodes:
            if node.type == 'GROUP' and node.node_tree == tree and mat not in mats:
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
            baked_source = get_mask_source(mask, get_baked=True)
            if baked_source and baked_source.image == image:
                entities.append(mask)
                continue

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

            baked_source = get_layer_source(layer, get_baked=True)
            if baked_source and baked_source.image == image:
                entities.append(layer)
                continue

            source = get_layer_source(layer)
            if source and source.image == image:
                entities.append(layer)

    return entities 

def check_yp_entities_images_segments_in_lists(entity, image, segment_name, segment_name_prop, entities=[], images=[], segment_names=[], segment_name_props=[]):

    if image.yia.is_image_atlas or image.yua.is_udim_atlas:
        if image.yia.is_image_atlas:
            segment = image.yia.segments.get(segment_name)
        else: segment = image.yua.segments.get(segment_name)

        similar_ids = [i for i, s in enumerate(segment_names) if s == segment.name and images[i] == image]
        if len(similar_ids) > 0:
            entities[similar_ids[0]].append(entity)
            segment_name_props[similar_ids[0]].append(segment_name_prop)
        else:
            images.append(image)
            segment_names.append(segment.name)
            entities.append([entity])
            segment_name_props.append([segment_name_prop])

    else:
        if image not in images:
            images.append(image)
            segment_names.append('')
            entities.append([entity])
            segment_name_props.append([segment_name_prop])
        else:
            idx = [i for i, img in enumerate(images) if img == image][0]
            entities[idx].append(entity)
            segment_name_props[idx].append(segment_name_prop)

    return entities, images, segment_names, segment_name_props

def get_yp_entities_images_and_segments(yp):
    entities = []
    images = []
    segment_names = []
    segment_name_props = []

    for layer in yp.layers:

        baked_source = get_layer_source(layer, get_baked=True)
        if baked_source and baked_source.image:
            image = baked_source.image
            entities, images, segment_names, segment_name_props = check_yp_entities_images_segments_in_lists(
                    layer, image, layer.baked_segment_name, 'baked_segment_name', entities, images, segment_names, segment_name_props)

        if layer.type == 'IMAGE':
            source = get_layer_source(layer)
            if source and source.image:
                image = source.image
                entities, images, segment_names, segment_name_props = check_yp_entities_images_segments_in_lists(
                        layer, image, layer.segment_name, 'segment_name', entities, images, segment_names, segment_name_props)

        for mask in layer.masks:

            baked_source = get_mask_source(mask, get_baked=True)
            if baked_source and baked_source.image:
                image = baked_source.image
                entities, images, segment_names, segment_name_props = check_yp_entities_images_segments_in_lists(
                        mask, image, mask.baked_segment_name, 'baked_segment_name', entities, images, segment_names, segment_name_props)

            if mask.type == 'IMAGE':
                source = get_mask_source(mask)
                if source and source.image:
                    image = source.image
                    entities, images, segment_names, segment_name_props = check_yp_entities_images_segments_in_lists(
                            mask, image, mask.segment_name, 'segment_name', entities, images, segment_names, segment_name_props)

    return entities, images, segment_names, segment_name_props

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
    if layer.use_baked or layer.type not in {'VCOL', 'BACKGROUND', 'COLOR', 'GROUP', 'HEMI', 'OBJECT_INDEX', 'BACKFACE'}:
        return True

    for ch in layer.channels:
        if ch.override and ch.override_type not in {'VCOL', 'DEFAULT'}:
            return True

    return False

def is_mask_using_vector(mask):
    if mask.use_baked or mask.type not in {'VCOL', 'BACKGROUND', 'COLOR', 'COLOR_ID', 'HEMI', 'OBJECT_INDEX', 'BACKFACE', 'EDGE_DETECT', 'MODIFIER'}:
        return True

    return False

def get_node(tree, name, parent=None):
    node = tree.nodes.get(name)

    if node and parent and node.parent != parent:
        return None

    return node

def is_normal_height_input_connected(root_normal_ch):
    # NOTE: Assuming that the active node is using the input tree
    node = get_active_ypaint_node()
    if not node: return False

    io_height_name = root_normal_ch.name + io_suffix['HEIGHT']
    height_inp = node.inputs.get(io_height_name)
    return height_inp and len(height_inp.links) > 0

def is_normal_input_connected(root_normal_ch):
    # NOTE: Assuming that the active node is using the input tree
    node = get_active_ypaint_node()
    if not node: return False
    
    normal_inp = node.inputs.get(root_normal_ch.name)
    return normal_inp and len(normal_inp.links) > 0

def is_overlay_normal_empty(yp):

    root_ch = get_root_height_channel(yp)
    if root_ch and is_normal_input_connected(root_ch):
        return False

    for l in yp.layers:
        c = get_height_channel(l)
        if not c or not l.enable or not c.enable: continue
        if c.normal_map_type == 'NORMAL_MAP' or (c.normal_map_type == 'BUMP_MAP' and not c.write_height):
            return False

    return True

def any_layers_using_vdisp(yp):

    for l in yp.layers:
        c = get_height_channel(l)
        if not c or not l.enable or not c.enable: continue
        if c.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':
            return True

    return False

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

def get_vcol_data_type_and_domain_by_name(obj, vcol_name, objs=[]):

    data_type = 'BYTE_COLOR'
    domain = 'CORNER'

    vcol = None
    vcols = get_vertex_colors(obj)
    if vcol_name in vcols:
        vcol = vcols.get(vcol_name)
        if is_greater_than_320():
            data_type = vcol.data_type
            domain = vcol.domain

    if not vcol:

        # Also check on other objects
        if not any(objs): objs = [obj]

        # Check geometry nodes outputs
        outp_found = False
        for o in objs:
            for mod in o.modifiers:
                if mod.type == 'NODES' and mod.node_group:
                    outputs = get_tree_outputs(mod.node_group)
                    for outp in outputs:
                        if ((is_greater_than_400() and outp.socket_type == 'NodeSocketColor') or
                            (not is_greater_than_400() and outp.type == 'RGBA')):
                            if mod[outp.identifier + '_attribute_name'] == vcol_name:
                                data_type = 'FLOAT_COLOR'
                                domain = outp.attribute_domain
                                outp_found = True
                                break
                if outp_found:
                    break
            if outp_found:
                break

    return data_type, domain

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
            mcol = get_mask_color_id_color(m)
            if abs(mcol[0]-color_id[0]) < COLORID_TOLERANCE and abs(mcol[1]-color_id[1]) < COLORID_TOLERANCE and abs(mcol[2]-color_id[2]) < COLORID_TOLERANCE:
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
        if not get_layer_enabled(layer): continue
        layer_tree = get_tree(layer)

        for i, ch in enumerate(layer.channels):
            root_ch = yp.channels[i]
            if not get_channel_enabled(ch, layer, root_ch): continue

            if not yp.use_linear_blending and ch.override and ch.override_type == 'IMAGE':
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

            if ch.override_1 and ch.override_1_type == 'IMAGE':
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
            if not get_mask_enabled(mask, layer): continue
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

            if yp.use_linear_blending:
                normal_ch = get_height_channel(layer)
                normal_root_ch = get_root_height_channel(yp)
                if normal_ch and get_channel_enabled(normal_ch, layer, normal_root_ch) and not normal_ch.override_1 and normal_ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'}:
                    ch_linear = layer_tree.nodes.get(normal_ch.linear)
                    #if ((is_image_source_srgb(image, source) and not ch_linear) or
                    #    (not is_image_source_srgb(image, source) and ch_linear)
                    #    ):
                    # NOTE: Float image is pretended to be sRGB even if it's using linear colorspace
                    if (image.is_float and ch_linear) or (not image.is_float and not ch_linear):
                        return True

                if not image.is_float and ((is_image_source_srgb(image, source) and linear) or
                    (not is_image_source_srgb(image, source) and not linear)
                    ):
                    return True

                if image.is_float and ((is_image_source_srgb(image, source) and not linear) or
                    (not is_image_source_srgb(image, source) and linear)
                    ):
                    return True

            else:
                if ((is_image_source_srgb(image, source) and not linear) or
                    (not is_image_source_srgb(image, source) and linear)
                    ):
                    return True

    return False

def get_write_height(ch):
    #if ch.normal_map_type == 'NORMAL_MAP':
    #    return ch.normal_write_height
    return ch.write_height

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

def copy_fcurves(src_fc, dest, subdest, attr):
    dest_path = subdest.path_from_id() + '.' + attr

    # Get prop value
    prop_value = getattr(subdest, attr)

    # Check array index
    array_index = src_fc.array_index if type(prop_value) == bpy_types.bpy_prop_array else -1

    # New fcurve
    nfc = None

    # Check if fcurve is from driver or not
    is_driver = type(src_fc.id_data) != bpy.types.Action

    if is_driver:
        # Add new driver
        nfc = dest.driver_add(dest_path)

        # Copy driver props with reverse on because some of the props need to set first
        copy_id_props(src_fc.driver, nfc.driver, reverse=True)

    else:

        # Remember current frame
        frame_current = bpy.context.scene.frame_current

        for i, kp in enumerate(src_fc.keyframe_points):
            # Get frame
            frame = int(kp.co[0])

            # Set attribute based on fcurve keyframe
            if array_index >= 0:
                # Update scene frame
                bpy.context.scene.frame_set(frame)

                # Set attribute with index
                att = getattr(subdest, attr)
                att[array_index] = src_fc.evaluate(frame)
            else: 
                setattr(subdest, attr, src_fc.evaluate(frame))

            # Insert keyframe
            dest.keyframe_insert(data_path=dest_path, frame=frame)

            # Get new fcurve
            if not nfc:
                if array_index >= 0:
                    nfc = [f for f in dest.animation_data.action.fcurves if f.data_path == dest_path and f.array_index == array_index][0]
                else: nfc = [f for f in dest.animation_data.action.fcurves if f.data_path == dest_path][0]

            # Get new keyframe point
            nkp = nfc.keyframe_points[i]

            # Copy keyframe props
            copy_id_props(kp, nkp)

        # Set frame back
        if bpy.context.scene.frame_current != frame_current:
            bpy.context.scene.frame_current = frame_current

def get_action_and_driver_fcurves(obj):
    fcs = []
    if obj.animation_data:

        # Fcurves from action
        if obj.animation_data.action:
            fcs.append(obj.animation_data.action.fcurves)
            #for fc in obj.animation_data.action.fcurves:
            #    fcs.append(fc)

        # Fcurves from drivers
        for fc in obj.animation_data.drivers:
            fcs.append(obj.animation_data.drivers)
            #for fc in obj.animation_data.drivers:
            #    fcs.append(fc)

    return fcs

def get_yp_fcurves(yp):
    tree = yp.id_data

    fcurves = []

    if tree.animation_data and tree.animation_data.action:
        for fc in tree.animation_data.action.fcurves:
            if fc.data_path.startswith('yp.'):
                fcurves.append(fc)

    return fcurves

def get_yp_drivers(yp):
    tree = yp.id_data

    drivers = []

    if tree.animation_data:
        for dr in tree.animation_data.drivers:
            if dr.data_path.startswith('yp.'):
                drivers.append(dr)

    return drivers

def get_yp_fcurves_and_drivers(yp):
    fcurves = get_yp_fcurves(yp)
    fcurves.extend(get_yp_drivers(yp))
    return fcurves

def remap_layer_fcurves(yp, index_dict):

    fcurves = get_yp_fcurves_and_drivers(yp)
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
    fcurves = get_yp_fcurves_and_drivers(yp)

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
    fcurves = get_yp_fcurves_and_drivers(yp)

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
    fcurves = get_yp_fcurves_and_drivers(yp)

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
    fcurves = get_yp_fcurves_and_drivers(yp)

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
    fcurves = get_yp_fcurves_and_drivers(yp)

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
    fcurves = get_yp_fcurves_and_drivers(yp)

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
    drivers = get_yp_drivers(yp)

    for fc in reversed(fcurves):
        if entity.path_from_id() in fc.data_path:
            tree.animation_data.action.fcurves.remove(fc)

    for dr in reversed(drivers):
        if entity.path_from_id() in dr.data_path:
            tree.animation_data.drivers.remove(dr)

def remove_channel_fcurves(root_ch):
    tree = root_ch.id_data
    yp = tree.yp
    fcurves = get_yp_fcurves(yp)
    drivers = get_yp_drivers(yp)

    index = get_channel_index(root_ch)

    for fc in reversed(fcurves):
        m = re.match(r'.*\.channels\[(\d+)\].*', fc.data_path)
        if m and index == int(m.group(1)):
            tree.animation_data.action.fcurves.remove(fc)

    for dr in reversed(drivers):
        m = re.match(r'.*\.channels\[(\d+)\].*', dr.data_path)
        if m and index == int(m.group(1)):
            tree.animation_data.drivers.remove(dr)

def shift_modifier_fcurves_down(parent):
    yp = parent.id_data.yp
    fcurves = get_yp_fcurves_and_drivers(yp)

    for i, mod in reversed(list(enumerate(parent.modifiers))):
        for fc in fcurves:
            if parent.path_from_id() not in fc.data_path: continue
            m = re.match(r'.*\.modifiers\[(\d+)\].*', fc.data_path)
            if m and int(m.group(1)) == i:
                fc.data_path = fc.data_path.replace('.modifiers[' + str(i) + ']', '.modifiers[' + str(i+1) + ']')

def shift_normal_modifier_fcurves_down(parent):
    yp = parent.id_data.yp
    fcurves = get_yp_fcurves_and_drivers(yp)

    for i, mod in reversed(list(enumerate(parent.modifiers_1))):
        for fc in fcurves:
            if parent.path_from_id() not in fc.data_path: continue
            m = re.match(r'.*\.modifiers_1\[(\d+)\].*', fc.data_path)
            if m and int(m.group(1)) == i:
                fc.data_path = fc.data_path.replace('.modifiers_1[' + str(i) + ']', '.modifiers_1[' + str(i+1) + ']')

def shift_modifier_fcurves_up(parent, start_index=1):
    tree = parent.id_data
    yp = tree.yp
    fcurves = get_yp_fcurves_and_drivers(yp)

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
    fcurves = get_yp_fcurves_and_drivers(yp)

    for i, mod in enumerate(parent.modifiers_1):
        if i < start_index: continue
        for fc in fcurves:
            if parent.path_from_id() not in fc.data_path: continue
            m = re.match(r'.*\.modifiers_1\[(\d+)\].*', fc.data_path)
            if m and int(m.group(1)) == i:
                fc.data_path = fc.data_path.replace('.modifiers_1[' + str(i) + ']', '.modifiers_1[' + str(i-1) + ']')

def shift_channel_fcurves_up(yp, start_index=1):
    fcurves = get_yp_fcurves_and_drivers(yp)

    for i, root_ch in enumerate(yp.channels):
        if i < start_index: continue
        for fc in fcurves:
            m = re.match(r'.*\.channels\[(\d+)\].*', fc.data_path)
            if m and int(m.group(1)) == i:
                fc.data_path = fc.data_path.replace('.channels[' + str(i) + ']', '.channels[' + str(i-1) + ']')

def shift_mask_fcurves_up(layer, start_index=1):
    tree = layer.id_data
    yp = tree.yp
    fcurves = get_yp_fcurves_and_drivers(yp)

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

def copy_image_channel_pixels(src, dest, src_idx=0, dest_idx=0, segment=None, segment_src=None, invert_value=False):

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
        if invert_value:
            dest_pxs[start_y:start_y+height, start_x:start_x+width][::, ::, dest_idx] = 1.0 - src_pxs[src_start_y:src_start_y+height, src_start_x:src_start_x+width][::, ::, src_idx]
        else: dest_pxs[start_y:start_y+height, start_x:start_x+width][::, ::, dest_idx] = src_pxs[src_start_y:src_start_y+height, src_start_x:src_start_x+width][::, ::, src_idx]
        dest.pixels.foreach_set(dest_pxs.ravel())

    else:
        # Get image pixels
        src_pxs = list(src.pixels)
        dest_pxs = list(dest.pixels)

        # Copy to selected channel
        if invert_value:
            for y in range(height):
                source_offset_y = width * 4 * (y + src_start_y)
                offset_y = dest.size[0] * 4 * (y + start_y)
                for x in range(width):
                    source_offset_x = 4 * (x + src_start_x)
                    offset_x = 4 * (x + start_x)
                    dest_pxs[offset_y + offset_x + dest_idx] = 1.0 - src_pxs[source_offset_y + source_offset_x + src_idx]
        else:
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
        start_x = segment.width * segment.tile_x
        start_y = segment.height * segment.tile_y

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

def get_entity_input_name(entity, prop_name):

    yp = entity.id_data.yp

    # Get property rna
    #entity_rna = type(entity).bl_rna
    #rna = entity_rna.properties[prop_name]

    # Regex
    m1 = re.match(r'^yp\.layers\[(\d+)\].*', entity.path_from_id())

    if m1:
        layer_index = int(m1.group(1))
    else:
        return ''

    # Get path without layer
    path = entity.path_from_id()
    path = path.replace('yp.layers[' + str(layer_index) + ']', '')

    return path + '.' + prop_name

def get_entity_prop_input(entity, prop_name):
    root_tree = entity.id_data
    yp = root_tree.yp

    # Regex
    m1 = re.match(r'^yp\.layers\[(\d+)\].*', entity.path_from_id())
    if m1:
        layer_index = int(m1.group(1))
        layer = yp.layers[layer_index]
    else:
        return None

    # Get layer node
    layer_node = root_tree.nodes.get(layer.group_node)

    # Get path
    path = entity.path_from_id()
    path = path.replace('yp.layers[' + str(layer_index) + ']', '')
    path += '.' + prop_name

    return layer_node.inputs.get(path)

def set_entity_prop_value(entity, prop_name, value):
    inp = get_entity_prop_input(entity, prop_name)
    if inp: 
        if type(value) == Color:
            inp.default_value = (value.r, value.g, value.b, 1.0)
        else: inp.default_value = value
    setattr(entity, prop_name, value)

def get_entity_prop_value(entity, prop_name):
    inp = get_entity_prop_input(entity, prop_name)
    if inp: return inp.default_value
    return getattr(entity, prop_name)

def get_mask_color_id_color(mask):
    val = get_entity_prop_value(mask, 'color_id')
    return Color((val[0], val[1], val[2]))

def split_layout(layout, factor, align=False):
    if not is_greater_than_280():
        return layout.split(percentage=factor, align=align)

    return layout.split(factor=factor, align=align)

def get_armature_modifier(obj, return_index=False):
    for i, mod in enumerate(obj.modifiers):
        if mod.type == 'ARMATURE' and mod.object:
            if return_index:
                return mod, i
            return mod

    if return_index:
        return None, None

    return None

def remember_armature_index(obj):
    ys_tree = get_ysculpt_tree(obj)
    if not ys_tree: return
    ys = ys_tree.ys
    
    mod, idx = get_armature_modifier(obj, return_index=True)
    if mod:
        ys.ori_armature_index = idx

def restore_armature_order(obj):
    ys_tree = get_ysculpt_tree(obj)
    if not ys_tree: return
    ys = ys_tree.ys

    mod, idx = get_armature_modifier(obj, return_index=True)

    if not mod: return

    ori_obj = bpy.context.object
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.modifier_move_to_index(modifier=mod.name, 
            index=min(ys.ori_armature_index, len(obj.modifiers)-1))

    bpy.context.view_layer.objects.active = ori_obj    

