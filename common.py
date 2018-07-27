import bpy, os, sys, re
from mathutils import *
from bpy.app.handlers import persistent
#from .__init__ import bl_info

TEXGROUP_PREFIX = '~TL Tex '
MASKGROUP_PREFIX = '~TL Mask '
ADDON_NAME = 'yTexLayers'

MODIFIER_TREE_START = '__mod_start_'
MODIFIER_TREE_END = '__mod_end_'

MASK_TREE_START = '__mask_start_'
MASK_TREE_END = '__mask_end_'

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

normal_map_type_items = (
        ('BUMP_MAP', 'Bump Map', '', 'MATCAP_09', 0),
        ('FINE_BUMP_MAP', 'Fine Bump Map', '', 'MATCAP_09', 1),
        ('NORMAL_MAP', 'Normal Map', '', 'MATCAP_23', 2)
        )

normal_blend_items = (
        ('MIX', 'Mix', ''),
        #('VECTOR_MIX', 'Vector Mix', ''),
        ('OVERLAY', 'Overlay', '')
        )

texture_type_items = (
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
        )

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

texture_node_bl_idnames = {
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
        }

GAMMA = 2.2

def get_current_version_str():
    bl_info = sys.modules[ADDON_NAME].bl_info
    return str(bl_info['version']).replace(', ', '.').replace('(','').replace(')','')

def get_active_material():
    scene = bpy.context.scene
    engine = scene.render.engine
    if not hasattr(bpy.context, 'object'): return None
    obj = bpy.context.object

    if not obj: return None

    mat = obj.active_material

    if engine in {'BLENDER_RENDER', 'BLENDER_GAME'}:
        return None

    return mat

def in_active_layer(obj):
    scene = bpy.context.scene
    space = bpy.context.space_data
    if space.type == 'VIEW_3D' and space.local_view:
        return any([layer for layer in obj.layers_local_view if layer])
    else:
        return any([layer for i, layer in enumerate(obj.layers) if layer and scene.layers[i]])

def get_addon_filepath():

    sep = os.sep

    # Search for addon dirs
    roots = bpy.utils.script_paths()

    possible_dir_names = [ADDON_NAME, ADDON_NAME + '-master']

    for root in roots:
        if os.path.basename(root) != 'scripts': continue
        filepath = root + sep + 'addons'

        dirs = next(os.walk(filepath))[1]
        folders = [x for x in dirs if x in possible_dir_names]

        if folders:
            return filepath + sep + folders[0] + sep

    return 'ERROR: No path found for yPanel!'

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

def copy_node_props_(source, dest, extras = []):
    #print()
    props = dir(source)
    filters = ['rna_type', 'name']
    filters.extend(extras)
    for prop in props:
        if prop.startswith('__'): continue
        if prop.startswith('bl_'): continue
        if prop in filters: continue
        val = getattr(source, prop)
        if 'bpy_func' in str(type(val)): continue
        # Copy stuff here
        try: 
            setattr(dest, prop, val)
            #print('SUCCESS:', prop, val)
        except: 
            #print('FAILED:', prop, val)
            pass

def copy_node_props(source ,dest, extras = []):
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
                else: point_copy = curve_copy.points[j]
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
        dest.inputs[i].default_value = inp.default_value

    # Copy outputs default value
    for i, outp in enumerate(source.outputs):
        dest.outputs[i].default_value = outp.default_value 

def update_image_editor_image(context, image):
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR':
            if not area.spaces[0].use_image_pin:
                if area.spaces[0].image != image:
                    area.spaces[0].image = image

# Check if name already available on the list
def get_unique_name(name, items):
    unique_name = name
    name_found = [item for item in items if item.name == name]
    if name_found:
        i = 1
        while True:
            new_name = name + ' ' + str(i)
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

#def get_active_texture_layers_node():
#    #node = get_active_node()
#    #if not node or node.type != 'GROUP' or not node.node_tree or not node.node_tree.tl.is_tl_node:
#    #    return None
#    #return node
#
#    mat = get_active_material()
#    if not mat or not mat.node_tree: return None
#
#    nodes = mat.node_tree.nodes
#
#    return nodes.get(mat.tl.active_tl_node)

def get_active_texture_layers_node():
    tlui = bpy.context.window_manager.tlui

    # Get material UI prop
    mat = get_active_material()
    if not mat or not mat.node_tree: return None

    # Search for its name first
    mui = tlui.materials.get(mat.name)

    # If not found, search for its pointer
    if not mui:
        mui = [mui for mui in tlui.materials if mui.material == mat]
        if mui: 
            mui = mui[0]
            mui.name = mui.material.name

    # If still not found, create one
    if not mui:
        mui = tlui.materials.add()
        mui.material = mat
        mui.name = mat.name

    # Try to get tl node
    node = get_active_node()
    if node and node.type == 'GROUP' and node.node_tree and node.node_tree.tl.is_tl_node:
        # Update node name
        if mui.active_tl_node != node.name:
            mui.active_tl_node = node.name
        return node

    # If not active node isn't a group node
    node = mat.node_tree.nodes.get(mui.active_tl_node)
    if node: return node

    # If node not found
    for node in mat.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree and node.node_tree.tl.is_tl_node:
            mui.active_tl_node = node.name
            return node

    return None

def remove_node(tree, obj, prop, remove_data=True):
    if not hasattr(obj, prop): return

    scene = bpy.context.scene
    node = tree.nodes.get(getattr(obj, prop))

    if node: 
        if remove_data:
            # Remove image data if the node is the only user
            if node.bl_idname == 'ShaderNodeTexImage':
                image = node.image
                if image:
                    if ((scene.tool_settings.image_paint.canvas == image and image.users == 2) or
                        (scene.tool_settings.image_paint.canvas != image and image.users == 1)):
                        bpy.data.images.remove(image)

        # Remove the node itself
        tree.nodes.remove(node)

    setattr(obj, prop, '')

def new_node(tree, obj, prop, node_id_name, label=''):
    
    if not hasattr(obj, prop): return

    node = tree.nodes.new(node_id_name)
    setattr(obj, prop, node.name)

    if label != '':
        node.label = label

    return node

def check_new_node(tree, obj, prop, node_id_name, label=''):
    ''' Check if node is available, if not, create one '''
    if not hasattr(obj, prop): return

    # Try to get the node first
    node = tree.nodes.get(getattr(obj, prop))
    new = False

    # Create new node if not found
    if not node:
        node = new_node(tree, obj, prop, node_id_name, label)
        new = True

    return node, new

def get_tree(obj):

    #m = re.match(r'tl\.textures\[(\d+)\]', obj.path_from_id())
    #if not m: return None
    if not hasattr(obj.id_data, 'tl') or not hasattr(obj, 'group_node'): return None

    tree = obj.id_data
    tl = tree.tl

    group_node = tree.nodes.get(obj.group_node)
    if not group_node or group_node.type != 'GROUP': return None
    return group_node.node_tree

def get_mod_tree(obj):

    m1 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]', obj.path_from_id())
    m2 = re.match(r'tl\.textures\[(\d+)\]\.channels\[(\d+)\]\.modifiers\[(\d+)\]', obj.path_from_id())
    #m2 = re.match(r'tl\.channels\[(\d+)\]\.modifiers\[(\d+)\]', obj.path_from_id())
    if not m1 and not m2:
        return obj.id_data

    tl = obj.id_data.tl
    tex = tl.textures[int(m1.group(1))]
    ch = tex.channels[int(m1.group(2))]
    tex_tree = get_tree(tex)

    #print(ch.mod_group)
    mod_group = tex_tree.nodes.get(ch.mod_group)
    if not mod_group or mod_group.type != 'GROUP':
        return tex_tree

    return mod_group.node_tree

# Some image_ops need this
#def get_active_image():
#    node = get_active_texture_layers_node()
#    if not node: return None
#    tl = node.node_tree.tl
#    nodes = node.node_tree.nodes
#    if len(tl.textures) == 0: return None
#    tex = tl.textures[tl.active_texture_index]
#    if tex.type != 'ShaderNodeTexImage': return None
#    source = nodes.get(tex.source)
#    return source.image
