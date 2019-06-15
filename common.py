import bpy, os, sys, re, time, numpy, math
from mathutils import *
from bpy.app.handlers import persistent
#from .__init__ import bl_info

BLENDER_28_GROUP_INPUT_HACK = False

MAX_VERTEX_DATA = 8

LAYERGROUP_PREFIX = '~yP Layer '
MASKGROUP_PREFIX = '~yP Mask '
ADDON_NAME = 'painty'
ADDON_TITLE = 'Painty'

INFO_PREFIX = '__yp_info_'

TREE_START = 'Group Input'
TREE_END = 'Group Output'
ONE_VALUE = 'One Value'
ZERO_VALUE = 'Zero Value'

#BAKED_UV = 'UV Map'
#BAKED_TANGENT = 'Baked Tangent'
#BAKED_TANGENT_FLIP = 'Baked Flip Backface Tangent'
#BAKED_BITANGENT = 'Baked Bitangent'
#BAKED_BITANGENT_FLIP = 'Baked Flip Backface Bitangent'
BAKED_PARALLAX = 'Baked Parallax'
BAKED_PARALLAX_FILTER = 'Baked Parallax Filter'

TEXCOORD = 'Texture Coordinate'
GEOMETRY = 'Geometry'

#GENERATED_PARALLAX_PREP = 'Generated Parallax Preparation'
#NORMAL_PARALLAX_PREP = 'Normal Parallax Preparation'
#OBJECT_PARALLAX_PREP = 'Object Parallax Preparation'
PARALLAX_PREP_SUFFIX = ' Parallax Preparation'

#GENERATED_MATRIX_TRANSFORM = 'Generated Matrix Transform'
#NORMAL_MATRIX_TRANSFORM = 'Normal Matrix Transform'
#OBJECT_MATRIX_TRANSFORM = 'Object Matrix Transform'

PARALLAX = 'Parallax'

MOD_TREE_START = '__mod_start'
MOD_TREE_END = '__mod_end'

HEIGHT_MAP = 'Height Map'

START_UV = ' Start UV'
DELTA_UV = ' Delta UV'
CURRENT_UV = ' Current UV'

ITERATE_GROUP = '~yP Iterate Parallax Group'
PARALLAX_DIVIDER = 4

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

TEMP_UV = '~TL Temp Paint UV'

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

TEXCOORD_IO_PREFIX = 'Texcoord '
PARALLAX_MIX_PREFIX = 'Parallax Mix '
PARALLAX_DELTA_PREFIX = 'Parallax Delta '
PARALLAX_CURRENT_PREFIX = 'Parallax Current '
PARALLAX_CURRENT_MIX_PREFIX = 'Parallax Current Mix '

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

def get_list_of_ypaint_nodes(mat):

    if not mat.node_tree: return []
    
    yp_nodes = []
    for node in mat.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree.yp.is_ypaint_node:
            yp_nodes.append(node)

    return yp_nodes

#def in_active_layer(obj):
#    scene = bpy.context.scene
#    space = bpy.context.space_data
#    if space.type == 'VIEW_3D' and space.local_view:
#        return any([layer for layer in obj.layers_local_view if layer])
#    else:
#        return any([layer for i, layer in enumerate(obj.layers) if layer and scene.layers[i]])

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

    return 'ERROR: No path found for ' + ADDON_NAME + '!'

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
    filters = ['rna_type', 'name', 'location', 'parent']
    filters.extend(extras)
    #print()
    for prop in props:
        if prop.startswith('__'): continue
        if prop.startswith('bl_'): continue
        if prop in filters: continue
        val = getattr(source, prop)
        if 'bpy_func' in str(type(val)): continue
        if 'bpy_prop' in str(type(val)): continue
        #print(prop, str(type(getattr(source, prop))))
        # Copy stuff here
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
        dest.inputs[i].default_value = inp.default_value

    # Copy outputs default value
    for i, outp in enumerate(source.outputs):
        dest.outputs[i].default_value = outp.default_value 

def update_image_editor_image(context, image):
    for area in context.screen.areas:
        if area.type == 'IMAGE_EDITOR' and not area.spaces[0].use_image_pin and area.spaces[0].image != image:
            area.spaces[0].image = image
            # Hack for Blender 2.8 which keep pinning image automatically
            area.spaces[0].use_image_pin = False

# Check if name already available on the list
def get_unique_name(name, items, surname = ''):

    if surname != '':
        unique_name = name + ' ' + surname
    else: unique_name = name

    name_found = [item for item in items if item.name == unique_name]
    if name_found:
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

def simple_remove_node(tree, node, remove_data=True):
    #if not node: return
    scene = bpy.context.scene

    if remove_data:
        if node.bl_idname == 'ShaderNodeTexImage':
            image = node.image
            if image:
                if ((scene.tool_settings.image_paint.canvas == image and image.users == 2) or
                    (scene.tool_settings.image_paint.canvas != image and image.users == 1)):
                    bpy.data.images.remove(image)

        elif node.bl_idname == 'ShaderNodeGroup':
            if node.node_tree and node.node_tree.users == 1:
                bpy.data.node_groups.remove(node.node_tree)

            #remove_tree_data_recursive(node)

    tree.nodes.remove(node)

def remove_node(tree, entity, prop, remove_data=True, obj=None):
    if not hasattr(entity, prop): return
    #if prop not in entity: return

    scene = bpy.context.scene
    node = tree.nodes.get(getattr(entity, prop))
    #node = tree.nodes.get(entity[prop])

    if node: 
        if remove_data:
            # Remove image data if the node is the only user
            if node.bl_idname == 'ShaderNodeTexImage':
                image = node.image
                if image:
                    if ((scene.tool_settings.image_paint.canvas == image and image.users == 2) or
                        (scene.tool_settings.image_paint.canvas != image and image.users == 1)):
                        bpy.data.images.remove(image)

            elif node.bl_idname == 'ShaderNodeGroup':
                if node.node_tree and node.node_tree.users == 1:
                    remove_tree_inside_tree(node.node_tree)
                    bpy.data.node_groups.remove(node.node_tree)

            elif (obj and obj.type == 'MESH' #and obj.active_material and obj.active_material.users == 1
                    and hasattr(entity, 'type') and entity.type == 'VCOL' and node.bl_idname == 'ShaderNodeAttribute'):
                vcol = obj.data.vertex_colors.get(node.attribute_name)

                T = time.time()

                # Check if other layer use this vertex color
                other_users_found = False
                for ng in bpy.data.node_groups:
                    for t in ng.yp.layers:

                        # Search for vcol layer
                        if t.type == 'VCOL':
                            src = get_layer_source(t)
                            if src != node and src.attribute_name == vcol.name:
                                other_users_found = True
                                break

                        # Search for mask layer
                        for m in t.masks:
                            if m.type == 'VCOL':
                                src = get_mask_source(m)
                                if src != node and src.attribute_name == vcol.name:
                                    other_users_found = True
                                    break

                print('INFO: Searching on entire node groups to search for vcol takes', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

                #other_user_found = False
                #for t in yp.layers:
                #    if t.type == 'VCOL':
                if not other_users_found:
                    obj.data.vertex_colors.remove(vcol)

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

        #node = tree.nodes.new('ShaderNodeValue')
        #node.name = ZERO_VALUE
        #node.label = 'Zero Value'
        #node.outputs[0].default_value = 0.0

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

def replace_image(old_image, new_image, yp=None, uv_name = ''):

    if old_image == new_image: return

    # Rename
    old_name = old_image.name
    old_image.name = '_____temp'
    new_image.name = old_name

    # Set filepath
    if new_image.filepath == '' and old_image.filepath != '' and not old_image.packed_file:
        new_image.filepath = old_image.filepath

    # Replace all users
    users = get_all_image_users(old_image)
    for user in users:
        #print(user)
        user.image = new_image

    replaceds = users

    # Replace uv_map of layers and masks
    if yp and uv_name != '':

        replaceds = []

        # Disable temp uv update
        #ypui = bpy.context.window_manager.ypui
        #ori_disable_temp_uv = ypui.disable_auto_temp_uv_update

        for i, layer in enumerate(yp.layers):
            if layer.type == 'IMAGE':
                source = get_layer_source(layer)
                if source.image and source.image == new_image:
                    if layer.uv_name != uv_name:
                        layer.uv_name = uv_name
                    if i not in replaceds:
                        replaceds.append(i)

            for mask in layer.masks:
                if mask.type == 'IMAGE':
                    source = get_mask_source(mask)
                    if source.image and source.image == new_image:
                        if mask.uv_name != uv_name:
                            mask.uv_name = uv_name
                        if i not in replaceds:
                            replaceds.append(i)

        # Recover temp uv update
        #ypui.disable_auto_temp_uv_update = ori_disable_temp_uv

    # Remove old image
    bpy.data.images.remove(old_image)

    return replaceds

def mute_node(tree, entity, prop):
    if not hasattr(entity, prop): return
    node = tree.nodes.get(getattr(entity, prop))
    if node: node.mute = True

def unmute_node(tree, entity, prop):
    if not hasattr(entity, prop): return
    node = tree.nodes.get(getattr(entity, prop))
    if node: node.mute = False

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
        info.label = 'Part of ' + ADDON_TITLE + ' addon version ' + yp.version
        info.width = 360.0
    elif tree_type == 'ROOT':
        info.label = 'Created using ' + ADDON_TITLE + ' addon version ' + yp.version
        info.width = 420.0
    else:
        info.label = 'Part of ' + ADDON_TITLE + ' addon'
        info.width = 250.0

    info.use_custom_color = True
    info.color = (1.0, 1.0, 1.0)
    info.height = 30.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'Get this addon on patreon.com/ucupumar'
    info.use_custom_color = True
    info.color = (1.0, 1.0, 1.0)
    info.width = 420.0
    info.height = 30.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    info.label = 'WARNING: Do NOT edit this group manually!'
    info.use_custom_color = True
    info.color = (1.0, 0.5, 0.5)
    info.width = 450.0
    info.height = 30.0
    infos.append(info)

    info = nodes.new('NodeFrame')
    #info.label = 'Please use this panel: Node Editor > Tools > ' + ADDON_TITLE
    info.label = 'Please use this panel: Node Editor > Tools > Misc'
    info.use_custom_color = True
    info.color = (1.0, 0.5, 0.5)
    info.width = 580.0
    info.height = 30.0
    infos.append(info)

    if tree_type in {'LAYER', 'ROOT'}:

        loc = Vector((0, 70))

        for info in reversed(infos):
            info.name = INFO_PREFIX + info.name

            loc.y += 40
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
        for ng in data_from.node_groups:
            if ng == name: # and ng not in exist_groups:

                data_to.node_groups.append(ng)
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

def replace_new_node(tree, entity, prop, node_id_name, label='', group_name='', return_status=False, hard_replace=False, dirty=False):
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

        if not prev_tree or (prev_tree.name != group_name and not m):

            if hard_replace:
                tree.nodes.remove(node)
                node = new_node(tree, entity, prop, node_id_name, label)
                dirty = True

            # Replace group tree
            node.node_tree = get_node_tree_lib(group_name)

            if not prev_tree:
                dirty = True

            else:
                # Compare previous group inputs with current group inputs
                if len(prev_tree.inputs) != len(node.inputs):
                    dirty = True
                else:
                    for i, inp in enumerate(node.inputs):
                        if inp.name != prev_tree.inputs[i].name:
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

    try:
        tree = entity.id_data
        yp = tree.yp
        group_node = tree.nodes.get(entity.group_node)
        #if not group_node or group_node.type != 'GROUP': return None
        return group_node.node_tree
    except: 
        return None

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

def get_mask_tree(mask):

    m = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
    if not m : return None

    yp = mask.id_data.yp
    layer = yp.layers[int(m.group(1))]
    layer_tree = get_tree(layer)

    group_node = layer_tree.nodes.get(mask.group_node)
    if not group_node or group_node.type != 'GROUP': return layer_tree
    return group_node.node_tree

def get_mask_source(mask):
    tree = get_mask_tree(mask)
    return tree.nodes.get(mask.source)

def get_mask_mapping(mask):
    tree = get_mask_tree(mask)
    return tree.nodes.get(mask.mapping)

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
    tree = get_source_tree(layer)
    return tree.nodes.get(layer.mapping)

def get_neighbor_uv_space_input(texcoord_type):
    if texcoord_type == 'UV':
        return 0.0 # Tangent Space
    if texcoord_type in {'Generated', 'Normal', 'Object'}:
        return 1.0 # Object Space
    if texcoord_type in {'Camera', 'Window', 'Reflection'}: 
        return 2.0 # View Space

def change_layer_name(yp, obj, src, layer, texes):
    if yp.halt_update: return

    yp.halt_update = True

    if layer.type == 'VCOL' and obj.type == 'MESH':

        # Get vertex color from node
        vcol = obj.data.vertex_colors.get(src.attribute_name)

        # Temporarily change its name to temp name so it won't affect unique name
        vcol.name = '___TEMP___'

        # Get unique name
        layer.name = get_unique_name(layer.name, obj.data.vertex_colors) 

        # Set vertex color name and attribute node
        vcol.name = layer.name
        src.attribute_name = layer.name

    elif layer.type == 'IMAGE':
        src.image.name = '___TEMP___'
        layer.name = get_unique_name(layer.name, bpy.data.images) 
        src.image.name = layer.name

    else:
        name = layer.name
        layer.name = '___TEMP___'
        layer.name = get_unique_name(name, texes) 

    yp.halt_update = False

def set_obj_vertex_colors(obj, vcol, color):
    if obj.type != 'MESH': return

    if bpy.app.version_string.startswith('2.8'):
        col = (color[0], color[1], color[2], 1.0)
    else: col = color

    for poly in obj.data.polygons:
        for loop_index in poly.loop_indices:
            vcol.data[loop_index].color = col

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

def fix_io_index(item, items, correct_index):
    cur_index = [i for i, it in enumerate(items) if it == item]
    if cur_index and cur_index[0] != correct_index:
        items.move(cur_index[0], correct_index)

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

def is_top_member(layer):
    
    if layer.parent_idx == -1:
        return False

    yp = layer.id_data.yp

    for i, t in enumerate(yp.layers):
        if t == layer:
            if layer.parent_idx == i-1:
                return True
            else: return False

    return False

def is_bottom_member(layer):

    if layer.parent_idx == -1:
        return False

    yp = layer.id_data.yp

    layer_idx = -1
    last_member_idx = -1
    for i, t in enumerate(yp.layers):
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

def set_uv_neighbor_resolution(entity, uv_neighbor=None, source=None, mapping=None):

    yp = entity.id_data.yp
    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if m1: 
        tree = get_tree(entity)
        if not mapping: mapping = get_layer_mapping(entity)
        if not source: source = get_layer_source(entity)
    elif m2: 
        tree = get_tree(yp.layers[int(m2.group(1))])
        if not mapping: mapping = get_mask_mapping(entity)
        if not source: source = get_mask_source(entity)
    else: return

    if not uv_neighbor: uv_neighbor = tree.nodes.get(entity.uv_neighbor)
    if not uv_neighbor: return

    if 'ResX' not in uv_neighbor.inputs: return

    if entity.type == 'IMAGE' and source.image:
        uv_neighbor.inputs['ResX'].default_value = source.image.size[0] * mapping.scale[0]
        uv_neighbor.inputs['ResY'].default_value = source.image.size[1] * mapping.scale[1]
    else:
        uv_neighbor.inputs['ResX'].default_value = 1000.0
        uv_neighbor.inputs['ResY'].default_value = 1000.0

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
        segment = image.yia.segments.get(entity.segment_name)

        scale_x = segment.width/image.size[0] * scale_x
        scale_y = segment.height/image.size[1] * scale_y

        offset_x = scale_x * segment.tile_x + offset_x * scale_x
        offset_y = scale_y * segment.tile_y + offset_y * scale_y

    mapping.translation = (offset_x, offset_y, offset_z)
    mapping.rotation = entity.rotation
    mapping.scale = (scale_x, scale_y, scale_z)

    set_uv_neighbor_resolution(entity, source=source, mapping=mapping)

    if entity.type == 'IMAGE' and entity.texcoord_type == 'UV':
        if m1 or (m2 and entity.active_edit):
            yp.need_temp_uv_refresh = True

def is_transformed(mapping):
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

def refresh_temp_uv(obj, entity): 

    #if not entity or entity.segment_name == '' or entity.type != 'IMAGE':
    if not entity or entity.type != 'IMAGE': # or not is_transformed(entity):
        return False

    #yp = entity.id_data.yp
    #yp.need_temp_uv_refresh = False

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    # Get source
    if m1: 
        source = get_layer_source(entity)
        mapping = get_layer_mapping(entity)
    elif m2: 
        source = get_mask_source(entity)
        mapping = get_mask_mapping(entity)
    else: return False

    if bpy.app.version_string.startswith('2.8'):
        uv_layers = obj.data.uv_layers
    else: uv_layers = obj.data.uv_textures

    layer_uv = uv_layers.get(entity.uv_name)
    if not layer_uv: return False

    if uv_layers.active != layer_uv:
        uv_layers.active = layer_uv

    # Delete previous temp uv
    for uv in uv_layers:
        if uv.name == TEMP_UV:
            uv_layers.remove(uv)

    if not is_transformed(mapping):
        return False

    img = source.image
    if not img: return False

    # New uv layers
    temp_uv_layer = uv_layers.new(name=TEMP_UV)
    uv_layers.active = temp_uv_layer

    # Cannot do this on edit mode
    ori_mode = obj.mode
    if ori_mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')

    # Create transformation matrix
    # Scale
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

    # Create numpy array to store uv coordinates
    arr = numpy.zeros(len(obj.data.loops)*2, dtype=numpy.float32)
    obj.data.uv_layers.active.data.foreach_get('uv', arr)
    arr.shape = (arr.shape[0]//2, 2)

    # Matrix transformation for each uv coordinates
    if bpy.app.version_string.startswith('2.8'):
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
    obj.data.uv_layers.active.data.foreach_set('uv', arr.ravel())

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

def get_root_parallax_channel(yp):
    for ch in yp.channels:
        if ch.type == 'NORMAL' and ch.enable_parallax:
            return ch

    return None

def get_root_height_channel(yp):
    for ch in yp.channels:
        if ch.type == 'NORMAL': # and ch.enable_parallax:
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
    for inp in source.inputs:
        target_inp = target.inputs.get(inp.name)

        if target_inp and target_inp.bl_socket_idname != inp.bl_socket_idname:
            target.inputs.remove(target_inp)
            target_inp = None

        if not target_inp:
            target_inp = target.inputs.new(inp.bl_socket_idname, inp.name)
            target_inp.default_value = inp.default_value

        valid_inputs.append(target_inp)

    # Copy outputs
    for outp in source.outputs:
        target_outp = target.outputs.get(outp.name)

        if target_outp and target_outp.bl_socket_idname != outp.bl_socket_idname:
            target.outputs.remove(target_outp)
            target_outp = None

        if not target_outp:
            target_outp = target.outputs.new(outp.bl_socket_idname, outp.name)
            target_outp.default_value = outp.default_value

        valid_outputs.append(target_outp)

    # Remove invalid inputs
    for inp in target.inputs:
        if inp not in valid_inputs:
            target.inputs.remove(inp)

    # Remove invalid outputs
    for outp in target.outputs:
        if outp not in valid_outputs:
            target.outputs.remove(outp)

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
            #print('Aaaaaa')
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

#def set_baked_parallax_node(yp, node, img=None):
#    ch = get_root_parallax_channel(yp)
#
#    # Set node parameters
#    #node.inputs['layer_depth'].default_value = 1.0 / ch.parallax_num_of_layers
#    #node.inputs['depth_scale'].default_value = ch.displacement_height_ratio
#    #node.inputs['depth_scale'].default_value = get_displacement_max_height(ch)
#    #node.inputs['ref_plane'].default_value = ch.parallax_ref_plane
#
#    #delta_uv = tree.nodes.get(uv.parallax_delta_uv)
#
#    #if not delta_uv:
#    #    delta_uv = new_node(tree, uv, 'parallax_delta_uv', 'ShaderNodeMixRGB', uv.name + DELTA_UV)
#    #    delta_uv.inputs[0].default_value = 1.0
#    #    delta_uv.blend_type = 'MULTIPLY'
#
#    #current_uv = tree.nodes.get(uv.parallax_current_uv)
#
#    #if not current_uv:
#    #    current_uv = new_node(tree, uv, 'parallax_current_uv', 'ShaderNodeVectorMath', uv.name + CURRENT_UV)
#    #    current_uv.operation = 'SUBTRACT'
#
#    tree = node.node_tree
#
#    if img:
#        depth_source = tree.nodes.get('_depth_source')
#        depth_from_tex = depth_source.node_tree.nodes.get('_depth_from_tex')
#        depth_from_tex.image = img
#
#    parallax_loop = tree.nodes.get('_parallax_loop')
#    create_delete_iterate_nodes(loop_tree, ch.parallax_num_of_layers)
#
#    #counter = 0
#    #while True:
#    #    it = loop_tree.nodes.get('_iterate_' + str(counter))
#
#    #    it_found = False
#    #    if it: it_found = True
#
#    #    if not it and counter < ch.parallax_num_of_layers:
#    #        it = loop_tree.nodes.new('ShaderNodeGroup')
#    #        it.name = '_iterate_' + str(counter)
#    #        it.node_tree = iter_tree
#
#    #    if it and counter >= ch.parallax_num_of_layers:
#    #        loop_tree.nodes.remove(it)
#
#    #    if not it_found and counter >= ch.parallax_num_of_layers:
#    #        break
#
#    #    counter += 1
#
#    #for n in parallax_loop.node_tree.nodes:
#    #    if n.type == 'GROUP':
#    #        iter_tree= n.node_tree
#    #        counter += 1
#
#    #if counter != 

def get_channel_index(root_ch):
    yp = root_ch.id_data.yp

    for i, c in enumerate(yp.channels):
        if c == root_ch:
            return i

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
        base_distance = abs(ch.bump_distance)

    if ch.enable_transition_bump:
        if ch.normal_map_type == 'NORMAL_MAP' and layer.type != 'GROUP':
            #max_height = ch.transition_bump_distance
            max_height = abs(get_transition_bump_max_distance_with_crease(ch))
        else:
            if ch.transition_bump_flip:
                #max_height = ch.transition_bump_distance + abs(ch.bump_distance)*2
                max_height = abs(get_transition_bump_max_distance_with_crease(ch)) + base_distance*2

            else: 
                #max_height = max(ch.transition_bump_distance, abs(ch.bump_distance))
                max_height = abs(get_transition_bump_max_distance_with_crease(ch)) + base_distance

    else: 
        #max_height = abs(ch.bump_distance)
        max_height = base_distance

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
        delta = get_transition_bump_max_distance(ch) - abs(ch.bump_distance)

    return delta

def get_max_height_from_list_of_layers(layers, ch_index, layer=None, top_layers_only=False):

    max_height = 0.0

    for l in reversed(layers):
        if ch_index > len(l.channels)-1: continue
        if top_layers_only and l.parent_idx != -1: continue
        c = l.channels[ch_index]
        ch_max_height = get_layer_channel_max_height(l, c)
        if (l.enable and c.enable and 
                (c.write_height or (not c.write_height and l == layer)) and
                c.normal_blend_type in {'MIX', 'COMPARE'} and max_height < ch_max_height
                ):
            max_height = ch_max_height
        if l == layer:
            break

    for l in reversed(layers):
        if ch_index > len(l.channels)-1: continue
        if top_layers_only and l.parent_idx != -1: continue
        c = l.channels[ch_index]
        ch_max_height = get_layer_channel_max_height(l, c)
        if (l.enable and c.enable and 
                (c.write_height or (not c.write_height and l == layer)) and
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
            if ch.write_height:
                channels.append(ch)

    return channels

def get_write_height_normal_channel(layer):
    yp = layer.id_data.yp

    for i, root_ch in enumerate(yp.channels):
        if root_ch.type == 'NORMAL':
            ch = layer.channels[i]
            if ch.write_height:
                return ch

    return None

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
            parallax_prep.inputs['depth_scale'].default_value = max_height

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

#def get_io_index(layer, root_ch, alpha=False):
#    if alpha:
#        return root_ch.io_index+1
#    return root_ch.io_index
#
#def get_alpha_io_index(layer, root_ch):
#    return get_io_index(layer, root_ch, alpha=True)

# Some image_ops need this
#def get_active_image():
#    node = get_active_ypaint_node()
#    if not node: return None
#    yp = node.node_tree.yp
#    nodes = node.node_tree.nodes
#    if len(yp.layers) == 0: return None
#    layer = yp.layers[yp.active_layer_index]
#    if layer.type != 'ShaderNodeTexImage': return None
#    source = nodes.get(layer.source)
#    return source.image
