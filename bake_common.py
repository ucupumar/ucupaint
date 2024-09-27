import bpy, time, os, numpy, tempfile
from bpy.props import *
from .common import *
from .input_outputs import *
from .node_connections import *
from . import lib, Layer, ImageAtlas, UDIM

BL28_HACK = True

BAKE_PROBLEMATIC_MODIFIERS = {
        'MIRROR',
        'SOLIDIFY',
        'ARRAY',
        }

JOIN_PROBLEMATIC_TEXCOORDS = {
        'Object',
        'Generated',
        }

EMPTY_IMG_NODE = '___EMPTY_IMAGE__'
ACTIVE_UV_NODE = '___ACTIVE_UV__'
TEMP_EMIT_WHITE = '__EMIT_WHITE__'
TEMP_MATERIAL = '__TEMP_MATERIAL_'

def get_problematic_modifiers(obj):
    pms = []

    for m in obj.modifiers:
        if m.type in BAKE_PROBLEMATIC_MODIFIERS:
            # Mirror modifier is not problematic if mirror uv is used
            if m.type == 'MIRROR':
                if not m.use_mirror_u and not m.use_mirror_v:
                    if is_bl_newer_than(2, 80):
                        if m.offset_u == 0.0 and m.offset_v == 0.0:
                            pms.append(m)
                    else: pms.append(m)
            else: pms.append(m)

    return pms

''' Search for texcoord node that output join problematic texcoords outside yp '''
def search_join_problematic_texcoord(tree, node):
    for inp in node.inputs:
        for link in inp.links:
            from_node = link.from_node
            from_socket = link.from_socket
            if from_node.type == 'TEX_COORD' and from_socket.name in JOIN_PROBLEMATIC_TEXCOORDS:
                return True
            elif node.type == 'GROUP' and node.node_tree and not node.node_tree.yp.is_ypaint_node:
                output = [n for n in node.node_tree.nodes if n.type == 'GROUP_OUTPUT' and n.is_active_output]
                if output:
                    if search_join_problematic_texcoord(node.node_tree, output[0]):
                        return True
            if search_join_problematic_texcoord(tree, from_node):
                return True

    return False

def is_join_objects_problematic(yp, mat=None):
    for layer in yp.layers:

        for mask in layer.masks:
            if mask.type in {'VCOL', 'HEMI', 'COLOR_ID'}: 
                continue
            if mask.texcoord_type in JOIN_PROBLEMATIC_TEXCOORDS or mask.type in {'OBJECT_INDEX'}:
                return True

        if layer.type in {'VCOL', 'COLOR', 'BACKGROUND', 'HEMI', 'GROUP'}: 
            continue
        if layer.texcoord_type in JOIN_PROBLEMATIC_TEXCOORDS:
            return True

    if mat:
        output = get_material_output(mat)
        if output: 
            if search_join_problematic_texcoord(mat.node_tree, output):
                return True

    return False

def bake_object_op():
    try:
        bpy.ops.object.bake()
    except Exception as e:
        scene = bpy.context.scene
        if scene.cycles.device == 'GPU':
            print('EXCEPTIION: GPU baking failed! Trying to use CPU...')
            scene.cycles.device = 'CPU'

            bpy.ops.object.bake()
        else:
            print('EXCEPTIION:', e)

def remember_before_bake(yp=None, mat=None):
    book = {}
    book['scene'] = scene = bpy.context.scene
    book['obj'] = obj = bpy.context.object
    book['mode'] = obj.mode
    uv_layers = get_uv_layers(obj)
    ypui = bpy.context.window_manager.ypui

    # Remember render settings
    book['ori_engine'] = scene.render.engine
    book['ori_bake_type'] = scene.cycles.bake_type
    book['ori_samples'] = scene.cycles.samples
    book['ori_threads_mode'] = scene.render.threads_mode
    book['ori_margin'] = scene.render.bake.margin
    book['ori_use_clear'] = scene.render.bake.use_clear
    book['ori_normal_space'] = scene.render.bake.normal_space
    book['ori_simplify'] = scene.render.use_simplify
    book['ori_device'] = scene.cycles.device
    if hasattr(scene.render.bake, 'use_pass_direct'): book['ori_use_pass_direct'] = scene.render.bake.use_pass_direct
    if hasattr(scene.render.bake, 'use_pass_indirect'): book['ori_use_pass_indirect'] = scene.render.bake.use_pass_indirect
    if hasattr(scene.render.bake, 'use_pass_diffuse'): book['ori_use_pass_diffuse'] = scene.render.bake.use_pass_diffuse
    if hasattr(scene.render.bake, 'use_pass_emit'): book['ori_use_pass_emit'] = scene.render.bake.use_pass_emit
    if hasattr(scene.render.bake, 'use_pass_ambient_occlusion'):
        book['ori_use_pass_ambient_occlusion'] = scene.render.bake.use_pass_ambient_occlusion

    if hasattr(scene.render, 'tile_x'):
        book['ori_tile_x'] = scene.render.tile_x
        book['ori_tile_y'] = scene.render.tile_y
    book['ori_use_selected_to_active'] = scene.render.bake.use_selected_to_active
    if hasattr(scene.render.bake, 'max_ray_distance'):
        book['ori_max_ray_distance'] = scene.render.bake.max_ray_distance
    book['ori_cage_extrusion'] = scene.render.bake.cage_extrusion
    book['ori_use_cage'] = scene.render.bake.use_cage
    if is_bl_newer_than(2, 80):
        book['ori_cage_object_name'] = scene.render.bake.cage_object.name if scene.render.bake.cage_object else ''
    else: book['ori_cage_object_name'] = scene.render.bake.cage_object

    if hasattr(scene.render.bake, 'margin_type'):
        book['ori_margin_type'] = scene.render.bake.margin_type

    if hasattr(scene.cycles, 'use_denoising'):
        book['ori_use_denoising'] = scene.cycles.use_denoising

    if hasattr(scene.cycles, 'use_fast_gi'):
        book['ori_use_fast_gi'] = scene.cycles.use_fast_gi

    if hasattr(scene.render.bake, 'target'):
        book['ori_bake_target'] = scene.render.bake.target

    if is_bl_newer_than(2, 80):
        book['ori_material_override'] = bpy.context.view_layer.material_override
    else: book['ori_material_override'] = scene.render.layers.active.material_override

    # Multires related
    book['ori_use_bake_multires'] = scene.render.use_bake_multires
    book['ori_use_bake_clear'] = scene.render.use_bake_clear
    book['ori_render_bake_type'] = scene.render.bake_type
    book['ori_bake_margin'] = scene.render.bake_margin

    if is_bl_newer_than(2, 81) and not is_bl_newer_than(3) and scene.cycles.device == 'GPU' and 'compute_device_type' in bpy.context.preferences.addons['cycles'].preferences:
        book['compute_device_type'] = bpy.context.preferences.addons['cycles'].preferences['compute_device_type']

    # Remember uv
    book['ori_active_uv'] = uv_layers.active.name
    active_render_uvs = [u for u in uv_layers if u.active_render]
    if active_render_uvs:
        book['ori_active_render_uv'] = active_render_uvs[0].name

    # Remember scene objects
    if is_bl_newer_than(2, 80):
        book['ori_hide_selects'] = [o for o in bpy.context.view_layer.objects if o.hide_select]
        book['ori_active_selected_objs'] = [o for o in bpy.context.view_layer.objects if o.select_get()]
        book['ori_hide_renders'] = [o for o in bpy.context.view_layer.objects if o.hide_render]
        book['ori_hide_viewports'] = [o for o in bpy.context.view_layer.objects if o.hide_viewport]
        book['ori_hide_objs'] = [o for o in bpy.context.view_layer.objects if o.hide_get()]

        layer_cols = get_all_layer_collections([], bpy.context.view_layer.layer_collection)

        book['ori_layer_col_hide_viewport'] = [lc for lc in layer_cols if lc.hide_viewport]
        book['ori_layer_col_exclude'] = [lc for lc in layer_cols if lc.exclude]
        book['ori_col_hide_viewport'] = [c for c in bpy.data.collections if c.hide_viewport]
        book['ori_col_hide_render'] = [c for c in bpy.data.collections if c.hide_render]

    else: 
        book['ori_hide_selects'] = [o for o in scene.objects if o.hide_select]
        book['ori_active_selected_objs'] = [o for o in scene.objects if o.select]
        book['ori_hide_renders'] = [o for o in scene.objects if o.hide_render]
        book['ori_hide_objs'] = [o for o in scene.objects if o.hide]
        book['ori_scene_layers'] = [i for i in range(20) if scene.layers[i]]

    # Remember image editor images
    book['editor_images'] = [a.spaces[0].image for a in bpy.context.screen.areas if a.type == 'IMAGE_EDITOR']
    book['editor_pins'] = [a.spaces[0].use_image_pin for a in bpy.context.screen.areas if a.type == 'IMAGE_EDITOR']

    # Remember world settings
    if scene.world:
        book['ori_distance'] = scene.world.light_settings.distance

    # Remember ypui
    #book['ori_disable_temp_uv'] = ypui.disable_auto_temp_uv_update

    # Remember yp
    if yp:
        book['parallax_ch'] = get_root_parallax_channel(yp)
    else: book['parallax_ch'] = None

    # Remember material props
    if mat:
        book['ori_bsdf'] = mat.yp.ori_bsdf

    # Remember all objects using the same material
    objs = get_all_objects_with_same_materials(obj.active_material, True)
    book['ori_mat_objs'] = [o.name for o in objs]
    book['ori_mat_objs_active_nodes'] = []

    # Remember other material active nodes
    for o in objs:
        active_node_names = []
        for m in o.data.materials:
            if m and m.use_nodes and m.node_tree.nodes.active:
                active_node_names.append(m.node_tree.nodes.active.name)
                continue
            active_node_names.append('')

        book['ori_mat_objs_active_nodes'].append(active_node_names)

    return book

def get_active_render_uv_node(tree, active_render_uv_name):
    act_uv = tree.nodes.get(ACTIVE_UV_NODE)
    if not act_uv:
        act_uv = tree.nodes.new('ShaderNodeUVMap')
        act_uv.name = ACTIVE_UV_NODE
        act_uv.uv_map = active_render_uv_name

    return act_uv

def add_active_render_uv_node(tree, active_render_uv_name):
    for n in tree.nodes:
        # Check for vector input
        if n.bl_idname.startswith('ShaderNodeTex'):
            vec = n.inputs.get('Vector')
            if vec and len(vec.links) == 0:
                act_uv = get_active_render_uv_node(tree, active_render_uv_name)
                tree.links.new(act_uv.outputs[0], vec)

        # Check for texcoord node
        if n.type == 'TEX_COORD':
            for l in n.outputs['UV'].links:
                act_uv = get_active_render_uv_node(tree, active_render_uv_name)
                tree.links.new(act_uv.outputs[0], l.to_socket)

        # Check for normal map
        if n.type == 'NORMAL_MAP':
            n.uv_map = active_render_uv_name

        if n.type == 'GROUP' and n.node_tree and not n.node_tree.yp.is_ypaint_node:
            add_active_render_uv_node(n.node_tree, active_render_uv_name)

def prepare_other_objs_channels(yp, other_objs):

    ch_other_objects = []
    ch_other_mats = []
    ch_other_sockets = []
    ch_other_defaults = []

    ori_mat_no_nodes = []

    valid_bsdf_types = ['BSDF_PRINCIPLED', 'BSDF_DIFFUSE', 'EMISSION']

    for ch in yp.channels:
        objs = []
        mats = []
        sockets = []
        defaults = []

        for o in other_objs:

            # Normal channel will always use any objects
            if ch.type == 'NORMAL':
                objs.append(o)
                continue

            # Set new material if there's no material
            if len(o.data.materials) == 0:
                temp_mat = get_temp_default_material()
                o.data.materials.append(temp_mat)
            else:
                for i, m in enumerate(o.data.materials):
                    if m == None:
                        temp_mat = get_temp_default_material()
                        o.data.materials[i] = temp_mat
                    elif not m.use_nodes:
                        if m not in ori_mat_no_nodes:
                            ori_mat_no_nodes.append(m)
                        m.use_nodes = True

            for mat in o.data.materials:

                if mat == None: continue
                if mat in mats: continue
                if not mat.use_nodes: continue

                # Get material output
                output = get_material_output(mat)
                if not output: continue

                socket = None
                default = None

                # If material originally aren't using nodes
                if mat in ori_mat_no_nodes:
                    if ch.name == 'Color' and hasattr(mat, 'diffuse_color'):
                        default = mat.diffuse_color
                    elif hasattr(mat, ch.name):
                        default = getattr(mat, ch.name)
                    elif hasattr(mat, ch.name.lower()):
                        default = getattr(mat, ch.name.lower())

                # Search material nodes for yp node
                yp_node = get_closest_yp_node_backward(output)
                if yp_node:
                    oyp = yp_node.node_tree.yp
                    if ch.name in oyp.channels:
                        socket = yp_node.outputs[ch.name]

                # Check for possible sockets available on the bsdf node
                if not socket:
                    # Search for main bsdf
                    bsdf_node = get_closest_bsdf_backward(output, valid_bsdf_types)

                    if ch.name == 'Color' and bsdf_node.type == 'BSDF_PRINCIPLED':
                        socket = bsdf_node.inputs['Base Color']

                    elif ch.name in bsdf_node.inputs:
                        socket = bsdf_node.inputs[ch.name]

                    if socket:
                        if len(socket.links) == 0:
                            if default == None:
                                default = socket.default_value
                        else:
                            socket = socket.links[0].from_socket

                # Append objects and materials if socket is found
                if socket or default:
                    mats.append(mat)
                    sockets.append(socket)
                    defaults.append(default)

                    if o not in objs:
                        objs.append(o)

        ch_other_objects.append(objs)
        ch_other_mats.append(mats)
        ch_other_sockets.append(sockets)
        ch_other_defaults.append(defaults)

    return ch_other_objects, ch_other_mats, ch_other_sockets, ch_other_defaults, ori_mat_no_nodes

def recover_other_objs_channels(other_objs, ori_mat_no_nodes):
    for o in other_objs:
        if len(o.data.materials) == 1 and o.data.materials[0].name == TEMP_MATERIAL:
            o.data.materials.clear()
        else:
            for i, m in reversed(list(enumerate(o.data.materials))):
                if m.name == TEMP_MATERIAL:
                    o.data.materials.pop(index=i)

    for m in ori_mat_no_nodes:
        m.use_nodes = False

    remove_temp_default_material()

def prepare_bake_settings(book, objs, yp=None, samples=1, margin=5, uv_map='', bake_type='EMIT', 
        disable_problematic_modifiers=False, hide_other_objs=True, bake_from_multires=False, 
        tile_x=64, tile_y=64, use_selected_to_active=False, max_ray_distance=0.0, cage_extrusion=0.0,
        bake_target = 'IMAGE_TEXTURES',
        source_objs=[], bake_device='CPU', use_denoising=False, margin_type='ADJACENT_FACES', cage_object_name=''):

    scene = bpy.context.scene
    ypui = bpy.context.window_manager.ypui

    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.render.threads_mode = 'AUTO'
    scene.render.bake.margin = margin
    #scene.render.bake.use_clear = True
    scene.render.bake.use_clear = False
    scene.render.bake.use_selected_to_active = use_selected_to_active
    if hasattr(scene.render.bake, 'max_ray_distance'):
        scene.render.bake.max_ray_distance = max_ray_distance
    scene.render.bake.cage_extrusion = cage_extrusion
    cage_object = bpy.data.objects.get(cage_object_name) if cage_object_name != '' else None
    scene.render.bake.use_cage = True if cage_object else False
    if cage_object: 
        if is_bl_newer_than(2, 80): scene.render.bake.cage_object = cage_object
        else: scene.render.bake.cage_object = cage_object.name
    scene.render.use_simplify = False
    if hasattr(scene.render.bake, 'use_pass_direct'): scene.render.bake.use_pass_direct = True
    if hasattr(scene.render.bake, 'use_pass_indirect'): scene.render.bake.use_pass_indirect = True
    if hasattr(scene.render.bake, 'use_pass_diffuse'): scene.render.bake.use_pass_diffuse = True
    if hasattr(scene.render.bake, 'use_pass_emit'): scene.render.bake.use_pass_emit = True
    if hasattr(scene.render.bake, 'use_pass_ambient_occlusion'): scene.render.bake.use_pass_ambient_occlusion = True

    if hasattr(scene.render, 'tile_x'):
        scene.render.tile_x = tile_x
        scene.render.tile_y = tile_y

    if hasattr(scene.cycles, 'use_denoising'):
        scene.cycles.use_denoising = use_denoising

    if hasattr(scene.render.bake, 'target'):
        scene.render.bake.target = bake_target

    if hasattr(scene.render.bake, 'margin_type'):
        scene.render.bake.margin_type = margin_type

    if is_bl_newer_than(2, 80):
        bpy.context.view_layer.material_override = None
    else: scene.render.layers.active.material_override = None

    if bake_from_multires:
        scene.render.use_bake_multires = True
        scene.render.bake_type = bake_type
        scene.render.bake_margin = margin
        scene.render.use_bake_clear = False
    else: 
        scene.render.use_bake_multires = False
        scene.cycles.bake_type = bake_type

    # Old blender will always use CPU
    if not is_bl_newer_than(2, 80):
        scene.cycles.device = 'CPU'
    else: scene.cycles.device = bake_device

    # Use CUDA bake if Optix is selected
    if (is_bl_newer_than(2, 81) and not is_bl_newer_than(3) and 'compute_device_type' in bpy.context.preferences.addons['cycles'].preferences and
            bpy.context.preferences.addons['cycles'].preferences['compute_device_type'] == 3):
        #scene.cycles.device = 'CPU'
        bpy.context.preferences.addons['cycles'].preferences['compute_device_type'] = 1

    if bake_type == 'NORMAL':
        scene.render.bake.normal_space = 'TANGENT'

    # Disable other object selections and select only active object
    if is_bl_newer_than(2, 80):

        # Disable exclude only works on source objects
        for o in source_objs:
            layer_cols = get_object_parent_layer_collections([], bpy.context.view_layer.layer_collection, o)
            for lc in layer_cols:
                lc.exclude = False

        # Show viewport and render of object layer collection
        for o in objs:
            o.hide_select = False
            o.hide_viewport = False
            o.hide_render = False
            layer_cols = get_object_parent_layer_collections([], bpy.context.view_layer.layer_collection, o)
            for lc in layer_cols:
                lc.hide_viewport = False
                lc.collection.hide_viewport = False
                lc.collection.hide_render = False

        if hide_other_objs:
            for o in bpy.context.view_layer.objects:
                if o not in objs:
                    o.hide_render = True

        #for o in scene.objects:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)

        for obj in objs:
            obj.hide_set(False)

            if bake_from_multires:
                # Do not select object without multires modifier
                mod = get_multires_modifier(obj)
                if not mod:
                    obj.select_set(False)
                else: obj.select_set(True)
            else:
                obj.select_set(True)
            #print(obj.name, obj.hide_render, obj.select_get())

        # Disable material override
        book['material_override'] = bpy.context.view_layer.material_override
        bpy.context.view_layer.material_override = None

    else:

        for obj in objs:
            obj.hide_select = False
            obj.hide_render = False

        if hide_other_objs:
            for o in scene.objects:
                if o not in objs:
                    o.hide_render = True

        for o in scene.objects:
            o.select = False

        for obj in objs:
            obj.hide = False
            obj.select = True

            # Unhide layer objects
            if not in_active_279_layer(obj):
                for i in range(20):
                    if obj.layers[i] and not scene.layers[i]:
                        scene.layers[i] = True
                        break

            # Blender 2.76 need all objects to be UV unwrapped
            if not is_bl_newer_than(2, 77):
                ori_active_object = scene.objects.active
                uv_layers = get_uv_layers(obj)
                if len(uv_layers) == 0:
                    scene.objects.active = obj
                    bpy.ops.node.y_add_simple_uvs()
                if scene.objects.active != ori_active_object:
                    scene.objects.active = ori_active_object

    book['obj_mods_lib'] = {}
    if disable_problematic_modifiers:
        for obj in objs:
            book['obj_mods_lib'][obj.name] = {}
            book['obj_mods_lib'][obj.name]['disabled_mods'] = []
            book['obj_mods_lib'][obj.name]['disabled_viewport_mods'] = []

            for mod in get_problematic_modifiers(obj):

                if mod.show_render:
                    mod.show_render = False
                    book['obj_mods_lib'][obj.name]['disabled_mods'].append(mod.name)

                if mod.show_viewport:
                    mod.show_viewport = False
                    book['obj_mods_lib'][obj.name]['disabled_viewport_mods'].append(mod.name)

    # Disable auto temp uv update
    #ypui.disable_auto_temp_uv_update = True

    # Set to object mode
    try: bpy.ops.object.mode_set(mode = 'OBJECT')
    except: pass

    # Disable parallax channel
    if book['parallax_ch']:
        book['parallax_ch'].enable_parallax = False

    for o in objs:
        mat = o.active_material
        if not mat: continue

        # Add extra uv nodes for non connected texture nodes outside yp node
        if uv_map != '':

            uv_layers = get_uv_layers(o)
            active_render_uvs = [u for u in uv_layers if u.active_render]

            if active_render_uvs:
                active_render_uv = active_render_uvs[0]

                # Only add new uv node if target uv map is different than active render uv
                if active_render_uv.name != uv_map:
                    add_active_render_uv_node(mat.node_tree, active_render_uv.name)

        for m in o.data.materials:
            if not m or not m.use_nodes: continue

            # Create temporary image texture node to make sure
            # other materials inside single object did not bake to their active image
            if m != mat:
                temp = m.node_tree.nodes.get(EMPTY_IMG_NODE)
                if not temp:
                    temp = m.node_tree.nodes.new('ShaderNodeTexImage')
                    temp.name = EMPTY_IMG_NODE
                m.node_tree.nodes.active = temp

    # Set active uv layers
    if uv_map != '':
        for obj in objs:
            if obj.type != 'MESH': continue
            #set_active_uv_layer(obj, uv_map)
            uv_layers = get_uv_layers(obj)
            uv = uv_layers.get(uv_map)
            if uv: 
                uv_layers.active = uv
                uv.active_render = True

def recover_bake_settings(book, yp=None, recover_active_uv=False, mat=None):
    scene = book['scene']
    obj = book['obj']
    uv_layers = get_uv_layers(obj)
    ypui = bpy.context.window_manager.ypui

    scene.render.engine = book['ori_engine']
    scene.cycles.samples = book['ori_samples']
    scene.cycles.bake_type = book['ori_bake_type']
    scene.render.threads_mode = book['ori_threads_mode']
    scene.render.bake.margin = book['ori_margin']
    scene.render.bake.use_clear = book['ori_use_clear']
    scene.render.use_simplify = book['ori_simplify']
    scene.cycles.device = book['ori_device']
    if hasattr(scene.render.bake, 'use_pass_direct'): scene.render.bake.use_pass_direct = book['ori_use_pass_direct']
    if hasattr(scene.render.bake, 'use_pass_indirect'): scene.render.bake.use_pass_indirect = book['ori_use_pass_indirect']
    if hasattr(scene.render.bake, 'use_pass_emit'): scene.render.bake.use_pass_emit = book['ori_use_pass_emit']
    if hasattr(scene.render.bake, 'use_pass_diffuse'): scene.render.bake.use_pass_diffuse = book['ori_use_pass_diffuse']
    if hasattr(scene.render.bake, 'use_pass_ambient_occlusion'): scene.render.bake.use_pass_ambient_occlusion = book['ori_use_pass_ambient_occlusion']
    if hasattr(scene.render, 'tile_x'):
        scene.render.tile_x = book['ori_tile_x']
        scene.render.tile_y = book['ori_tile_y']
    if hasattr(scene.cycles, 'use_denoising'):
        scene.cycles.use_denoising = book['ori_use_denoising']
    if hasattr(scene.cycles, 'use_fast_gi'):
        scene.cycles.use_fast_gi = book['ori_use_fast_gi']
    if hasattr(scene.render.bake, 'target'):
        scene.render.bake.target = book['ori_bake_target']
    if hasattr(scene.render.bake, 'margin_type'):
        scene.render.bake.margin_type = book['ori_margin_type']
    scene.render.bake.use_selected_to_active = book['ori_use_selected_to_active']
    if hasattr(scene.render.bake, 'max_ray_distance'):
        scene.render.bake.max_ray_distance = book['ori_max_ray_distance']
    scene.render.bake.cage_extrusion = book['ori_cage_extrusion']
    scene.render.bake.use_cage = book['ori_use_cage']
    if book['ori_cage_object_name'] != '':
        cage_object = bpy.data.objects.get(book['ori_cage_object_name'])
        if cage_object: 
            if is_bl_newer_than(2, 80): scene.render.bake.cage_object = cage_object
            else: scene.render.bake.cage_object = cage_object.name

    if is_bl_newer_than(2, 80):
        bpy.context.view_layer.material_override = book['ori_material_override']
    else: scene.render.layers.active.material_override = book['ori_material_override']

    # Multires related
    scene.render.use_bake_multires = book['ori_use_bake_multires']
    scene.render.use_bake_clear = book['ori_use_bake_clear']
    scene.render.bake_type = book['ori_render_bake_type']
    scene.render.bake_margin = book['ori_bake_margin']

    if 'compute_device_type' in book:
        bpy.context.preferences.addons['cycles'].preferences['compute_device_type'] = book['compute_device_type']

    if is_bl_newer_than(2, 80) and 'material_override' in book:
        bpy.context.view_layer.material_override = book['material_override']

    # Recover world settings
    if scene.world:
        scene.world.light_settings.distance = book['ori_distance']

    # Recover uv
    if recover_active_uv:
        uvl = uv_layers.get(book['ori_active_uv'])
        if uvl: uv_layers.active = uvl

        # NOTE: Blender 2.90 or lower need to use active render so the UV in image editor paint mode is updated
        if not is_bl_newer_than(2, 91):
            if 'ori_active_render_uv' in book:
                uvl = uv_layers.get(book['ori_active_render_uv'])
                if uvl: uvl.active_render = True

    if is_bl_newer_than(2, 91):
        if 'ori_active_render_uv' in book:
            uvl = uv_layers.get(book['ori_active_render_uv'])
            if uvl: uvl.active_render = True

    # Recover active object and mode
    if is_bl_newer_than(2, 80):
        bpy.context.view_layer.objects.active = obj
    else: scene.objects.active = obj
    bpy.ops.object.mode_set(mode = book['mode'])

    # Disable other object selections
    if is_bl_newer_than(2, 80):

        # Recover collections
        layer_cols = get_all_layer_collections([], bpy.context.view_layer.layer_collection)
        for lc in layer_cols:
            if lc in book['ori_layer_col_hide_viewport']:
                lc.hide_viewport = True
            else: lc.hide_viewport = False

            if lc in book['ori_layer_col_exclude']:
                lc.exclude = True
            else: lc.exclude = False

        for c in bpy.data.collections:
            if c in book['ori_col_hide_viewport']:
                c.hide_viewport = True
            else: c.hide_viewport = False

            if c in book['ori_col_hide_render']:
                c.hide_render = True
            else: c.hide_render = False

        objs = [o for o in bpy.context.view_layer.objects]
        for o in objs:
            if o in book['ori_active_selected_objs']:
                o.select_set(True)
            else: o.select_set(False)
            if o in book['ori_hide_renders']:
                o.hide_render = True
            else: o.hide_render = False
            if o in book['ori_hide_viewports']:
                o.hide_viewport = True
            else: o.hide_viewport = False
            if o in book['ori_hide_objs']:
                o.hide_set(True)
            else: o.hide_set(False)
            if o in book['ori_hide_selects']:
                o.hide_select = True
            else: o.hide_select = False
    else:
        for o in scene.objects:
            if o in book['ori_active_selected_objs']:
                o.select = True
            else: o.select = False
            if o in book['ori_hide_renders']:
                o.hide_render = True
            else: o.hide_render = False
            if o in book['ori_hide_objs']:
                o.hide = True
            else: o.hide = False
            if o in book['ori_hide_selects']:
                o.hide_select = True
            else: o.hide_select = False
        for i in range(20):
            scene.layers[i] = i in book['ori_scene_layers']

    # Recover image editors
    for i, area in enumerate([a for a in bpy.context.screen.areas if a.type == 'IMAGE_EDITOR']):
        # Some image can be deleted after baking process so use try except
        try: area.spaces[0].image = book['editor_images'][i]
        except: area.spaces[0].image = None

        area.spaces[0].use_image_pin = book['editor_pins'][i]

    # Recover active object

    # Recover ypui
    #ypui.disable_auto_temp_uv_update = book['ori_disable_temp_uv']

    # Recover parallax
    if book['parallax_ch']:
        book['parallax_ch'].enable_parallax = True

    # Recover modifiers
    for obj_name, lib in book['obj_mods_lib'].items():
        o = get_scene_objects().get(obj_name)
        if o:
            for mod_name in lib['disabled_mods']:
                mod = o.modifiers.get(mod_name)
                if mod: mod.show_render = True

            for mod_name in lib['disabled_viewport_mods']:
                mod = o.modifiers.get(mod_name)
                if mod: mod.show_viewport = True

    if mat:
        # Recover stored material original bsdf for preview
        if 'ori_bsdf' in book:
            mat.yp.ori_bsdf = book['ori_bsdf']

    # Recover other material active nodes
    if 'ori_mat_objs' in book:
        for i, o_name in enumerate(book['ori_mat_objs']):
            o = bpy.data.objects.get(o_name)
            if not o: continue
            for j, m in enumerate(o.data.materials):
                if not m or not m.use_nodes: continue
                active_node = m.node_tree.nodes.get(book['ori_mat_objs_active_nodes'][i][j])
                m.node_tree.nodes.active = active_node

                # Remove temporary nodes
                temp = m.node_tree.nodes.get(EMPTY_IMG_NODE)
                if temp: m.node_tree.nodes.remove(temp)
                #act_uv = m.node_tree.nodes.get(ACTIVE_UV_NODE)
                #if act_uv: m.node_tree.nodes.remove(act_uv)

def prepare_composite_settings(res_x=1024, res_y=1024, use_hdr=False):
    book = {}

    # Remember original scene
    book['ori_scene_name'] = bpy.context.scene.name

    # Remember active object and view layer
    book['ori_viewlayer'] = bpy.context.window.view_layer.name if bpy.context.window.view_layer and is_bl_newer_than(2, 80) else ''
    book['ori_object'] = bpy.context.object.name if bpy.context.object else ''

    # Check if original viewport is using camera view
    area = bpy.context.area
    book['ori_camera_view'] = area.type == 'VIEW_3D' and area.spaces[0].region_3d.view_perspective == 'CAMERA'

    # Create new temporary scene
    scene = bpy.data.scenes.new(name='TEMP_COMPOSITE_SCENE')
    bpy.context.window.scene = scene

    # Set up render settings
    scene.cycles.samples = 1
    if hasattr(scene, 'eevee'):
        scene.eevee.taa_render_samples = 1
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = 1.0
    scene.render.pixel_aspect_y = 1.0
    scene.use_nodes = True
    scene.view_settings.view_transform = 'Standard' if is_bl_newer_than(2, 80) else 'Default'

    # Float/HDR image related
    scene.render.image_settings.file_format = 'OPEN_EXR' if use_hdr else 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '32' if use_hdr else '8'

    # Remember temp scene name
    book['temp_scene_name'] = scene.name

    # Create temporary camera
    if not scene.camera:
        cam_data = bpy.data.cameras.new('TEMP_CAM')
        cam_obj = bpy.data.objects.new('TEMP_CAM', cam_data)
        link_object(scene, cam_obj)
        scene.camera = cam_obj
        book['temp_camera_name'] = cam_obj.name

    return book

def recover_composite_settings(book):
    scene = bpy.data.scenes.get(book['temp_scene_name'])

    # Remove temporary objects
    if 'temp_camera_name' in book:
        cam_obj = bpy.data.objects.get(book['temp_camera_name'])
        if cam_obj:
            cam = cam_obj.data
            remove_datablock(bpy.data.objects, cam_obj)
            remove_datablock(bpy.data.cameras, cam)

    # Remove temp scene
    remove_datablock(bpy.data.scenes, scene)

    # Go back to original scene
    scene = bpy.data.scenes.get(book['ori_scene_name'])
    bpy.context.window.scene = scene

    # Recover camera view
    if book['ori_camera_view']:
        bpy.context.area.spaces[0].region_3d.view_perspective = 'CAMERA'

    # Recover view layer
    if is_bl_newer_than(2, 80):
        ori_viewlayer = bpy.context.scene.view_layers.get(book['ori_viewlayer'])
        if ori_viewlayer and bpy.context.window.view_layer != ori_viewlayer:
            bpy.context.window.view_layer = ori_viewlayer

    # Recover active object
    ori_object = bpy.data.objects.get(book['ori_object'])
    if ori_object and bpy.context.object != ori_object:
        set_active_object(ori_object)

def denoise_image(image):
    if not is_bl_newer_than(2, 81): return image

    T = time.time()
    print('DENOISE: Doing Denoise pass on', image.name + '...')

    # Preparing settings
    book = prepare_composite_settings(use_hdr=image.is_float)
    scene = bpy.context.scene

    # Set up compositor
    tree = scene.node_tree
    composite = [n for n in tree.nodes if n.type == 'COMPOSITE'][0]
    denoise = tree.nodes.new('CompositorNodeDenoise')
    denoise.use_hdr = image.is_float
    image_node = tree.nodes.new('CompositorNodeImage')
    image_node.image = image

    gamma = None
    if image.colorspace_settings.name != get_srgb_name() and not image.is_float:
        gamma = tree.nodes.new('CompositorNodeGamma')
        gamma.inputs[1].default_value = 2.2

    rgb = image_node.outputs[0]
    if gamma:
        tree.links.new(rgb, gamma.inputs[0])
        rgb = gamma.outputs[0]
    tree.links.new(rgb, denoise.inputs['Image'])
    rgb = denoise.outputs[0]
    tree.links.new(rgb, composite.inputs[0])

    if image.source == 'TILED':
        tilenums = [tile.number for tile in image.tiles]
    else: tilenums = [1001]

    # Get temporary filepath
    ext = 'exr' if image.is_float else 'png'
    filepath = os.path.join(tempfile.gettempdir(), 'TEST_RENDER__.' + ext)

    for tilenum in tilenums:

        # Swap tile to 1001 to access the data
        if tilenum != 1001:
            UDIM.swap_tile(image, 1001, tilenum)

        # Set render resolution
        scene.render.resolution_x = image.size[0]
        scene.render.resolution_y = image.size[1]

        # Render image!
        bpy.ops.render.render()

        # Save the image
        render_result = next(img for img in bpy.data.images if img.type == "RENDER_RESULT")
        render_result.save_render(filepath)
        temp_image = bpy.data.images.load(filepath)

        # Copy image pixels
        copy_image_pixels(temp_image, image)

        # Remove temp image
        remove_datablock(bpy.data.images, temp_image)
        os.remove(filepath)

        # Swap back the tile
        if tilenum != 1001:
            UDIM.swap_tile(image, 1001, tilenum)

    # Recover settings
    recover_composite_settings(book)

    print('DENOISE:', image.name, 'denoise pass is done at', '{:0.2f}'.format(time.time() - T), 'seconds!')
    return image

def blur_image(image, alpha_aware=True, factor=1.0, samples=512, bake_device='CPU'):
    T = time.time()
    print('BLUR: Doing Blur pass on', image.name + '...')
    book = remember_before_bake()

    width = image.size[0]
    height = image.size[1]

    # Set active collection to be root collection
    if is_bl_newer_than(2, 80):
        ori_layer_collection = bpy.context.view_layer.active_layer_collection
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection

    # Create new plane
    bpy.ops.object.mode_set(mode = 'OBJECT')
    plane_obj = create_plane_on_object_mode()

    prepare_bake_settings(book, [plane_obj], samples=samples, margin=0, bake_device=bake_device)

    # Create temporary material
    mat = bpy.data.materials.new('__TEMP__')
    mat.use_nodes = True
    plane_obj.active_material = mat

    # Create nodes
    output = get_active_mat_output_node(mat.node_tree)
    emi = mat.node_tree.nodes.new('ShaderNodeEmission')

    uv_map = mat.node_tree.nodes.new('ShaderNodeUVMap')
    #uv_map.uv_map = 'UVMap' # Will use active UV instead since every language has different default UV name

    blur = mat.node_tree.nodes.new('ShaderNodeGroup')
    blur.node_tree = get_node_tree_lib(lib.BLUR_VECTOR)
    blur.inputs[0].default_value = factor

    source_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    target_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    target_tex.image = image

    # Connect nodes

    mat.node_tree.links.new(uv_map.outputs[0], blur.inputs[1])
    mat.node_tree.links.new(blur.outputs[0], source_tex.inputs[0])

    mat.node_tree.links.new(emi.outputs[0], output.inputs[0])
    mat.node_tree.nodes.active = target_tex

    if image.source == 'TILED':
        tilenums = [tile.number for tile in image.tiles]
    else: tilenums = [1001]

    for tilenum in tilenums:

        # Swap tile to 1001 to access the data
        if tilenum != 1001:
            UDIM.swap_tile(image, 1001, tilenum)

        width = image.size[0]
        height = image.size[1]

        # Copy image
        image_copy = duplicate_image(image)

        # Set source image
        source_tex.image = image_copy

        # Blender 2.79 need to set these parameter to correct the gamma
        if not is_bl_newer_than(2, 80) :
            if image.colorspace_settings.name == get_srgb_name():
                source_tex.color_space = 'COLOR'
            else: source_tex.color_space = 'NONE' 

        # Connect nodes again
        mat.node_tree.links.new(source_tex.outputs[0], emi.inputs[0])
        mat.node_tree.links.new(emi.outputs[0], output.inputs[0])

        print('BLUR: Baking blur on', image.name + '...')
        bake_object_op()

        # Run alpha pass
        if alpha_aware:
            print('BLUR: Running alpha pass to blur result of', image.name + '...')

            # TODO: Bake blur on alpha channel
            pass

            # TODO: Bake straight over on blurred rgb
            pass

            # TODO: Copy result to main image
            #copy_image_channel_pixels(image_copy, image, 3, 3)

        # Swap back the tile
        if tilenum != 1001:
            UDIM.swap_tile(image, 1001, tilenum)

        # Remove temp images
        remove_datablock(bpy.data.images, image_copy, user=source_tex, user_prop='image')

    # Remove temp datas
    print('BLUR: Removing temporary data of blur pass')
    if alpha_aware:
        if straight_over.node_tree.users == 1:
            remove_datablock(bpy.data.node_groups, straight_over.node_tree, user=straight_over, user_prop='node_tree')

    if blur.node_tree.users == 1:
        remove_datablock(bpy.data.node_groups, blur.node_tree, user=blur, user_prop='node_tree')

    remove_datablock(bpy.data.materials, mat)
    remove_mesh_obj(plane_obj)

    # Recover settings
    recover_bake_settings(book)

    # Recover original active layer collection
    if is_bl_newer_than(2, 80):
        bpy.context.view_layer.active_layer_collection = ori_layer_collection

    print('BLUR:', image.name, 'blur pass is done at', '{:0.2f}'.format(time.time() - T), 'seconds!')

    return image

def create_plane_on_object_mode():

    if not is_bl_newer_than(2, 77):
        bpy.ops.mesh.primitive_plane_add()
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.0)
        bpy.ops.object.mode_set(mode = 'OBJECT')
    else: 
        bpy.ops.mesh.primitive_plane_add(calc_uvs=True)

    if not is_bl_newer_than(2, 80):
        return bpy.context.scene.objects.active

    return bpy.context.view_layer.objects.active

def fxaa_image(image, alpha_aware=True, bake_device='CPU', first_tile_only=False):
    T = time.time()
    print('FXAA: Doing FXAA pass on', image.name + '...')
    book = remember_before_bake()

    # Set active collection to be root collection
    if is_bl_newer_than(2, 80):
        ori_layer_collection = bpy.context.view_layer.active_layer_collection
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection

    # Create new plane
    bpy.ops.object.mode_set(mode = 'OBJECT')
    plane_obj = create_plane_on_object_mode()

    prepare_bake_settings(book, [plane_obj], samples=1, margin=0, bake_device=bake_device)

    # Create temporary material
    mat = bpy.data.materials.new('__TEMP__')
    mat.use_nodes = True
    plane_obj.active_material = mat

    # Create nodes
    output = get_active_mat_output_node(mat.node_tree)
    emi = mat.node_tree.nodes.new('ShaderNodeEmission')

    target_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    target_tex.image = image
    fxaa = mat.node_tree.nodes.new('ShaderNodeGroup')
    fxaa.node_tree = get_node_tree_lib(lib.FXAA)

    # Connect nodes
    mat.node_tree.links.new(emi.outputs[0], output.inputs[0])
    mat.node_tree.nodes.active = target_tex

    if image.source == 'TILED' and not first_tile_only:
        tilenums = [tile.number for tile in image.tiles]
    else: tilenums = [1001]

    for tilenum in tilenums:

        # Swap tile to 1001 to access the data
        if tilenum != 1001:
            UDIM.swap_tile(image, 1001, tilenum)

        width = image.size[0]
        height = image.size[1]

        # Copy image
        pixels = list(image.pixels)
        image_ori  = None
        image_copy = image.copy()
        image_copy.pixels = pixels

        # Straight over won't work if using fxaa nodes, need another bake pass
        if alpha_aware:
            image_ori = image.copy()
            image_ori.pixels = pixels

            uv_map = mat.node_tree.nodes.new('ShaderNodeUVMap')
            source_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
            source_tex.image = image_copy

            straight_over = mat.node_tree.nodes.new('ShaderNodeGroup')
            straight_over.node_tree = get_node_tree_lib(lib.STRAIGHT_OVER)
            straight_over.inputs[1].default_value = 0.0

            mat.node_tree.links.new(uv_map.outputs[0], source_tex.inputs[0])
            mat.node_tree.links.new(source_tex.outputs[0], straight_over.inputs[2])
            mat.node_tree.links.new(source_tex.outputs[1], straight_over.inputs[3])
            mat.node_tree.links.new(straight_over.outputs[0], emi.inputs[0])

            # Bake
            print('FXAA: Baking straight over on', image.name + '...')
            bake_object_op()

            pixels_1 = list(image.pixels)
            image_copy.pixels = pixels_1

        # Fill fxaa nodes
        res_x = fxaa.node_tree.nodes.get('res_x')
        res_y = fxaa.node_tree.nodes.get('res_y')
        fxaa_uv_map = fxaa.node_tree.nodes.get('uv_map')
        tex_node = fxaa.node_tree.nodes.get('tex')
        tex = tex_node.node_tree.nodes.get('tex')

        res_x.outputs[0].default_value = width
        res_y.outputs[0].default_value = height
        tex.image = image_copy
        if not is_bl_newer_than(2, 80) :
            if image.colorspace_settings.name == get_srgb_name():
                tex.color_space = 'COLOR'
            else: tex.color_space = 'NONE'

        # Connect nodes again
        mat.node_tree.links.new(fxaa.outputs[0], emi.inputs[0])
        mat.node_tree.links.new(emi.outputs[0], output.inputs[0])

        print('FXAA: Baking FXAA on', image.name + '...')
        bake_object_op()

        # Copy original alpha to baked image
        if alpha_aware:
            print('FXAA: Copying original alpha to FXAA result of', image.name + '...')
            copy_image_channel_pixels(image_ori, image, 3, 3)

        # Swap back the tile
        if tilenum != 1001:
            UDIM.swap_tile(image, 1001, tilenum)

        # Remove temp images
        remove_datablock(bpy.data.images, image_copy, user=tex, user_prop='image')
        if image_ori : 
            remove_datablock(bpy.data.images, image_ori)

    # Remove temp datas
    print('FXAA: Removing temporary data of FXAA pass')
    if alpha_aware:
        if straight_over.node_tree.users == 1:
            remove_datablock(bpy.data.node_groups, straight_over.node_tree, user=straight_over, user_prop='node_tree')

    if fxaa.node_tree.users == 1:
        remove_datablock(bpy.data.node_groups, tex_node.node_tree, user=tex_node, user_prop='node_tree')
        remove_datablock(bpy.data.node_groups, fxaa.node_tree, user=fxaa, user_prop='node_tree')

    remove_datablock(bpy.data.materials, mat)
    plane = plane_obj.data
    bpy.ops.object.delete()
    remove_datablock(bpy.data.meshes, plane)

    # Recover settings
    recover_bake_settings(book)

    # Recover original active layer collection
    if is_bl_newer_than(2, 80):
        bpy.context.view_layer.active_layer_collection = ori_layer_collection

    print('FXAA:', image.name, 'FXAA pass is done at', '{:0.2f}'.format(time.time() - T), 'seconds!')

    return image

def bake_to_vcol(mat, node, root_ch, objs, extra_channel=None, extra_multiplier=1.0, bake_alpha=False, vcol_name=''):

    # Create setup nodes
    emit = mat.node_tree.nodes.new('ShaderNodeEmission')

    if root_ch.type == 'NORMAL':

        norm = mat.node_tree.nodes.new('ShaderNodeGroup')
        if is_greater_than_280 and not is_bl_newer_than(3):
            norm.node_tree = get_node_tree_lib(lib.BAKE_NORMAL_ACTIVE_UV)
        else: norm.node_tree = get_node_tree_lib(lib.BAKE_NORMAL_ACTIVE_UV_300)

    # Get output node and remember original bsdf input
    output = get_active_mat_output_node(mat.node_tree)
    ori_bsdf = output.inputs[0].links[0].from_socket

    # Connect emit to output material
    mat.node_tree.links.new(emit.outputs[0], output.inputs[0])

    # Links to bake
    rgb = node.outputs[root_ch.name]
    if root_ch.type == 'NORMAL':
        rgb = create_link(mat.node_tree, rgb, norm.inputs[0])[0]

    if extra_channel:
        mul = simple_new_mix_node(mat.node_tree)
        mmixcol0, mmixcol1, mmixout = get_mix_color_indices(mul)
        mul.inputs[0].default_value = 1.0
        mul.inputs[mmixcol1].default_value = (extra_multiplier, extra_multiplier, extra_multiplier, 1.0)
        mul.blend_type = 'MULTIPLY'

        extra_rgb = node.outputs[extra_channel.name]
        extra_rgb = create_link(mat.node_tree, extra_rgb, mul.inputs[mmixcol0])[mmixout]

        add = simple_new_mix_node(mat.node_tree)
        amixcol0, amixcol1, amixout = get_mix_color_indices(add)
        add.inputs[0].default_value = 1.0
        add.blend_type = 'ADD'

        rgb = create_link(mat.node_tree, rgb, add.inputs[amixcol0])[amixout]
        create_link(mat.node_tree, extra_rgb, add.inputs[amixcol1])

    mat.node_tree.links.new(rgb, emit.inputs[0])

    # To avoid duplicate code, define the function here
    def bake_alpha_to_vcol():
        temp_vcol_alpha_name = '__temp__ucupaint_vertex_color_for_alpha_bake'
        for obj in objs:
            # Creates temp vertex color for baking alpha
            temp_vcol = new_vertex_color(obj, temp_vcol_alpha_name)
            set_active_vertex_color(obj, temp_vcol)
        bake_object_op()
        for obj in objs:
            vcols = get_vertex_colors(obj)
            temp_vcol = vcols.get(temp_vcol_alpha_name)
            target_vcol = vcols.get(vcol_name)
            
            # Speed up the process with numpy
            dim_rgba = 4
            temp_nvcol = numpy.zeros(len(temp_vcol.data) * dim_rgba, dtype=numpy.float32)
            target_nvcol = numpy.zeros(len(target_vcol.data) * dim_rgba, dtype=numpy.float32)
            
            temp_vcol.data.foreach_get('color', temp_nvcol)
            target_vcol.data.foreach_get('color', target_nvcol)
            temp_nvcol2D = temp_nvcol.reshape(-1, dim_rgba)
            target_nvcol2D = target_nvcol.reshape(-1, dim_rgba)

            # Moves the alpha of the temp vertex color to the target vertex color
            target_nvcol2D[:, 3] = temp_nvcol2D[:, 0]
            target_vcol.data.foreach_set('color', target_nvcol)   

            # Deletes the temp vertex color and resets the active vertex color
            vcols.remove(temp_vcol)
            set_active_vertex_color(obj, target_vcol)

    # Bake!
    # When bake_alpha is True and the channel type is 'VALUE', bake the alpha channel separately.
    if bake_alpha and root_ch.type == 'VALUE':
        bake_alpha_to_vcol()
    else:
        # Bake without alpha channel
        bake_object_op()
    
    # If bake_alpha is True and the channel type is 'RGB', Bake twice to merge Alpha channel
    if bake_alpha and root_ch.type == 'RGB' and root_ch.enable_alpha:
        # Connect channel alpha channel
        alpha_outp = node.outputs.get(root_ch.name + io_suffix['ALPHA'])
        mat.node_tree.links.new(alpha_outp, emit.inputs[0])
        bake_alpha_to_vcol()

    # Remove temp nodes
    simple_remove_node(mat.node_tree, emit)
    if root_ch.type == 'NORMAL':
        simple_remove_node(mat.node_tree, norm)

    if extra_channel:
        simple_remove_node(mat.node_tree, mul)
        simple_remove_node(mat.node_tree, add)

    # Recover original bsdf
    mat.node_tree.links.new(ori_bsdf, output.inputs[0])

def get_valid_filepath(img, use_hdr):
    if img.filepath != '':
        prefix, ext = os.path.splitext(img.filepath)
        if use_hdr and not img.is_float:
            #if ext == '.png':
            return prefix + '.exr'
        elif not use_hdr and img.is_float:
            #if ext == '.exr':
            return prefix + '.png'

    return img.filepath

def bake_channel(uv_map, mat, node, root_ch, width=1024, height=1024, target_layer=None, use_hdr=False, 
                 aa_level=1, force_use_udim=False, tilenums=[], interpolation='Linear', 
                 use_float_for_displacement=False, use_float_for_normal=False):

    print('BAKE CHANNEL: Baking', root_ch.name + ' channel...')

    tree = node.node_tree
    yp = tree.yp
    ypup = get_user_preferences()

    channel_idx = get_channel_index(root_ch)

    # Check if udim image is needed based on number of tiles
    if tilenums == []:
        objs = get_all_objects_with_same_materials(mat)
        tilenums = UDIM.get_tile_numbers(objs, uv_map)

    # Check if temp bake is necessary
    temp_baked = []
    if root_ch.type == 'NORMAL':
        for lay in yp.layers:
            if lay.type in {'HEMI'} and not lay.use_temp_bake:
                print('BAKE CHANNEL: Fake lighting layer found! Baking temporary image of ' + lay.name + ' layer...')
                temp_bake(bpy.context, lay, width, height, True, 1, bpy.context.scene.render.bake.margin, uv_map)
                temp_baked.append(lay)
            for mask in lay.masks:
                if mask.type in {'HEMI'} and not mask.use_temp_bake:
                    print('BAKE CHANNEL: Fake lighting mask found! Baking temporary image of ' + mask.name + ' mask...')
                    temp_bake(bpy.context, mask, width, height, True, 1, bpy.context.scene.render.bake.margin, uv_map)
                    temp_baked.append(mask)

    ch = None
    img = None
    segment = None
    if target_layer:
        if target_layer.type != 'IMAGE':
            return False

        source = get_layer_source(target_layer)
        if not source.image:
            return False

        if source.image.yia.is_image_atlas and target_layer.segment_name != '':
            segment = source.image.yia.segments.get(target_layer.segment_name)
        elif source.image.yua.is_udim_atlas and target_layer.segment_name != '':
            segment = source.image.yua.segments.get(target_layer.segment_name)
        else:
            img_name = source.image.name
            # Set new name for original image
            source.image.name = get_unique_name(img_name, bpy.data.images)
            img = source.image.copy()
            img.name = img_name

        ch = target_layer.channels[channel_idx]

    # Check if udim will be used
    use_udim = force_use_udim or len(tilenums) > 1 or (segment and segment.id_data.source == 'TILED')

    # Get output node and remember original bsdf input
    output = get_active_mat_output_node(mat.node_tree)
    ori_bsdf = output.inputs[0].links[0].from_socket

    # Get material output
    mat_out = get_material_output(mat)

    # Create setup nodes
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    emit = mat.node_tree.nodes.new('ShaderNodeEmission')

    if root_ch.type == 'NORMAL':

        norm = mat.node_tree.nodes.new('ShaderNodeGroup')
        if is_greater_than_280 and not is_bl_newer_than(3):
            norm.node_tree = get_node_tree_lib(lib.BAKE_NORMAL_ACTIVE_UV)
        else: norm.node_tree = get_node_tree_lib(lib.BAKE_NORMAL_ACTIVE_UV_300)

    # Set tex as active node
    mat.node_tree.nodes.active = tex

    #disp_from_socket = None
    #for l in output.inputs['Displacement'].links:
    #    disp_from_socket = l.from_socket

    # Connect emit to output material
    mat.node_tree.links.new(emit.outputs[0], output.inputs[0])

    # Image name
    if segment:
        img_name = '__TEMP_SEGMENT_'
        filepath = ''
    elif not img:
        img_name = tree.name + ' ' + root_ch.name
        filepath = ''
    else:
        img_name = img.name
        #filepath = img.filepath
        filepath = get_valid_filepath(img, use_hdr)

    if not target_layer:
        # Set nodes
        baked = tree.nodes.get(root_ch.baked)
        # Some user reported baked node can accidentally used by multiple channels,
        # So it's better to check if the baked node is unique per channel
        if not baked or not is_root_ch_prop_node_unique(root_ch, 'baked'):
            baked = new_node(tree, root_ch, 'baked', 'ShaderNodeTexImage', 'Baked ' + root_ch.name)
        if hasattr(baked, 'color_space'):
            if root_ch.colorspace == 'LINEAR' or root_ch.type == 'NORMAL':
                baked.color_space = 'NONE'
            else: baked.color_space = 'COLOR'
        baked.interpolation = interpolation
        
        # Normal related nodes
        if root_ch.type == 'NORMAL':
            baked_normal = tree.nodes.get(root_ch.baked_normal)
            if not baked_normal:
                baked_normal = new_node(tree, root_ch, 'baked_normal', 'ShaderNodeNormalMap', 'Baked Normal')
            baked_normal.uv_map = uv_map

            baked_normal_prep = tree.nodes.get(root_ch.baked_normal_prep)
            if not baked_normal_prep:
                baked_normal_prep = new_node(tree, root_ch, 'baked_normal_prep', 'ShaderNodeGroup', 
                        'Baked Normal Preparation')
                if is_greater_than_280:
                    baked_normal_prep.node_tree = get_node_tree_lib(lib.NORMAL_MAP_PREP)
                else: baked_normal_prep.node_tree = get_node_tree_lib(lib.NORMAL_MAP_PREP_LEGACY)

        # Check if image is available
        if baked.image:
            img_name = baked.image.name
            if root_ch.type == 'NORMAL':
                filepath = baked.image.filepath
            else: filepath = get_valid_filepath(baked.image, use_hdr)
            baked.image.name = '____TEMP'

    if not img:

        if segment:
            if source.image.yia.is_image_atlas:
                width = segment.width
                height = segment.height

                if source.image.yia.color == 'WHITE':
                    color = (1.0, 1.0, 1.0, 1.0)
                elif source.image.yia.color == 'BLACK':
                    color = (0.0, 0.0, 0.0, 1.0)
                else: color = (0.0, 0.0, 0.0, 0.0)
            else:
                copy_dict = {}
                segment_tilenums = UDIM.get_udim_segment_tilenums(segment)
                tilenums = UDIM.get_udim_segment_base_tilenums(segment)

                color = segment.base_color

        elif root_ch.type == 'NORMAL':
            color = (0.5, 0.5, 1.0, 1.0)

        elif root_ch.type == 'VALUE':
            val = node.inputs[root_ch.name].default_value
            color = (val, val, val, 1.0)

        elif root_ch.enable_alpha:
            color = (0.0, 0.0, 0.0, 1.0)

        else:
            # NOTE: Sometimes user like to add solid color as base color rather than edit the channel background color
            # So check the first layer that uses solid color that has no masks and use it as bake background color
            base_solid_color = None
            for layer in yp.layers:
                if not layer.enable or layer.type != 'COLOR' or len(layer.masks) > 0 or layer.parent_idx != -1: continue
                c = layer.channels[channel_idx]
                if not c.enable or c.override: continue
                source = get_layer_source(layer)
                if source:
                    base_solid_color = source.outputs[0].default_value
                    break

            if base_solid_color != None:
                col = base_solid_color
            else: col = node.inputs[root_ch.name].default_value

            col = Color((col[0], col[1], col[2]))
            col = linear_to_srgb(col)
            color = (col.r, col.g, col.b, 1.0)

        # Create new image
        #if force_use_udim or len(tilenums) > 1 or (segment and segment.id_data.source == 'TILED'):
        if use_udim:

            # Create new udim image
            img = bpy.data.images.new(name=img_name, width=width, height=height, 
                    alpha=True, tiled=True) #float_buffer=hdr)

            # Fill tiles
            if segment:
                for i, tilenum in enumerate(tilenums):
                    tile = source.image.tiles.get(segment_tilenums[i])
                    copy_dict[tilenum] = segment_tilenums[i]
                    if tile: UDIM.fill_tile(img, tilenum, color, tile.size[0], tile.size[1])
            else:
                for tilenum in tilenums:
                    UDIM.fill_tile(img, tilenum, color, width, height)

            UDIM.initial_pack_udim(img, color)

        else:
            # Create new standard image
            img = bpy.data.images.new(name=img_name,
                    width=width, height=height, alpha=True) #, alpha=True, float_buffer=hdr)
            img.generated_type = 'BLANK'

        # Set image base color
        if hasattr(img, 'use_alpha'):
            img.use_alpha = True
        img.generated_color = color

        # Set filepath
        if filepath != '' and (
                (use_udim and '.<UDIM>.' in filepath) or 
                (not use_udim and '.<UDIM>.' not in filepath)
            ):
            img.filepath = filepath

        # Use hdr
        if (root_ch.type == 'NORMAL' and use_float_for_normal) or use_hdr:
            img.use_generated_float = True

        # Set colorspace to linear
        if root_ch.colorspace == 'LINEAR' or root_ch.type == 'NORMAL' or (root_ch.type != 'NORMAL' and use_hdr):
            img.colorspace_settings.name = get_noncolor_name()
        else: img.colorspace_settings.name = get_srgb_name()

    # Bake main image
    if (
        (target_layer and (root_ch.type != 'NORMAL' or ch.normal_map_type == 'NORMAL_MAP')) or
        (not target_layer)
        ):

        # Set image to tex node
        tex.image = img

        # Links to bake
        rgb = node.outputs[root_ch.name]
        if root_ch.type == 'NORMAL':
            rgb = create_link(mat.node_tree, rgb, norm.inputs[0])[0]
        #elif root_ch.colorspace != 'LINEAR' and target_layer:
        #elif target_layer:
            #rgb = create_link(mat.node_tree, rgb, lin2srgb.inputs[0])[0]

        mat.node_tree.links.new(rgb, emit.inputs[0])

        # Bake!
        print('BAKE CHANNEL: Baking main image of ' + root_ch.name + ' channel...')
        bake_object_op()

    # Bake displacement
    if root_ch.type == 'NORMAL':

        # Make sure height outputs available
        check_all_channel_ios(yp, reconnect=True, force_height_io=True)

        if not target_layer:

            ### Normal overlay only
            if is_overlay_normal_empty(yp) and not root_ch.enable_subdiv_setup:
                # Remove baked_normal_overlay
                remove_node(tree, root_ch, 'baked_normal_overlay')
            else:

                # Original displacement connection
                ori_disp_from_node = ''
                ori_disp_from_socket = ''

                # Remove displacement link if subdiv setup is on
                if root_ch.enable_subdiv_setup:
                    for link in mat_out.inputs['Displacement'].links:
                        ori_disp_from_node = link.from_node.name
                        ori_disp_from_socket = link.from_socket.name
                        mat.node_tree.links.remove(link)
                        break

                baked_normal_overlay = tree.nodes.get(root_ch.baked_normal_overlay)
                if not baked_normal_overlay:
                    baked_normal_overlay = new_node(tree, root_ch, 'baked_normal_overlay', 'ShaderNodeTexImage', 
                            'Baked ' + root_ch.name + ' Overlay Only')
                    if hasattr(baked_normal_overlay, 'color_space'):
                        baked_normal_overlay.color_space = 'NONE'

                if baked_normal_overlay.image:
                    norm_img_name = baked_normal_overlay.image.name
                    filepath = baked_normal_overlay.image.filepath
                    #filepath = get_valid_filepath(baked_normal_overlay.image, use_hdr)
                    baked_normal_overlay.image.name = '____NORM_TEMP'
                else:
                    norm_img_name = tree.name + ' ' + root_ch.name + ' without Bump'

                # Create target image
                norm_img = img.copy()
                norm_img.name = norm_img_name
                norm_img.colorspace_settings.name = get_noncolor_name()
                color = (0.5, 0.5, 1.0, 1.0)

                if img.source == 'TILED':
                    UDIM.fill_tiles(norm_img, color)
                    UDIM.initial_pack_udim(norm_img, color)
                else: 
                    norm_img.generated_color = color
                    if filepath != '' and (
                            (use_udim and '.<UDIM>.' in filepath) or 
                            (not use_udim and '.<UDIM>.' not in filepath)
                        ):
                        norm_img.filepath = filepath

                tex.image = norm_img

                # Bake setup (doing little bit doing hacky reconnection here)
                end = tree.nodes.get(TREE_END)
                end_linear = tree.nodes.get(root_ch.end_linear)
                if end_linear:
                    ori_soc = end.inputs[root_ch.name].links[0].from_socket
                    soc = end_linear.inputs['Normal Overlay'].links[0].from_socket
                    create_link(tree, soc, end.inputs[root_ch.name])
                    #create_link(mat.node_tree, node.outputs[root_ch.name], emit.inputs[0])

                # Bake
                print('BAKE CHANNEL: Baking normal overlay image of ' + root_ch.name + ' channel...')
                bake_object_op()

                #return

                # Recover connection
                if end_linear:
                    create_link(tree, ori_soc, end.inputs[root_ch.name])

                # Set baked normal overlay image
                if baked_normal_overlay.image:
                    temp = baked_normal_overlay.image
                    img_users = get_all_image_users(baked_normal_overlay.image)
                    for user in img_users:
                        user.image = norm_img
                    remove_datablock(bpy.data.images, temp)
                else:
                    baked_normal_overlay.image = norm_img

                # Recover displacement link
                if ori_disp_from_node != '':
                    nod = mat.node_tree.nodes.get(ori_disp_from_node)
                    if nod: 
                        soc = nod.outputs.get(ori_disp_from_socket)
                        if soc:
                            mat.node_tree.links.new(soc, mat_out.inputs['Displacement'])

            ### Vector Displacement
            if not any_layers_using_vdisp(yp):
                # Remove baked_vdisp
                remove_node(tree, root_ch, 'baked_vdisp')
            else:

                baked_vdisp = tree.nodes.get(root_ch.baked_vdisp)
                if not baked_vdisp:
                    baked_vdisp = new_node(tree, root_ch, 'baked_vdisp', 'ShaderNodeTexImage', 
                            'Baked ' + root_ch.name + ' Vector Displacement')
                    if hasattr(baked_vdisp, 'color_space'):
                        baked_vdisp.color_space = 'NONE'

                if baked_vdisp.image:
                    vdisp_img_name = baked_vdisp.image.name
                    filepath = baked_vdisp.image.filepath
                    baked_vdisp.image.name = '____VDISP_TEMP'
                else:
                    vdisp_img_name = tree.name + ' ' + root_ch.name + ' Vector Displacement'

                # Set interpolation to cubic
                baked_vdisp.interpolation = 'Cubic'

                # Create target image
                vdisp_img = img.copy()
                vdisp_img.name = vdisp_img_name
                vdisp_img.use_generated_float = True
                vdisp_img.colorspace_settings.name = get_noncolor_name()
                color = (0.0, 0.0, 0.0, 1.0)

                if img.source == 'TILED':
                    UDIM.fill_tiles(vdisp_img, color)
                    UDIM.initial_pack_udim(vdisp_img, color)
                else: 
                    vdisp_img.generated_color = color
                    if filepath != '' and (
                            (use_udim and '.<UDIM>.' in filepath) or 
                            (not use_udim and '.<UDIM>.' not in filepath)
                        ):
                        vdisp_img.filepath = filepath

                tex.image = vdisp_img

                # Bake setup 
                create_link(mat.node_tree, node.outputs[root_ch.name + io_suffix['VDISP']], 
                        emit.inputs[0])

                # Bake
                print('BAKE CHANNEL: Baking vector displacement image of ' + root_ch.name + ' channel...')
                bake_object_op()

                # Set baked vector displacement image
                if baked_vdisp.image:
                    temp = baked_vdisp.image
                    img_users = get_all_image_users(baked_vdisp.image)
                    for user in img_users:
                        user.image = vdisp_img
                    remove_datablock(bpy.data.images, temp)
                else:
                    baked_vdisp.image = vdisp_img

            ### Max Height

            # Create target image
            if UDIM.is_udim_supported():
                mh_img = bpy.data.images.new(name='____MAXHEIGHT_TEMP', width=100, height=100, 
                        alpha=False, tiled=False, float_buffer=True)
            else:
                mh_img = bpy.data.images.new(name='____MAXHEIGHT_TEMP', width=100, height=100, 
                        alpha=False, float_buffer=True)

            mh_img.colorspace_settings.name = get_noncolor_name()
            tex.image = mh_img

            # Bake setup (doing little bit doing hacky reconnection here)
            start = tree.nodes.get(TREE_START)
            end = tree.nodes.get(TREE_END)
            ori_soc = end.inputs[root_ch.name].links[0].from_socket
            max_height = start.outputs.get(root_ch.name + io_suffix['HEIGHT'])
            # Get the last layer that output max height
            for l in yp.layers:
                if not l.enable or not l.channels[get_channel_index(root_ch)].enable: continue
                lnode = tree.nodes.get(l.group_node)
                outp = lnode.outputs.get(root_ch.name + io_suffix['MAX_HEIGHT'])
                if outp:
                    max_height = outp
                    break
            create_link(tree, max_height, end.inputs[root_ch.name])
            create_link(mat.node_tree, node.outputs[root_ch.name + io_suffix['MAX_HEIGHT']], 
                    emit.inputs[0])

            # Use high margin to make sure all pixels are covered
            ori_margin = bpy.context.scene.render.bake.margin
            bpy.context.scene.render.bake.margin = 1000

            # Bake
            print('BAKE CHANNEL: Baking max height of ' + root_ch.name + ' channel...')
            bake_object_op()

            # Recover margin
            bpy.context.scene.render.bake.margin = ori_margin

            # Recover connection
            create_link(tree, ori_soc, end.inputs[root_ch.name])

            # Set baked max height image
            max_height_value = mh_img.pixels[0]
            end_max_height = check_new_node(tree, root_ch, 'end_max_height', 'ShaderNodeValue', 'Max Height')
            end_max_height.outputs[0].default_value = max_height_value

            # Remove max height image
            remove_datablock(bpy.data.images, mh_img, user=tex, user_prop='image')

            ### Displacement

            # Create target image
            baked_disp = tree.nodes.get(root_ch.baked_disp)
            if not baked_disp:
                baked_disp = new_node(tree, root_ch, 'baked_disp', 'ShaderNodeTexImage', 
                        'Baked ' + root_ch.name + ' Displacement')
                if hasattr(baked_disp, 'color_space'):
                    baked_disp.color_space = 'NONE'

            if baked_disp.image:
                disp_img_name = baked_disp.image.name
                filepath = baked_disp.image.filepath
                #filepath = get_valid_filepath(baked_disp.image, use_hdr)
                baked_disp.image.name = '____DISP_TEMP'
            else:
                disp_img_name = tree.name + ' Displacement'

            # Set interpolation to cubic
            baked_disp.interpolation = 'Cubic'

            disp_img = img.copy()
            disp_img.name = disp_img_name
            disp_img.use_generated_float = use_float_for_displacement
            disp_img.colorspace_settings.name = get_noncolor_name()
            color = (0.5, 0.5, 0.5, 1.0)

            if img.source == 'TILED':
                UDIM.fill_tiles(disp_img, color)
                UDIM.initial_pack_udim(disp_img, color)
            else: 
                disp_img.generated_color = color
                if filepath != '' and (
                        (use_udim and '.<UDIM>.' in filepath) or 
                        (not use_udim and '.<UDIM>.' not in filepath)
                    ):
                    disp_img.filepath = filepath

        elif ch.normal_map_type == 'BUMP_MAP':
            disp_img = img
        else: disp_img = None

        if disp_img:

            # Bake setup
            # Spread height only created if layer has no parent
            if target_layer and target_layer.parent_idx == -1:
                spread_height = mat.node_tree.nodes.new('ShaderNodeGroup')
                spread_height.node_tree = get_node_tree_lib(lib.SPREAD_NORMALIZED_HEIGHT)

                create_link(mat.node_tree, node.outputs[root_ch.name + io_suffix['HEIGHT']], 
                        spread_height.inputs[0])
                create_link(mat.node_tree, node.outputs[root_ch.name + io_suffix['ALPHA']], 
                        spread_height.inputs[1])
                create_link(mat.node_tree, spread_height.outputs[0], emit.inputs[0])

                #create_link(mat.node_tree, node.outputs[root_ch.name + io_suffix['HEIGHT']], srgb2lin.inputs[0])
                #create_link(mat.node_tree, srgb2lin.outputs[0], emit.inputs[0])
            else:
                spread_height = None
                create_link(mat.node_tree, node.outputs[root_ch.name + io_suffix['HEIGHT']], emit.inputs[0])
            tex.image = disp_img

            #return

            # Bake
            print('BAKE CHANNEL: Baking displacement image of ' + root_ch.name + ' channel...')
            bake_object_op()

            if not target_layer:

                # Set baked displacement image
                if baked_disp.image:
                    temp = baked_disp.image
                    img_users = get_all_image_users(baked_disp.image)
                    for user in img_users:
                        user.image = disp_img
                    remove_datablock(bpy.data.images, temp)
                else:
                    baked_disp.image = disp_img

            if spread_height:
                simple_remove_node(mat.node_tree, spread_height)

        # Recover input outputs
        check_all_channel_ios(yp)

    # Bake alpha
    #if root_ch.type != 'NORMAL' and root_ch.enable_alpha:
    if root_ch.enable_alpha:

        # Create temp image
        alpha_img = img.copy()
        alpha_img.colorspace_settings.name = get_noncolor_name()
        create_link(mat.node_tree, node.outputs[root_ch.name + io_suffix['ALPHA']], emit.inputs[0])
        tex.image = alpha_img

        # Set temp filepath
        if img.source == 'TILED':
            alpha_img.name = '__TEMP__'
            UDIM.initial_pack_udim(alpha_img)

        # Bake
        print('BAKE CHANNEL: Baking alpha of ' + root_ch.name + ' channel...')
        bake_object_op()

        # Set tile pixels
        for tilenum in tilenums:

            # Swap tile
            if tilenum != 1001:
                UDIM.swap_tile(img, 1001, tilenum)
                UDIM.swap_tile(alpha_img, 1001, tilenum)

            # Copy alpha
            copy_image_channel_pixels(alpha_img, img, 0, 3)

            # Swap tile again to recover
            if tilenum != 1001:
                UDIM.swap_tile(img, 1001, tilenum)
                UDIM.swap_tile(alpha_img, 1001, tilenum)

        # Remove temp image
        remove_datablock(bpy.data.images, alpha_img, user=tex, user_prop='image')

    if not target_layer:
        # Set image to baked node and replace all previously original users
        if baked.image:
            temp = baked.image
            img_users = get_all_image_users(baked.image)
            for user in img_users:
                user.image = img
            remove_datablock(bpy.data.images, temp)
        else:
            baked.image = img

    simple_remove_node(mat.node_tree, tex, remove_data = tex.image != img)
    simple_remove_node(mat.node_tree, emit)
    #simple_remove_node(mat.node_tree, lin2srgb)
    #simple_remove_node(mat.node_tree, srgb2lin)
    if root_ch.type == 'NORMAL':
        simple_remove_node(mat.node_tree, norm)

    # Recover original bsdf
    mat.node_tree.links.new(ori_bsdf, output.inputs[0])

    # Recover baked temp
    for ent in temp_baked:
        print('BAKE CHANNEL: Removing temporary baked ' + ent.name + '...')
        disable_temp_bake(ent)

    # Set image to target layer
    if target_layer:
        ori_img = source.image

        if segment:
            if ori_img.yia.is_image_atlas:
                copy_image_pixels(img, ori_img, segment)
            else:
                UDIM.copy_tiles(img, ori_img, copy_dict)

            # Remove temp image
            remove_datablock(bpy.data.images, img)
        else:
            source.image = img
            safe_remove_image(ori_img)

        return True

def temp_bake(context, entity, width, height, hdr, samples, margin, uv_map, bake_device='CPU', margin_type='ADJACENT_FACES'):

    m1 = re.match(r'yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if not m1 and not m2: return

    yp = entity.id_data.yp
    obj = context.object
    #scene = context.scene

    # Prepare bake settings
    book = remember_before_bake(yp)
    prepare_bake_settings(book, [obj], yp, samples, margin, uv_map, bake_device=bake_device, margin_type=margin_type)

    mat = get_active_material()
    name = entity.name + ' Temp'

    # New target image
    image = bpy.data.images.new(name=name,
            width=width, height=height, alpha=True, float_buffer=hdr)
    image.colorspace_settings.name = get_noncolor_name()

    if entity.type == 'HEMI':

        if m1: source = get_layer_source(entity)
        else: source = get_mask_source(entity)

        # Create bake nodes
        source_copy = mat.node_tree.nodes.new(source.bl_idname)
        source_copy.node_tree = source.node_tree

        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        emit = mat.node_tree.nodes.new('ShaderNodeEmission')
        geo = mat.node_tree.nodes.new('ShaderNodeNewGeometry')
        output = get_active_mat_output_node(mat.node_tree)
        ori_bsdf = output.inputs[0].links[0].from_socket

        # Connect emit to output material
        mat.node_tree.links.new(emit.outputs[0], output.inputs[0])
        mat.node_tree.links.new(source_copy.outputs[0], output.inputs[0])
        mat.node_tree.links.new(geo.outputs['Normal'], source_copy.inputs['Normal'])

        # Set active texture
        tex.image = image
        mat.node_tree.nodes.active = tex

        # Bake
        bake_object_op()

        # Recover link
        mat.node_tree.links.new(ori_bsdf, output.inputs[0])

        # Remove temp nodes
        mat.node_tree.nodes.remove(tex)
        simple_remove_node(mat.node_tree, emit)
        simple_remove_node(mat.node_tree, source_copy)
        simple_remove_node(mat.node_tree, geo)

        # Set entity original type
        entity.original_type = 'HEMI'

    # Set entity flag
    entity.use_temp_bake = True

    # Recover bake settings
    recover_bake_settings(book, yp)

    # Set uv
    entity.uv_name = uv_map

    # Replace layer with temp image
    if m1: 
        Layer.replace_layer_type(entity, 'IMAGE', image.name, remove_data=True)
    else: Layer.replace_mask_type(entity, 'IMAGE', image.name, remove_data=True)

    return image

def disable_temp_bake(entity):
    if not entity.use_temp_bake: return

    m1 = re.match(r'yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    # Replace layer type
    if m1: Layer.replace_layer_type(entity, entity.original_type, remove_data=True)
    else: Layer.replace_mask_type(entity, entity.original_type, remove_data=True)

    # Set entity attribute
    entity.use_temp_bake = False

def get_duplicated_mesh_objects(scene, objs, hide_original=False):
    tt = time.time()
    print('INFO: Duplicating mesh(es) for baking...')

    new_objs = []

    for obj in objs:
        if obj.type != 'MESH': continue
        new_obj = obj.copy()
        link_object(scene, new_obj)
        new_objs.append(new_obj)
        new_obj.data = new_obj.data.copy()

        # Hide render of original object
        if hide_original:
            obj.hide_render = True

    print('INFO: Duplicating mesh(es) is done at', '{:0.2f}'.format(time.time() - tt), 'seconds!')
    return new_objs

def get_merged_mesh_objects(scene, objs, hide_original=False):

    # Duplicate objects
    new_objs = get_duplicated_mesh_objects(scene, objs, hide_original)
    new_meshes = [obj.data for obj in new_objs]

    tt = time.time()
    print('INFO: Merging mesh(es) for baking...')

    # Check if any objects use geometry nodes to output uv
    any_uv_geonodes = False
    for obj in new_objs:
        if any(get_output_uv_names_from_geometry_nodes(obj)):
            any_uv_geonodes = True

    # Select objects
    try: bpy.ops.object.mode_set(mode = 'OBJECT')
    except: pass
    bpy.ops.object.select_all(action='DESELECT')

    max_levels = -1
    hi_obj = None
    for obj in new_objs:
        set_active_object(obj)
        set_object_select(obj, True)

        # Apply shape keys
        if obj.data.shape_keys:
            # Set active shape to make sure context will be correct
            if not obj.active_shape_key: obj.active_shape_key_index = 0
            if is_bl_newer_than(3, 3):
                bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
            else: bpy.ops.object.shape_key_remove(all=True)

        # Apply modifiers
        mnames = [m.name for m in obj.modifiers]
        problematic_modifiers = get_problematic_modifiers(obj)

        # Get all uv output from geometry nodes
        geo_uv_names = get_output_uv_names_from_geometry_nodes(obj)

        for mname in mnames:

            m = obj.modifiers[mname]

            if m not in problematic_modifiers:
                if m.type == 'SUBSURF':
                    if m.render_levels > m.levels:
                        m.levels = m.render_levels
                elif m.type == 'MULTIRES':
                    if m.total_levels > m.levels:
                        m.levels = m.total_levels

                # Only apply modifier with show viewport on
                if m.show_viewport:
                    try:
                        bpy.ops.object.modifier_apply(modifier=m.name)
                        continue
                    except Exception as e: print(e)

            bpy.ops.object.modifier_remove(modifier=m.name)

        # HACK: Convert all geo uvs attribute to 2D vector 
        # This is needed since it always produce 3D vector on Blender 3.5
        # 3D vector can't produce correct tangent so smooth bump can't be baked
        for guv in geo_uv_names:
            for i, attr in enumerate(obj.data.attributes):
                if attr and attr.name == guv:
                    obj.data.attributes.active_index = i
                    bpy.ops.geometry.attribute_convert(domain='CORNER', data_type='FLOAT2')

    # Set first index as merged object
    merged_obj = new_objs[0]

    # Set active object
    set_active_object(merged_obj)
    if merged_obj.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')

    # Join
    bpy.ops.object.join()

    # Remove temp meshes
    for nm in new_meshes:
        if nm != merged_obj.data:
            remove_datablock(bpy.data.meshes, nm)

    print('INFO: Merging mesh(es) is done at', '{:0.2f}'.format(time.time() - tt), 'seconds!')
    return merged_obj

def resize_image(image, width, height, colorspace='Non-Color', samples=1, margin=0, segment=None, alpha_aware=True, yp=None, bake_device='CPU', specific_tile=0):

    T = time.time()
    image_name = image.name
    print('RESIZE IMAGE: Doing resize image pass on', image_name + '...')

    if image.source != 'TILED':
        if segment:
            ori_width = segment.width
            ori_height = segment.height
        else:
            ori_width = image.size[0]
            ori_height = image.size[1]

        if ori_width == width and ori_height == height:
            return

    book = remember_before_bake()

    if image.source == 'TILED':
        if specific_tile < 1001:
            tilenums = [tile.number for tile in image.tiles]
        else: tilenums = [specific_tile]
    else: tilenums = [1001]

    # Set active collection to be root collection
    if is_bl_newer_than(2, 80):
        ori_layer_collection = bpy.context.view_layer.active_layer_collection
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection

    # Create new plane
    bpy.ops.object.mode_set(mode = 'OBJECT')
    plane_obj = create_plane_on_object_mode()

    prepare_bake_settings(book, [plane_obj], samples=samples, margin=margin, bake_device=bake_device)

    mat = bpy.data.materials.new('__TEMP__')
    mat.use_nodes = True
    plane_obj.active_material = mat

    output = get_active_mat_output_node(mat.node_tree)
    emi = mat.node_tree.nodes.new('ShaderNodeEmission')
    uv_map = mat.node_tree.nodes.new('ShaderNodeUVMap')
    #uv_map.uv_map = 'UVMap' # Will use active UV instead since every language has different default UV name
    target_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    source_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    source_tex.image = image

    if not is_bl_newer_than(2, 80) :
        if image.colorspace_settings.name == get_srgb_name():
            source_tex.color_space = 'COLOR'
        else: source_tex.color_space = 'NONE'

    straight_over = mat.node_tree.nodes.new('ShaderNodeGroup')
    straight_over.node_tree = get_node_tree_lib(lib.STRAIGHT_OVER)
    straight_over.inputs[1].default_value = 0.0

    # Connect nodes
    mat.node_tree.links.new(uv_map.outputs[0], source_tex.inputs[0])
    mat.node_tree.links.new(emi.outputs[0], output.inputs[0])
    mat.node_tree.nodes.active = target_tex

    new_segment = None

    for tilenum in tilenums:

        # Swap tile to 1001 to access the data
        if tilenum != 1001:
            UDIM.swap_tile(image, 1001, tilenum)

        if segment:
            new_segment = ImageAtlas.get_set_image_atlas_segment(
                        width, height, image.yia.color, image.is_float, yp=yp) #, ypup.image_atlas_size)
            scaled_img = new_segment.id_data

            ori_start_x = segment.width * segment.tile_x
            ori_start_y = segment.height * segment.tile_y

            start_x = width * new_segment.tile_x
            start_y = height * new_segment.tile_y

            # If using image atlas, transform uv
            uv_layers = get_uv_layers(plane_obj)

            # Transform current uv using previous segment
            for i, d in enumerate(plane_obj.data.uv_layers.active.data):
                if i == 0: # Top right
                    d.uv.x = (ori_start_x + segment.width) / image.size[0]
                    d.uv.y = (ori_start_y + segment.height) / image.size[1]
                elif i == 1: # Top left
                    d.uv.x = ori_start_x / image.size[0]
                    d.uv.y = (ori_start_y + segment.height) / image.size[1]
                elif i == 2: # Bottom left
                    d.uv.x = ori_start_x / image.size[0]
                    d.uv.y = ori_start_y / image.size[1]
                elif i == 3: # Bottom right
                    d.uv.x = (ori_start_x + segment.width) / image.size[0]
                    d.uv.y = ori_start_y / image.size[1]

            # Create new uv and transform it using new segment
            temp_uv_layer = uv_layers.new(name='__TEMP')
            uv_layers.active = temp_uv_layer
            for i, d in enumerate(plane_obj.data.uv_layers.active.data):
                if i == 0: # Top right
                    d.uv.x = (start_x + width) / scaled_img.size[0]
                    d.uv.y = (start_y + height) / scaled_img.size[1]
                elif i == 1: # Top left
                    d.uv.x = start_x / scaled_img.size[0]
                    d.uv.y = (start_y + height) / scaled_img.size[1]
                elif i == 2: # Bottom left
                    d.uv.x = start_x / scaled_img.size[0]
                    d.uv.y = start_y / scaled_img.size[1]
                elif i == 3: # Bottom right
                    d.uv.x = (start_x + width) / scaled_img.size[0]
                    d.uv.y = start_y / scaled_img.size[1]

        else:
            scaled_img = bpy.data.images.new(name='__TEMP__', 
                width=width, height=height, alpha=True, float_buffer=image.is_float)
            scaled_img.colorspace_settings.name = colorspace
            if image.filepath != '' and not image.packed_file:
                scaled_img.filepath = image.filepath

        # Reconnect bake setup nodes
        mat.node_tree.links.new(source_tex.outputs[0], straight_over.inputs[2])
        mat.node_tree.links.new(source_tex.outputs[1], straight_over.inputs[3])
        mat.node_tree.links.new(straight_over.outputs[0], emi.inputs[0])

        # Set image target
        target_tex.image = scaled_img

        # Bake
        print('RESIZE IMAGE: Baking resized image on', image_name + '...')
        bake_object_op()

        if alpha_aware:

            # Create alpha image as bake target
            alpha_img = bpy.data.images.new(name='__TEMP_ALPHA__',
                    width=width, height=height, alpha=True, float_buffer=image.is_float)
            alpha_img.colorspace_settings.name = get_noncolor_name()

            # Retransform back uv
            if segment:
                for i, d in enumerate(plane_obj.data.uv_layers.active.data):
                    if i == 0: # Top right
                        d.uv.x = 1.0
                        d.uv.y = 1.0
                    elif i == 1: # Top left
                        d.uv.x = 0.0
                        d.uv.y = 1.0
                    elif i == 2: # Bottom left
                        d.uv.x = 0.0
                        d.uv.y = 0.0
                    elif i == 3: # Bottom right
                        d.uv.x = 1.0
                        d.uv.y = 0.0

            # Setup texture
            target_tex.image = alpha_img
            mat.node_tree.links.new(source_tex.outputs[1], emi.inputs[0])

            # Bake again!
            print('RESIZE IMAGE: Baking resized alpha on', image_name + '...')
            bake_object_op()

            if new_segment:
                copy_image_channel_pixels(alpha_img, scaled_img, 0, 3, new_segment)
            else: copy_image_channel_pixels(alpha_img, scaled_img, 0, 3, segment)

            # Remove alpha image
            remove_datablock(bpy.data.images, alpha_img)

        if image.source == 'TILED':
            # Resize tile first
            UDIM.fill_tile(image, 1001, image.generated_color, width, height)

            # Copy resized image to tile
            copy_image_pixels(scaled_img, image)

            remove_datablock(bpy.data.images, scaled_img)
        else:
            if not new_segment:
                # Replace original image to scaled image
                replace_image(image, scaled_img)
            image = scaled_img

        # Swap back the tile
        if tilenum != 1001:
            UDIM.swap_tile(image, 1001, tilenum)

    # Remove temp datas
    if straight_over.node_tree.users == 1:
        remove_datablock(bpy.data.node_groups, straight_over.node_tree, user=straight_over, user_prop='node_tree')
    remove_datablock(bpy.data.materials, mat)
    plane = plane_obj.data
    bpy.ops.object.delete()
    remove_datablock(bpy.data.meshes, plane)

    # Recover settings
    recover_bake_settings(book)

    # Recover original active layer collection
    if is_bl_newer_than(2, 80):
        bpy.context.view_layer.active_layer_collection = ori_layer_collection

    print('RESIZE IMAGE:', image_name, 'Resize image is done at', '{:0.2f}'.format(time.time() - T), 'seconds!')

    return image, new_segment

def get_temp_default_material():
    mat = bpy.data.materials.get(TEMP_MATERIAL)

    if not mat: 
        mat = bpy.data.materials.new(TEMP_MATERIAL)
        mat.use_nodes = True

    return mat

def remove_temp_default_material():
    mat = bpy.data.materials.get(TEMP_MATERIAL)
    if mat: 
        remove_datablock(bpy.data.materials, mat)

def get_temp_emit_white_mat():
    mat = bpy.data.materials.get(TEMP_EMIT_WHITE)

    if not mat: 
        mat = bpy.data.materials.new(TEMP_EMIT_WHITE)
        mat.use_nodes = True

        # Create nodes
        output = get_active_mat_output_node(mat.node_tree)
        emi = mat.node_tree.nodes.new('ShaderNodeEmission')
        mat.node_tree.links.new(emi.outputs[0], output.inputs[0])

    return mat

def remove_temp_emit_white_mat():
    mat = bpy.data.materials.get(TEMP_EMIT_WHITE)
    if mat: 
        remove_datablock(bpy.data.materials, mat)

def get_output_uv_names_from_geometry_nodes(obj):
    if not is_greater_than_350: return []

    uv_layers = get_uv_layers(obj)
    uv_names = []
    
    for m in obj.modifiers:
        if m.type == 'NODES' and m.node_group:
            outputs = get_tree_outputs(m.node_group)
            for outp in outputs:
                if ((is_bl_newer_than(4) and outp.socket_type == 'NodeSocketVector') or
                    (not is_bl_newer_than(4) and outp.type == 'VECTOR')):
                    uv = uv_layers.get(m[outp.identifier + '_attribute_name'])
                    if uv: uv_names.append(uv.name)

    return uv_names

class BaseBakeOperator():
    bake_device : EnumProperty(
            name='Bake Device',
            description='Device to use for baking',
            items = (('GPU', 'GPU Compute', ''),
                     ('CPU', 'CPU', '')),
            default='CPU'
            )
    
    samples : IntProperty(name='Bake Samples', 
            description='Bake Samples, more means less jagged on generated textures', 
            default=1, min=1)

    margin : IntProperty(name='Bake Margin',
            description = 'Bake margin in pixels',
            default=5, subtype='PIXEL')

    margin_type : EnumProperty(name = 'Margin Type',
            description = '',
            items = (('ADJACENT_FACES', 'Adjacent Faces', 'Use pixels from adjacent faces across UV seams.'),
                     ('EXTEND', 'Extend', 'Extend border pixels outwards')),
            default = 'ADJACENT_FACES')

    width : IntProperty(name='Width', default = 1234, min=1, max=16384)
    height : IntProperty(name='Height', default = 1234, min=1, max=16384)

    def invoke_operator(self, context):
        ypup = get_user_preferences()

        # Set up default bake device
        if ypup.default_bake_device != 'DEFAULT':
            self.bake_device = ypup.default_bake_device

        # Use user preference default image size if input uses default image size
        if self.width == 1234 and self.height == 1234:
            self.width = self.height = ypup.default_new_image_size

