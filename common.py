import bpy, os, sys, re, time
from mathutils import *
from bpy.app.handlers import persistent
#from .__init__ import bl_info

BLENDER_28_GROUP_INPUT_HACK = False

TEXGROUP_PREFIX = '~TL Tex '
MASKGROUP_PREFIX = '~TL Mask '
ADDON_NAME = 'yTexLayers'

SOURCE_TREE_START = '__source_start_'
SOURCE_TREE_END = '__source_end_'
SOURCE_SOLID_VALUE = '__source_solid_'

MOD_TREE_START = '__mod_start_'
MOD_TREE_END = '__mod_end_'

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

neighbor_directions = ['n', 's', 'e', 'w']

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

texture_type_labels = {
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
        'VCOL' : 'ShaderNodeAttribute',
        'BACKGROUND' : 'NodeGroupInput',
        'COLOR' : 'ShaderNodeRGB',
        'GROUP' : 'NodeGroupInput',
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

    return 'ERROR: No path found for yTexLayers!'

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
    if not mat or not mat.node_tree: 
        tlui.active_mat = ''
        return None

    # Search for its name first
    mui = tlui.materials.get(mat.name)

    # Flag for indicate new mui just created
    change_name = False

    # If still not found, create one
    if not mui:

        if tlui.active_mat != '':
            prev_mat = bpy.data.materials.get(tlui.active_mat)
            if not prev_mat:
                #print(tlui.active_mat)
                change_name = True
                # Remove prev mui
                prev_idx = [i for i, m in enumerate(tlui.materials) if m.name == tlui.active_mat]
                if prev_idx:
                    tlui.materials.remove(prev_idx[0])
                    #print('Removed!')

        mui = tlui.materials.add()
        mui.name = mat.name
        #print('New MUI!', mui.name)

    if tlui.active_mat != mat.name:
        tlui.active_mat = mat.name

    # Try to get tl node
    node = get_active_node()
    if node and node.type == 'GROUP' and node.node_tree and node.node_tree.tl.is_tl_node:
        # Update node name
        if mui.active_tl_node != node.name:
            #print('From:', mui.active_tl_node)
            mui.active_tl_node = node.name
            #print('To:', node.name)
        if tlui.active_tl_node != node.name:
            tlui.active_tl_node = node.name
        return node

    # If not active node isn't a group node
    # New mui possibly means material name just changed, try to get previous active node
    if change_name: 
        node = mat.node_tree.nodes.get(tlui.active_tl_node)
        if node:
            #print(mui.name, 'Change name from:', mui.active_tl_node)
            mui.active_tl_node = node.name
            #print(mui.name, 'Change name to', mui.active_tl_node)
            return node

    node = mat.node_tree.nodes.get(mui.active_tl_node)
    #print(mui.active_tl_node, node)
    if node: return node

    # If node still not found
    for node in mat.node_tree.nodes:
        if node.type == 'GROUP' and node.node_tree and node.node_tree.tl.is_tl_node:
            #print('Last resort!', mui.name, mui.active_tl_node)
            mui.active_tl_node = node.name
            return node

    return None

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
                    bpy.data.node_groups.remove(node.node_tree)

            elif (obj and obj.type == 'MESH' #and obj.active_material and obj.active_material.users == 1
                    and hasattr(entity, 'type') and entity.type == 'VCOL' and node.bl_idname == 'ShaderNodeAttribute'):
                vcol = obj.data.vertex_colors.get(node.attribute_name)

                T = time.time()

                # Check if other layer use this vertex color
                other_users_found = False
                for ng in bpy.data.node_groups:
                    for t in ng.tl.textures:

                        # Search for vcol layer
                        if t.type == 'VCOL':
                            src = get_tex_source(t)
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
                #for t in tl.textures:
                #    if t.type == 'VCOL':
                if not other_users_found:
                    obj.data.vertex_colors.remove(vcol)

        # Remove the node itself
        #print('Node ' + prop + ' from ' + str(entity) + ' removed!')
        tree.nodes.remove(node)

    setattr(entity, prop, '')
    #entity[prop] = ''

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

def check_new_node(tree, entity, prop, node_id_name, label=''):
    ''' Check if node is available, if not, create one '''

    # Try to get the node first
    try: node = tree.nodes.get(getattr(entity, prop))
    except: return None

    # Create new node if not found
    if not node:
        node = new_node(tree, entity, prop, node_id_name, label)

    return node

def replace_new_node(tree, entity, prop, node_id_name, label='', replaced_status=False):
    ''' Check if node is available, replace if available '''

    replaced = False

    # Try to get the node first
    try: node = tree.nodes.get(getattr(entity, prop))
    except: return None

    # Remove node if found and has different id name
    if node and node.bl_idname != node_id_name:
        remove_node(tree, entity, prop)
        node = None

    # Create new node
    if not node:
        node = new_node(tree, entity, prop, node_id_name, label)
        replaced = True

    if replaced_status:
        return node, replaced

    return node

def get_tree(entity):

    #m = re.match(r'tl\.textures\[(\d+)\]', entity.path_from_id())
    #if not m: return None
    #if not hasattr(entity.id_data, 'tl') or not hasattr(entity, 'group_node'): return None

    try:
        tree = entity.id_data
        tl = tree.tl
        group_node = tree.nodes.get(entity.group_node)
        #if not group_node or group_node.type != 'GROUP': return None
        return group_node.node_tree
    except: 
        return None

def get_mod_tree(entity):

    tl = entity.id_data.tl

    m = re.match(r'^tl\.channels\[(\d+)\].*', entity.path_from_id())
    if m:
        return entity.id_data

    m = re.match(r'^tl\.textures\[(\d+)\]\.channels\[(\d+)\].*', entity.path_from_id())
    if m:
        tex = tl.textures[int(m.group(1))]
        ch = tex.channels[int(m.group(2))]
        tree = get_tree(tex)

        mod_group = tree.nodes.get(ch.mod_group)
        if mod_group and mod_group.type == 'GROUP':
            return mod_group.node_tree

        return tree

    m = re.match(r'^tl\.textures\[(\d+)\].*', entity.path_from_id())
    if m:
        tex = tl.textures[int(m.group(1))]
        tree = get_tree(tex)

        source_group = tree.nodes.get(tex.source_group)
        if source_group and source_group.type == 'GROUP': 
            tree = source_group.node_tree

        mod_group = tree.nodes.get(tex.mod_group)
        if mod_group and mod_group.type == 'GROUP':
            return mod_group.node_tree

        return tree

def get_mask_tree(mask):

    m = re.match(r'tl\.textures\[(\d+)\]\.masks\[(\d+)\]', mask.path_from_id())
    if not m : return None

    tl = mask.id_data.tl
    tex = tl.textures[int(m.group(1))]
    tex_tree = get_tree(tex)

    group_node = tex_tree.nodes.get(mask.group_node)
    if not group_node or group_node.type != 'GROUP': return tex_tree
    return group_node.node_tree

def get_mask_source(mask):
    tree = get_mask_tree(mask)
    return tree.nodes.get(mask.source)

def get_source_tree(tex, tree=None):
    if not tree: tree = get_tree(tex)
    if not tree: return None

    if tex.source_group != '':
        source_group = tree.nodes.get(tex.source_group)
        return source_group.node_tree

    return tree

def get_tex_source(tex, tree=None):
    if not tree: tree = get_tree(tex)

    source_tree = get_source_tree(tex, tree)
    if source_tree: return source_tree.nodes.get(tex.source)
    if tree: return tree.nodes.get(tex.source)

    return None

def get_tex_mapping(tex):
    tree = get_source_tree(tex)
    return tree.nodes.get(tex.mapping)

def get_neighbor_uv_space_input(texcoord_type):
    if texcoord_type == 'UV':
        return 0.0 # Tangent Space
    if texcoord_type in {'Generated', 'Normal', 'Object'}:
        return 1.0 # Object Space
    if texcoord_type in {'Camera', 'Window', 'Reflection'}: 
        return 2.0 # View Space

def change_texture_name(tl, obj, src, tex, texes):
    if tl.halt_update: return

    tl.halt_update = True

    if tex.type == 'VCOL' and obj.type == 'MESH':

        # Get vertex color from node
        vcol = obj.data.vertex_colors.get(src.attribute_name)

        # Temporarily change its name to temp name so it won't affect unique name
        vcol.name = '___TEMP___'

        # Get unique name
        tex.name = get_unique_name(tex.name, obj.data.vertex_colors) 

        # Set vertex color name and attribute node
        vcol.name = tex.name
        src.attribute_name = tex.name

    elif tex.type == 'IMAGE':
        src.image.name = '___TEMP___'
        tex.name = get_unique_name(tex.name, bpy.data.images) 
        src.image.name = tex.name

    else:
        name = tex.name
        tex.name = '___TEMP___'
        tex.name = get_unique_name(name, texes) 

    tl.halt_update = False

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
    
def get_transition_bump_channel(tex):
    tl = tex.id_data.tl

    bump_ch = None
    for i, ch in enumerate(tex.channels):
        if tl.channels[i].type == 'NORMAL' and ch.enable and ch.enable_mask_bump:
            bump_ch = ch
            break

    return bump_ch

# BLENDER_28_GROUP_INPUT_HACK
def duplicate_lib_node_tree(node):
    node.node_tree.name += '_Copy'
    if node.node_tree.users > 1:
        node.node_tree = node.node_tree.copy()

    # Make sure input match to actual node its connected to
    for n in node.node_tree.nodes:
        if n.type == 'GROUP_INPUT':
            for i, inp in enumerate(node.inputs):
                for link in n.outputs[i].links:
                    try: link.to_socket.default_value = node.inputs[i].default_value
                    except: pass

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

def get_layer_depth(tex):

    tl = tex.id_data.tl

    upmost_found = False
    depth = 0
    cur_tex = tex
    parent_tex = tex

    while True:
        if cur_tex.parent_idx != -1:

            try: layer = tl.textures[cur_tex.parent_idx]
            except: break

            if layer.type == 'GROUP':
                parent_tex = layer
                depth += 1

        if parent_tex == cur_tex:
            break

        cur_tex = parent_tex

    return depth

def is_top_member(tex):
    
    if tex.parent_idx == -1:
        return False

    tl = tex.id_data.tl

    for i, t in enumerate(tl.textures):
        if t == tex:
            if tex.parent_idx == i-1:
                return True
            else: return False

    return False

def is_bottom_member(tex):

    if tex.parent_idx == -1:
        return False

    tl = tex.id_data.tl

    tex_idx = -1
    last_member_idx = -1
    for i, t in enumerate(tl.textures):
        if t == tex:
            tex_idx = i
        if t.parent_idx == tex.parent_idx:
            last_member_idx = i

    if tex_idx == last_member_idx:
        return True

    return False

#def get_upmost_parent_idx(tex, idx_limit = -1):
#
#    tl = tex.id_data.tl
#
#    cur_tex = tex
#    parent_tex = tex
#    parent_idx = -1
#
#    while True:
#        if cur_tex.parent_idx != -1 and cur_tex.parent_idx != idx_limit:
#
#            try: layer = tl.textures[cur_tex.parent_idx]
#            except: break
#
#            if layer.type == 'GROUP':
#                parent_tex = layer
#                parent_idx = cur_tex.parent_idx
#
#        if parent_tex == cur_tex:
#            break
#
#        cur_tex = parent_tex
#
#    return parent_idx

def get_tex_index(tex):
    tl = tex.id_data.tl

    for i, t in enumerate(tl.textures):
        if tex == t:
            return i

def get_tex_index_by_name(tl, name):

    for i, t in enumerate(tl.textures):
        if name == t.name:
            return i

    return -1

def get_parent_dict(tl):
    parent_dict = {}
    for t in tl.textures:
        if t.parent_idx != -1:
            try: parent_dict[t.name] = tl.textures[t.parent_idx].name
            except: parent_dict[t.name] = None
        else: parent_dict[t.name] = None

    return parent_dict

def set_parent_dict_val(tl, parent_dict, name, target_idx):

    if target_idx != -1:
        parent_dict[name] = tl.textures[target_idx].name
    else: parent_dict[name] = None

    return parent_dict

def get_list_of_direct_childrens(tex):
    tl = tex.id_data.tl

    if tex.type != 'GROUP':
        return []

    tex_idx = get_tex_index(tex)

    childs = []
    for t in tl.textures:
        if t.parent_idx == tex_idx:
            childs.append(t)

    return childs

def get_list_of_parent_ids(tex):

    tl = tex.id_data.tl

    cur_tex = tex
    parent_tex = tex
    parent_list = []

    while True:
        if cur_tex.parent_idx != -1:

            try: layer = tl.textures[cur_tex.parent_idx]
            except: break

            if layer.type == 'GROUP':
                parent_tex = layer
                parent_list.append(cur_tex.parent_idx)

        if parent_tex == cur_tex:
            break

        cur_tex = parent_tex

    return parent_list

def get_last_chained_up_layer_ids(tex, idx_limit):

    tl = tex.id_data.tl
    tex_idx = get_tex_index(tex)

    cur_tex = tex
    parent_tex = tex
    parent_idx = tex_idx

    while True:
        if cur_tex.parent_idx != -1 and cur_tex.parent_idx != idx_limit:

            try: layer = tl.textures[cur_tex.parent_idx]
            except: break

            if layer.type == 'GROUP':
                parent_tex = layer
                parent_idx = cur_tex.parent_idx

        if parent_tex == cur_tex:
            break

        cur_tex = parent_tex

    return parent_idx

def has_childrens(tex):

    tl = tex.id_data.tl

    if tex.type != 'GROUP':
        return False

    tex_idx = get_tex_index(tex)

    if tex_idx < len(tl.textures)-1:
        neighbor_tex = tl.textures[tex_idx+1]
        if neighbor_tex.parent_idx == tex_idx:
            return True

    return False

def get_last_child_idx(tex): #, very_last=False):

    tl = tex.id_data.tl
    tex_idx = get_tex_index(tex)

    if tex.type != 'GROUP': 
        return tex_idx

    for i, t in reversed(list(enumerate(tl.textures))):
        if i > tex_idx and tex_idx in get_list_of_parent_ids(t):
            return i

    return tex_idx

def get_upper_neighbor(tex):

    tl = tex.id_data.tl
    tex_idx = get_tex_index(tex)

    if tex_idx == 0:
        return None, None

    if tex.parent_idx == tex_idx-1:
        return tex_idx-1, tl.textures[tex_idx-1]

    upper_tex = tl.textures[tex_idx-1]

    neighbor_idx = get_last_chained_up_layer_ids(upper_tex, tex.parent_idx)
    neighbor_tex = tl.textures[neighbor_idx]

    return neighbor_idx, neighbor_tex

def get_lower_neighbor(tex):

    tl = tex.id_data.tl
    tex_idx = get_tex_index(tex)
    last_index = len(tl.textures)-1

    if tex_idx == last_index:
        return None, None

    if tex.type == 'GROUP':
        last_child_idx = get_last_child_idx(tex)

        if last_child_idx == last_index:
            return None, None

        neighbor_idx = last_child_idx + 1
    else:
        neighbor_idx = tex_idx+1

    neighbor_tex = tl.textures[neighbor_idx]

    return neighbor_idx, neighbor_tex

def is_valid_to_remove_bump_nodes(tex, ch):

    if tex.type == 'COLOR' and ((ch.enable_mask_bump and ch.enable) or len(tex.masks) == 0 or ch.mask_bump_chain == 0):
        return True

    return False

#def get_io_index(tex, root_ch, alpha=False):
#    if alpha:
#        return root_ch.io_index+1
#    return root_ch.io_index
#
#def get_alpha_io_index(tex, root_ch):
#    return get_io_index(tex, root_ch, alpha=True)

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
