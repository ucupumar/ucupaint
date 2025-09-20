import bpy, time, os, numpy, tempfile, bmesh
from bpy.props import *
from .common import *
from .input_outputs import *
from .node_connections import *
from . import lib, Layer, ImageAtlas, UDIM, image_ops, Mask

BL28_HACK = True

TEMP_VCOL = '__temp__vcol__'
TEMP_EMISSION = '_TEMP_EMI_'

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

blur_type_labels = {
    'NOISE' : 'Noise',
    'FLAT' : 'Flat',
    'TENT' : 'Tent',
    'QUAD' : 'Quadratic',
    'CUBIC' : 'Cubic',
    'GAUSS' : 'Gaussian',
    'FAST_GAUSS' : 'Fast Gaussian',
    'CATROM' : 'Catrom',
    'MITCH' : 'Mitch',
}

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

def get_compositor_node_tree(scene):
    if not is_bl_newer_than(5):
        return scene.node_tree
    
    return scene.compositing_node_group

def get_compositor_output_node(tree):
    node_type = 'GROUP_OUTPUT' if is_bl_newer_than(5) else 'COMPOSITE'
    for n in tree.nodes:
        if n.type == node_type:
            return n

    # Create new compositor output if there's none
    if is_bl_newer_than(5):
        n = tree.nodes.new('NodeGroupOutput')
        if 'Image' not in n.inputs:
            new_tree_output(tree, 'Image', 'NodeSocketColor')
    else: n = tree.nodes.new('CompositorNodeComposite')

    return n

def get_scene_bake_multires(scene):
    return scene.render.bake.use_multires if is_bl_newer_than(5) else scene.render.use_bake_multires

def get_scene_bake_clear(scene):
    return scene.render.bake.use_clear if is_bl_newer_than(5) else scene.render.use_bake_clear

def get_scene_render_bake_type(scene):
    return scene.render.bake.type if is_bl_newer_than(5) else scene.render.bake_type

def get_scene_bake_margin(scene):
    return scene.render.bake.margin if is_bl_newer_than(5) else scene.render.bake_margin

def set_scene_bake_multires(scene, value):
    if not is_bl_newer_than(5):
        scene.render.use_bake_multires = value
    else: scene.render.bake.use_multires = value

def set_scene_bake_clear(scene, value):
    if not is_bl_newer_than(5):
        scene.render.use_bake_clear = value
    else: scene.render.bake.use_clear = value

def set_scene_render_bake_type(scene, value):
    if not is_bl_newer_than(5):
        scene.render.bake_type = value
    else: scene.render.bake.type = value

def set_scene_bake_margin(scene, value):
    if not is_bl_newer_than(5):
        scene.render.bake_margin = value
    else: scene.render.bake.margin = value

def is_there_any_missmatched_attribute_types(objs):
    # Get number of attributes founds
    attr_counts = {}
    for obj in objs:
        for attr in obj.data.attributes:
            if attr.name not in attr_counts:
                attr_counts[attr.name] = 1
            else:
                attr_counts[attr.name] += 1
    
    # Get the same attribute used in all objects
    same_attrs = []
    for name, count in attr_counts.items():
        if count == len(objs):
            same_attrs.append(name)
            
    # Is there any missmatched type data
    for name in same_attrs:
        data_type = ''
        domain = ''
        for obj in objs:
            attr = obj.data.attributes[name]
            
            if data_type == '':
                data_type = attr.data_type
            elif data_type != attr.data_type:
                return True
            
            if domain == '':
                domain = attr.domain
            elif domain != attr.domain:
                return True

    return False

def is_join_objects_problematic(yp, mat=None):
    for layer in yp.layers:
        if not layer.enable: continue

        for mask in layer.masks:
            if not mask.enable: continue
            if mask.type in {'VCOL', 'HEMI', 'COLOR_ID'}: 
                continue
            if mask.texcoord_type in JOIN_PROBLEMATIC_TEXCOORDS or mask.type in {'OBJECT_INDEX'}:
                print('INFO: Merged bake is not happening because there\'s object index mask')
                return True

        if layer.type in {'VCOL', 'COLOR', 'BACKGROUND', 'HEMI', 'GROUP'}: 
            continue
        if layer.texcoord_type in JOIN_PROBLEMATIC_TEXCOORDS:
            print('INFO: Merged bake is not happening because there\'s problematic texcoord used')
            return True

    if mat:
        output = get_material_output(mat)
        if output: 
            if search_join_problematic_texcoord(mat.node_tree, output):
                print('INFO: Merged bake is not happening because there\'s problematic texcoord used outside node')
                return True

        # Check for missmatched color attribute data
        if is_bl_newer_than(3, 2):
            objs = get_all_objects_with_same_materials(mat, True)
            if is_there_any_missmatched_attribute_types(objs):
                print('INFO: Merged bake is not happening because there\'s missmatched attribute data types')
                return True

    return False

def get_pointiness_image_minmax_value(image):
    
    if is_bl_newer_than(2, 83):
        pxs = numpy.empty(shape=image.size[0] * image.size[1] * 4, dtype=numpy.float32)
        image.pixels.foreach_get(pxs)

        pxs.shape = (-1, image.size[0], 4)

        # Set alpha to half
        pxs *= (1, 1, 1, 0.5)

        min_val = pxs.min()
        max_val = pxs.max()

        return min_val, max_val
    else:
        # TODO: Get minimum and maximum pixel on legacy blenders
        return 0.4, 0.6

def bake_object_op(bake_type='EMIT'):
    try:
        if bake_type != 'EMIT':
            bpy.ops.object.bake(type=bake_type)
        else: bpy.ops.object.bake()
    except Exception as e:
        scene = bpy.context.scene
        if scene.cycles.device == 'GPU':
            print('EXCEPTIION: GPU baking failed! Trying to use CPU...')
            scene.cycles.device = 'CPU'

            if bake_type != 'EMIT':
                bpy.ops.object.bake(type=bake_type)
            else: bpy.ops.object.bake()
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
    book['ori_use_osl'] = scene.cycles.shading_system
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
    book['ori_use_bake_multires'] = get_scene_bake_multires(scene)
    book['ori_use_bake_clear'] = get_scene_bake_clear(scene)
    book['ori_render_bake_type'] = get_scene_render_bake_type(scene)
    book['ori_bake_margin'] = get_scene_bake_margin(scene)

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

def prepare_other_objs_colors(yp, other_objs):

    other_mats = []
    other_sockets = []
    other_defaults = []
    other_alpha_sockets = []
    other_alpha_defaults = []

    ori_mat_no_nodes = []

    valid_bsdf_types = ['BSDF_PRINCIPLED', 'BSDF_DIFFUSE', 'EMISSION']

    for o in other_objs:
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
            if mat in other_mats: continue
            if not mat.use_nodes: continue

            # Get material output
            output = get_material_output(mat)
            if not output: continue

            socket = None
            default = None
            alpha_socket = None
            alpha_default = 1.0

            if mat in ori_mat_no_nodes and hasattr(mat, 'diffuse_color'):
                default = mat.diffuse_color

            # Check for possible sockets available on the bsdf node
            if not socket:
                # Search for main bsdf
                bsdf_node = get_closest_bsdf_backward(output, valid_bsdf_types)

                if bsdf_node.type == 'BSDF_PRINCIPLED':
                    socket = bsdf_node.inputs['Base Color']

                elif 'Color' in bsdf_node.inputs:
                    socket = bsdf_node.inputs['Color']

                if socket:
                    if len(socket.links) == 0:
                        if default == None:
                            default = socket.default_value
                    else:
                        socket = socket.links[0].from_socket

                # Get alpha socket
                alpha_socket = bsdf_node.inputs.get('Alpha')
                if alpha_socket:

                    if len(alpha_socket.links) == 0:
                        alpha_default = alpha_socket.default_value
                        alpha_socket = None
                    else:
                        alpha_socket = alpha_socket.links[0].from_socket

            # Append objects and materials if socket is found
            if socket or default:
                other_mats.append(mat)
                other_sockets.append(socket)
                other_defaults.append(default)
                other_alpha_sockets.append(alpha_socket)
                other_alpha_defaults.append(alpha_default)

    return other_mats, other_sockets, other_defaults, other_alpha_sockets, other_alpha_defaults, ori_mat_no_nodes

def prepare_other_objs_channels(yp, other_objs):
    ch_other_objects = []
    ch_other_mats = []
    ch_other_sockets = []
    ch_other_defaults = []
    ch_other_default_weights = []
    ch_other_alpha_sockets = []
    ch_other_alpha_defaults = []

    ori_mat_no_nodes = []

    valid_bsdf_types = ['BSDF_PRINCIPLED', 'BSDF_DIFFUSE', 'EMISSION']

    for ch in yp.channels:
        objs = []
        mats = []
        sockets = []
        defaults = []
        default_weights = []
        alpha_sockets = []
        alpha_defaults = []

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
                #if mat in mats: continue
                if not mat.use_nodes: continue

                # Get material output
                output = get_material_output(mat)
                if not output: continue

                socket = None
                default = None
                default_weight = 1.0
                alpha_socket = None
                alpha_default = 1.0

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

                    # Check for alpha channel
                    for och in oyp.channels:
                        if och.enable_alpha: # and och.name == ch.name:
                            alpha_socket = yp_node.outputs.get(och.name + io_suffix['ALPHA'])

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

                                # Blender 4.0 has weight/strength value for some inputs
                                if is_bl_newer_than(4):
                                    input_prefixes = ['Subsurface', 'Coat', 'Sheen', 'Emission']
                                    for prefix in input_prefixes:
                                        if socket.name.startswith(prefix):

                                            if socket.name.startswith('Emission'):
                                                weight_socket_name = 'Emission Strength'
                                            else: weight_socket_name = prefix + ' Weight'

                                            # NOTE: Only set the default weight if there's no dedicated channel for weight in destination yp
                                            if weight_socket_name not in yp.channels and weight_socket_name != socket.name:
                                                weight_socket = bsdf_node.inputs.get(weight_socket_name)
                                                if weight_socket:
                                                    default_weight = weight_socket.default_value
                        else:
                            socket = socket.links[0].from_socket

                    # Get alpha socket
                    alpha_socket = bsdf_node.inputs.get('Alpha')
                    if alpha_socket:

                        if len(alpha_socket.links) == 0:
                            alpha_default = alpha_socket.default_value
                            alpha_socket = None
                        else:
                            alpha_socket = alpha_socket.links[0].from_socket

                # Append objects and materials if socket is found
                if socket or default:
                    mats.append(mat)
                    sockets.append(socket)
                    defaults.append(default)
                    default_weights.append(default_weight)
                    alpha_sockets.append(alpha_socket)
                    alpha_defaults.append(alpha_default)

                    if o not in objs:
                        objs.append(o)

        ch_other_objects.append(objs)
        ch_other_mats.append(mats)
        ch_other_sockets.append(sockets)
        ch_other_defaults.append(defaults)
        ch_other_default_weights.append(default_weights)
        ch_other_alpha_sockets.append(alpha_sockets)
        ch_other_alpha_defaults.append(alpha_defaults)

    return ch_other_objects, ch_other_mats, ch_other_sockets, ch_other_defaults, ch_other_default_weights, ch_other_alpha_sockets, ch_other_alpha_defaults, ori_mat_no_nodes

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

def prepare_bake_settings(
        book, objs, yp=None, samples=1, margin=5, uv_map='', bake_type='EMIT', 
        disable_problematic_modifiers=False, hide_other_objs=True, bake_from_multires=False, 
        tile_x=64, tile_y=64, use_selected_to_active=False, max_ray_distance=0.0, cage_extrusion=0.0,
        bake_target = 'IMAGE_TEXTURES',
        source_objs=[], bake_device='CPU', use_denoising=False, margin_type='ADJACENT_FACES', 
        use_cage=False, cage_object_name='', 
        normal_space='TANGENT', use_osl=False,
    ):

    scene = bpy.context.scene
    ypui = bpy.context.window_manager.ypui
    wmyp = bpy.context.window_manager.ypprops

    # Hack function on depsgraph update can cause crash, so halt it before baking
    wmyp.halt_hacks = True

    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.shading_system = use_osl
    scene.render.threads_mode = 'AUTO'
    scene.render.bake.margin = margin
    #scene.render.bake.use_clear = True
    scene.render.bake.use_clear = False
    scene.render.bake.use_selected_to_active = use_selected_to_active
    if hasattr(scene.render.bake, 'max_ray_distance'):
        scene.render.bake.max_ray_distance = max_ray_distance
    scene.render.bake.cage_extrusion = cage_extrusion
    cage_object = bpy.data.objects.get(cage_object_name) if cage_object_name != '' else None
    #scene.render.bake.use_cage = True if cage_object else False
    scene.render.bake.use_cage = use_cage
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
        set_scene_bake_multires(scene, True)
        set_scene_render_bake_type(scene, bake_type)
        set_scene_bake_margin(scene, margin)
        set_scene_bake_clear(scene, False)
    else: 
        set_scene_bake_multires(scene, False)
        scene.cycles.bake_type = bake_type

    # Old blender will always use CPU
    if not is_bl_newer_than(2, 80) or use_osl:
        scene.cycles.device = 'CPU'
    else: scene.cycles.device = bake_device

    # Use CUDA bake if Optix is selected
    if (is_bl_newer_than(2, 81) and not is_bl_newer_than(3) and 'compute_device_type' in bpy.context.preferences.addons['cycles'].preferences and
            bpy.context.preferences.addons['cycles'].preferences['compute_device_type'] == 3):
        #scene.cycles.device = 'CPU'
        bpy.context.preferences.addons['cycles'].preferences['compute_device_type'] = 1

    if bake_type == 'NORMAL':
        scene.render.bake.normal_space = normal_space

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

            # Blender 2.76 needs all objects to be UV unwrapped
            if not is_bl_newer_than(2, 77):
                ori_active_object = scene.objects.active
                uv_layers = get_uv_layers(obj)
                if len(uv_layers) == 0:
                    scene.objects.active = obj
                    bpy.ops.wm.y_add_simple_uvs()
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
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        try: bpy.ops.object.mode_set(mode = 'OBJECT')
        except: pass

    # Disable parallax channel
    if book['parallax_ch']:
        book['parallax_ch'].enable_parallax = False

    # Remember object materials related to baking
    book['ori_mat_objs'] = []
    book['ori_mat_objs_active_nodes'] = []

    for o in objs:
        mat = o.active_material
        if not mat: continue

        # Remember other material active nodes
        active_node_names = []
        for m in o.data.materials:
            if m and m.use_nodes and m.node_tree.nodes.active:
                active_node_names.append(m.node_tree.nodes.active.name)
                continue
            active_node_names.append('')

        book['ori_mat_objs'].append(o.name)
        book['ori_mat_objs_active_nodes'].append(active_node_names)

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
    wmyp = bpy.context.window_manager.ypprops

    scene.render.engine = book['ori_engine']
    scene.cycles.samples = book['ori_samples']
    scene.cycles.shading_system = book['ori_use_osl']
    scene.cycles.bake_type = book['ori_bake_type']
    scene.render.threads_mode = book['ori_threads_mode']
    scene.render.bake.margin = book['ori_margin']
    scene.render.bake.use_clear = book['ori_use_clear']
    scene.render.bake.normal_space = book['ori_normal_space']
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
    set_scene_bake_multires(scene, book['ori_use_bake_multires'])
    set_scene_bake_clear(scene, book['ori_use_bake_clear'])
    set_scene_render_bake_type(scene, book['ori_render_bake_type'])
    set_scene_bake_margin(scene, book['ori_bake_margin'])

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

    # Bring back the hack functions
    wmyp.halt_hacks = False

def prepare_composite_settings(res_x=1024, res_y=1024, use_hdr=False):
    book = {}

    # Remember original scene
    book['ori_scene_name'] = bpy.context.scene.name

    # Remember active object and view layer
    book['ori_viewlayer'] = bpy.context.window.view_layer.name if is_bl_newer_than(2, 80) and bpy.context.window.view_layer else ''
    book['ori_object'] = bpy.context.object.name if bpy.context.object else ''

    # Check if original viewport is using camera view
    area = bpy.context.area
    book['ori_camera_view'] = area.type == 'VIEW_3D' and area.spaces[0].region_3d.view_perspective == 'CAMERA'

    # Create new temporary scene
    scene = bpy.data.scenes.new(name='TEMP_COMPOSITE_SCENE')
    if is_bl_newer_than(2, 80):
        bpy.context.window.scene = scene
    else: bpy.context.screen.scene = scene

    # Set up render settings
    scene.cycles.samples = 1
    if hasattr(scene, 'eevee'):
        scene.eevee.taa_render_samples = 1
    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    scene.render.pixel_aspect_x = 1.0
    scene.render.pixel_aspect_y = 1.0
    if is_bl_newer_than(5):
        comp_tree = bpy.data.node_groups.new('TEMP_COMPOSITOR_TREE__', 'CompositorNodeTree')
        scene.compositing_node_group = comp_tree
    else:
        scene.use_nodes = True
    scene.view_settings.view_transform = 'Standard' if is_bl_newer_than(2, 80) else 'Default'
    scene.render.dither_intensity = 0.0

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

    # Remove compositor node tree
    if is_bl_newer_than(5):
        comp_tree = get_compositor_node_tree(scene)
        remove_datablock(bpy.data.node_groups, comp_tree)

    # Remove temp scene
    remove_datablock(bpy.data.scenes, scene)

    # Go back to original scene
    scene = bpy.data.scenes.get(book['ori_scene_name'])
    if is_bl_newer_than(2, 80):
        bpy.context.window.scene = scene
    else: bpy.context.screen.scene = scene

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

def blur_image(image, filter_type='GAUSS', size=10):
    T = time.time()
    print('BLUR: Doing Blur pass on', image.name + '...')

    # Preparing settings
    book = prepare_composite_settings(use_hdr=image.is_float)
    scene = bpy.context.scene

    # Set up compositor
    tree = get_compositor_node_tree(scene)
    composite = get_compositor_output_node(tree)
    blur = tree.nodes.new('CompositorNodeBlur')
    if not is_bl_newer_than(5):
        blur.filter_type = filter_type
    else: blur.inputs[2].default_value = blur_type_labels[filter_type]
    if is_bl_newer_than(4, 5):
        blur.inputs['Size'].default_value[0] = size
        blur.inputs['Size'].default_value[1] = size
    else:
        blur.size_x = int(size)
        blur.size_y = int(size)
    image_node = tree.nodes.new('CompositorNodeImage')
    image_node.image = image

    gamma = None
    if image.colorspace_settings.name != get_srgb_name() and not image.is_float:
        nodeid = 'ShaderNodeGamma' if is_bl_newer_than(5) else 'CompositorNodeGamma'
        gamma = tree.nodes.new(nodeid)
        gamma.inputs[1].default_value = 2.2

    rgb = image_node.outputs[0]
    if gamma:
        tree.links.new(rgb, gamma.inputs[0])
        rgb = gamma.outputs[0]
    tree.links.new(rgb, blur.inputs['Image'])
    rgb = blur.outputs[0]
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

    print('BLUR:', image.name, 'blur pass is done in', '{:0.2f}'.format(time.time() - T), 'seconds!')
    return image

def denoise_image(image):
    if not is_bl_newer_than(2, 81): return image

    T = time.time()
    print('DENOISE: Doing Denoise pass on', image.name + '...')

    # Preparing settings
    book = prepare_composite_settings(use_hdr=image.is_float)
    scene = bpy.context.scene

    # Set up compositor
    tree = get_compositor_node_tree(scene)
    composite = get_compositor_output_node(tree)
    denoise = tree.nodes.new('CompositorNodeDenoise')
    if is_bl_newer_than(5):
        denoise.inputs.get('HDR').default_value = image.is_float
    else: denoise.use_hdr = image.is_float
    image_node = tree.nodes.new('CompositorNodeImage')
    image_node.image = image

    gamma = None
    if image.colorspace_settings.name != get_srgb_name() and not image.is_float:
        nodeid = 'ShaderNodeGamma' if is_bl_newer_than(5) else 'CompositorNodeGamma'
        gamma = tree.nodes.new(nodeid)
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

    print('DENOISE:', image.name, 'denoise pass is done in', '{:0.2f}'.format(time.time() - T), 'seconds!')
    return image

def dither_image(image, dither_intensity=1.0, alpha_aware=True):
    if not image.is_float:
        print('DITHER: Cannot dither image \''+image.name+'\' since it\'s not a float image')
        return

    T = time.time()
    print('DITHER: Doing dithering pass on', image.name + '...')

    # Preparing settings
    book = prepare_composite_settings(use_hdr=image.is_float)
    scene = bpy.context.scene

    # Set render to byte image
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.dither_intensity = dither_intensity

    # Set up compositor
    tree = get_compositor_node_tree(scene)
    composite = get_compositor_output_node(tree)
    image_node = tree.nodes.new('CompositorNodeImage')
    image_node.image = image

    if image.source == 'TILED':
        tilenums = [tile.number for tile in image.tiles]
    else: tilenums = [1001]

    prefix_filename = 'DITHER_RENDER___'
    temp_images = []
    temp_filepaths = []

    # Render dithered byte images
    for i, tilenum in enumerate(tilenums):

        # Swap tile to 1001 to access the data
        if tilenum != 1001:
            UDIM.swap_tile(image, 1001, tilenum)

        # Get temporary filepath
        filepath = os.path.join(tempfile.gettempdir(), prefix_filename+str(tilenum)+'.png')
        temp_filepaths.append(filepath)

        # Set render resolution
        scene.render.resolution_x = image.size[0]
        scene.render.resolution_y = image.size[1]

        # Connect image's rgb
        tree.links.new(image_node.outputs[0], composite.inputs[0])

        # Disable alpha is necesarry if image has alpha
        if alpha_aware:
            composite.use_alpha = False

        # Render image!
        bpy.ops.render.render()

        # Save the image
        render_result = next(img for img in bpy.data.images if img.type == "RENDER_RESULT")
        render_result.save_render(filepath)
        temp_image = bpy.data.images.load(filepath)
        temp_images.append(temp_image)

        if alpha_aware:
            composite.use_alpha = True

            # Render alpha image!
            bpy.ops.render.render()

            # Save alpha image
            alpha_filepath = os.path.join(tempfile.gettempdir(), prefix_filename+str(tilenum)+'_ALPHA.png')
            render_result = next(img for img in bpy.data.images if img.type == "RENDER_RESULT")
            render_result.save_render(alpha_filepath)
            alpha_image = bpy.data.images.load(alpha_filepath)

            copy_image_channel_pixels(alpha_image, temp_image, 3, 3)

            # Remove alpha image
            remove_datablock(bpy.data.images, alpha_image)
            os.remove(alpha_filepath)

        # Swap back the tile
        if tilenum != 1001:
            UDIM.swap_tile(image, 1001, tilenum)

    # Convert input image to byte
    image = image_ops.toggle_image_bit_depth(image, no_copy=True, force_srgb=True)

    # Copy images
    for i, tilenum in enumerate(tilenums):

        # Swap tile to 1001 to access the data
        if tilenum != 1001:
            UDIM.swap_tile(image, 1001, tilenum)

        # Get temporary image
        temp_image = temp_images[i]
        filepath = temp_filepaths[i]

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

    print('DENOISE:', image.name, 'dithering pass is done in', '{:0.2f}'.format(time.time() - T), 'seconds!')
    return image

def noise_blur_image(image, alpha_aware=True, factor=1.0, samples=512, bake_device='CPU'):
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
    output = get_material_output(mat, create_one=True)
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
        if not is_bl_newer_than(2, 80):
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

    print('BLUR:', image.name, 'blur pass is done in', '{:0.2f}'.format(time.time() - T), 'seconds!')

    return image

def create_plane_on_object_mode():

    if not is_bl_newer_than(2, 77):
        bpy.ops.mesh.primitive_plane_add()
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=0.0)
        bpy.ops.object.mode_set(mode='OBJECT')
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
    output = get_material_output(mat, create_one=True)
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
    remove_mesh_obj(plane_obj)

    # Recover settings
    recover_bake_settings(book)

    # Recover original active layer collection
    if is_bl_newer_than(2, 80):
        bpy.context.view_layer.active_layer_collection = ori_layer_collection

    print('FXAA:', image.name, 'FXAA pass is done in', '{:0.2f}'.format(time.time() - T), 'seconds!')

    return image

def bake_to_vcol(mat, node, root_ch, objs, extra_channel=None, extra_multiplier=1.0, bake_alpha=False, vcol_name=''):

    # Create setup nodes
    emit = mat.node_tree.nodes.new('ShaderNodeEmission')

    if root_ch.type == 'NORMAL':

        norm = mat.node_tree.nodes.new('ShaderNodeGroup')
        if is_bl_newer_than(2, 80) and not is_bl_newer_than(3):
            norm.node_tree = get_node_tree_lib(lib.BAKE_NORMAL_ACTIVE_UV)
        else: norm.node_tree = get_node_tree_lib(lib.BAKE_NORMAL_ACTIVE_UV_300)

    # Get output node and remember original bsdf input
    output = get_material_output(mat, create_one=True)
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

def is_baked_normal_without_bump_needed(root_ch):
    return (
        (not is_overlay_normal_empty(root_ch) and (any_layers_using_disp(root_ch) or any_layers_using_vdisp(root_ch))) or
        (root_ch.enable_subdiv_setup and (any_layers_using_disp(root_ch) or any_layers_using_vdisp(root_ch)))
    )

def get_bake_max_height(root_ch, mat=None, node=None, tex=None, emit=None):

    T = time.time()
    print('BAKE MAX HEIGHT: Doing Max Height baking on', root_ch.name + '...')

    tree = root_ch.id_data
    yp = tree.yp
    scene = bpy.context.scene
    if not mat: mat = get_active_material()
    if not node: node = get_active_ypaint_node()

    # Do setup first before baking
    book = {}
    ori_margin = scene.render.bake.margin
    high_margin = 1000
    ori_matout_inp = None
    if not tex and not emit:
        obj = bpy.context.object
        uv_layers = get_uv_layers(obj)
        if len(uv_layers) == 0: return
        uv_map = uv_layers[0].name
        mat_out = get_material_output(mat)
        if not mat_out: return

        book = remember_before_bake()
        prepare_bake_settings(book, [obj], yp, samples=1, margin=high_margin, uv_map=uv_map, bake_device='CPU', margin_type='EXTEND')

        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        emit = mat.node_tree.nodes.new('ShaderNodeEmission')

        # Connect emit to output material
        if len(mat_out.inputs[0].links) > 0:
            ori_matout_inp = mat_out.inputs[0].links[0].from_socket
        mat.node_tree.links.new(emit.outputs[0], mat_out.inputs[0])

        mat.node_tree.nodes.active = tex

    else:
        # Use high margin to make sure all pixels are covered
        scene.render.bake.margin = high_margin

    # Check for height socket
    forced_height_ios = False
    if 'Height' not in node.outputs:
        check_all_channel_ios(yp, reconnect=True, force_height_io=True)
        forced_height_ios = True

    # Create target image
    if UDIM.is_udim_supported():
        img = bpy.data.images.new(
            name='____MAXHEIGHT_TEMP', width=100, height=100, 
            alpha=False, tiled=False, float_buffer=True
        )
    else:
        img = bpy.data.images.new(
            name='____MAXHEIGHT_TEMP', width=100, height=100, 
            alpha=False, float_buffer=True
        )

    img.colorspace_settings.name = get_noncolor_name()
    tex.image = img

    # Connect max height output to emit node
    create_link(mat.node_tree, node.outputs[root_ch.name + io_suffix['MAX_HEIGHT']], 
            emit.inputs[0])

    # Bake
    print('BAKE MAX HEIGHT: Baking max height of ' + root_ch.name + ' channel...')
    bake_object_op()

    # Set baked max height image
    max_height_value = img.pixels[0]
    #end_max_height = check_new_node(tree, root_ch, 'end_max_height', 'ShaderNodeValue', 'Max Height')
    #end_max_height.outputs[0].default_value = max_height_value

    # Remove max height image
    remove_datablock(bpy.data.images, img, user=tex, user_prop='image')

    if len(book) > 0:
        # Reconnect original output connections
        if ori_matout_inp:
            mat.node_tree.links.new(ori_matout_inp, mat_out.inputs[0])

        # Delete temporary nodes
        simple_remove_node(mat.node_tree, tex)
        simple_remove_node(mat.node_tree, emit)

        # Recover settings
        recover_bake_settings(book, yp)
    else:
        # Recover margin
        scene.render.bake.margin = ori_margin

    return max_height_value

def get_bake_properties_from_self(self):

    bprops = dotdict()

    # NOTE: Getting props from keys doesn't work
    #for prop in self.properties.keys():
    #    try: bprops[prop] = getattr(self, prop)
    #    except Exception as e: print(e)

    props = [
        'bake_device',
        'samples',
        'margin',
        'margin_type',
        'width',
        'height',
        'image_resolution',
        'use_custom_resolution',
        'name',
        'uv_map',
        'uv_map_1',
        'interpolation',
        'type',
        'use_cage',
        'cage_object_name',
        'cage_extrusion',
        'max_ray_distance',
        'normalize',
        'ao_distance',
        'bevel_samples',
        'bevel_radius',
        'bevel_grayscale_method',
        'multires_base',
        'target_type',
        'fxaa',
        'ssaa',
        'denoise',
        'channel_idx',
        'blend_type',
        'normal_blend_type',
        'normal_map_type',
        'hdr',
        'use_baked_disp',
        'flip_normals',
        'only_local',
        'subsurf_influence',
        'force_bake_all_polygons',
        'use_image_atlas',
        'use_udim',
        'blur',
        'blur_type',
        'blur_factor',
        'blur_size'
    ]

    for prop in props:
        if hasattr(self, prop):
            bprops[prop] = getattr(self, prop)
        elif prop == 'hdr':
            bprops['hdr'] = False

    return bprops

def bake_channel(
        uv_map, mat, node, root_ch, width=1024, height=1024, target_layer=None, use_hdr=False, 
        aa_level=1, force_use_udim=False, tilenums=[], interpolation='Linear', 
        use_float_for_displacement=False, use_float_for_normal=False, bprops=None
    ):

    print('BAKE CHANNEL: Baking', root_ch.name + ' channel...')

    tree = node.node_tree
    yp = tree.yp
    ypup = get_user_preferences()
    scene = bpy.context.scene

    channel_idx = get_channel_index(root_ch)

    # Check if udim image is needed based on number of tiles
    if tilenums == []:
        objs = get_all_objects_with_same_materials(mat)
        tilenums = UDIM.get_tile_numbers(objs, uv_map)

    # Check if baking fake lighting is necessary
    # NOTE: Only needed for Blender 2.80 or less because those are the only versions that can use non-baked fake lighting as bump
    ori_bprops_name = bprops['name'] if bprops else ''
    if not is_bl_newer_than(2, 81) and root_ch.type == 'NORMAL':
        for lay in yp.layers:
            if not lay.enable: continue
            if channel_idx >= len(lay.channels): continue
            ch = lay.channels[channel_idx]
            if not ch.enable: continue
            bake_happened = False

            if lay.type in {'HEMI'} and not lay.use_baked:
                bprops['name'] = 'Baked ' + lay.name
                bprops['hdr'] = is_bl_newer_than(2, 80)
                bake_entity_as_image(lay, bprops, set_image_to_entity=True)
                bake_happened = True

            for mask in lay.masks:
                if mask.type in {'HEMI'} and not mask.use_baked:
                    bprops['name'] = 'Baked ' + mask.name
                    bprops['hdr'] = is_bl_newer_than(2, 80)
                    bake_entity_as_image(mask, bprops, set_image_to_entity=True)
                    bake_happened = True

            if bake_happened:
                reconnect_layer_nodes(lay)
                rearrange_layer_nodes(lay)

    # Recover bprops name
    if ori_bprops_name != '': bprops['name'] = ori_bprops_name

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
    output = get_material_output(mat, create_one=True)
    ori_bsdf = output.inputs[0].links[0].from_socket

    # Create setup nodes
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    emit = mat.node_tree.nodes.new('ShaderNodeEmission')

    # Normal baking need special node setup
    bsdf = None
    norm = None
    if root_ch.type == 'NORMAL':
        if is_bl_newer_than(2, 80):
            # Use principled bsdf for Blender 2.80+
            bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
        else:
            # Use custom normal calculation for legacy blender
            norm = mat.node_tree.nodes.new('ShaderNodeGroup')
            norm.node_tree = get_node_tree_lib(lib.BAKE_NORMAL_ACTIVE_UV_300)

    # Set tex as active node
    mat.node_tree.nodes.active = tex

    #disp_from_socket = None
    #for l in output.inputs['Displacement'].links:
    #    disp_from_socket = l.from_socket

    # Original displacement connection
    ori_disp_from_node = ''
    ori_disp_from_socket = ''

    # Remove displacement link early if displacement setup is enabled and the current channel is not normal channel
    height_root_ch = get_root_height_channel(yp)
    if height_root_ch and root_ch != height_root_ch and height_root_ch.enable_subdiv_setup:
        for link in output.inputs['Displacement'].links:
            ori_disp_from_node = link.from_node.name
            ori_disp_from_socket = link.from_socket.name
            mat.node_tree.links.remove(link)
            break

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
                baked_normal_prep = new_node(
                    tree, root_ch, 'baked_normal_prep',
                    'ShaderNodeGroup', 'Baked Normal Preparation'
                )
                if is_bl_newer_than(2, 80):
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
            img = bpy.data.images.new(
                name=img_name, width=width, height=height,
                alpha=True, tiled=True,
                float_buffer = (root_ch.type == 'NORMAL' and use_float_for_normal) or use_hdr
            )

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
            img = bpy.data.images.new(
                name=img_name, width=width, height=height, alpha=True,
                float_buffer = (root_ch.type == 'NORMAL' and use_float_for_normal) or use_hdr
            )
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
            if norm:
                # Custom normal calculation setup
                rgb = create_link(mat.node_tree, rgb, norm.inputs[0])[0]
                mat.node_tree.links.new(rgb, emit.inputs[0])
            elif bsdf:
                # Baking normal from diffuse bsdf
                ori_normal_space = scene.render.bake.normal_space
                scene.cycles.bake_type = 'NORMAL'
                scene.render.bake.normal_space = 'TANGENT'

                # Connect bsdf node to output
                mat.node_tree.links.new(rgb, bsdf.inputs['Normal'])
                mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

                # HACK: Sometimes the bsdf node need color socket to be also connected
                for rch in yp.channels:
                    if rch.type == 'RGB':
                        soc = node.outputs.get(rch.name)
                        if soc: 
                            mat.node_tree.links.new(soc, bsdf.inputs[0])
                            break
        else:
            mat.node_tree.links.new(rgb, emit.inputs[0])

        # Bake!
        print('BAKE CHANNEL: Baking main image of ' + root_ch.name + ' channel...')
        bake_object_op(scene.cycles.bake_type)

        # Revert back the original bake settings
        if root_ch.type == 'NORMAL' and bsdf:
            scene.cycles.bake_type = 'EMIT'
            scene.render.bake.normal_space = ori_normal_space
            mat.node_tree.links.new(emit.outputs[0], output.inputs[0])

    # Bake displacement
    disp_img = None
    if root_ch.type == 'NORMAL':

        # Make sure height outputs available
        check_all_channel_ios(yp, reconnect=True, force_height_io=True)

        # Break displacement connection if displacement setup is enabled
        if root_ch.enable_subdiv_setup:
            for link in output.inputs['Displacement'].links:
                ori_disp_from_node = link.from_node.name
                ori_disp_from_socket = link.from_socket.name
                mat.node_tree.links.remove(link)
                break

        if not target_layer:

            ### Normal without bump only
            if not is_baked_normal_without_bump_needed(root_ch):
                # Remove baked_normal_overlay
                remove_node(tree, root_ch, 'baked_normal_overlay')
            else:

                baked_normal_overlay = tree.nodes.get(root_ch.baked_normal_overlay)
                if not baked_normal_overlay:
                    baked_normal_overlay = new_node(
                        tree, root_ch, 'baked_normal_overlay', 'ShaderNodeTexImage', 
                        'Baked ' + root_ch.name + ' Overlay Only'
                    )
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

                # Preparing for normal baking
                if bsdf:
                    scene.cycles.bake_type = 'NORMAL'
                    scene.render.bake.normal_space = 'TANGENT'
                    mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

                # Bake
                print('BAKE CHANNEL: Baking normal without bump image of ' + root_ch.name + ' channel...')
                bake_object_op(scene.cycles.bake_type)

                # Recover normal baking related
                if bsdf:
                    scene.cycles.bake_type = 'EMIT'
                    scene.render.bake.normal_space = ori_normal_space
                    mat.node_tree.links.new(emit.outputs[0], output.inputs[0])

                # Recover connection
                if end_linear:
                    create_link(tree, ori_soc, end.inputs[root_ch.name])

                # Set baked normal without bump image
                if baked_normal_overlay.image:
                    temp = baked_normal_overlay.image
                    img_users = get_all_image_users(baked_normal_overlay.image)
                    for user in img_users:
                        user.image = norm_img
                    remove_datablock(bpy.data.images, temp)
                else:
                    baked_normal_overlay.image = norm_img

            ### Vector Displacement
            if not any_layers_using_vdisp(root_ch):
                # Remove baked_vdisp
                remove_node(tree, root_ch, 'baked_vdisp')
            else:

                baked_vdisp = tree.nodes.get(root_ch.baked_vdisp)
                if not baked_vdisp:
                    baked_vdisp = new_node(
                        tree, root_ch, 'baked_vdisp', 'ShaderNodeTexImage', 
                        'Baked ' + root_ch.name + ' Vector Displacement'
                    )
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
                create_link(
                    mat.node_tree,
                    node.outputs[root_ch.name + io_suffix['VDISP']], 
                    emit.inputs[0]
                )

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

            if not any_layers_using_disp(root_ch):
                # Remove baked_disp
                remove_node(tree, root_ch, 'baked_disp')
                remove_node(tree, root_ch, 'end_max_height')
            else:

                ### Max Height

                max_height_value = get_bake_max_height(root_ch, mat, node, tex, emit)
                end_max_height = check_new_node(tree, root_ch, 'end_max_height', 'ShaderNodeValue', 'Max Height')
                end_max_height.outputs[0].default_value = max_height_value

                ### Displacement

                # Create target image
                baked_disp = tree.nodes.get(root_ch.baked_disp)
                if not baked_disp:
                    baked_disp = new_node(
                        tree, root_ch, 'baked_disp', 'ShaderNodeTexImage', 
                        'Baked ' + root_ch.name + ' Displacement'
                    )
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

        if disp_img:

            # Bake setup
            # Spread height only created if layer has no parent
            if target_layer and target_layer.parent_idx == -1:
                spread_height = mat.node_tree.nodes.new('ShaderNodeGroup')
                spread_height.node_tree = get_node_tree_lib(lib.SPREAD_NORMALIZED_HEIGHT)

                create_link(
                    mat.node_tree, node.outputs[root_ch.name + io_suffix['HEIGHT']], 
                    spread_height.inputs[0]
                )
                create_link(
                    mat.node_tree, node.outputs[root_ch.name + io_suffix['ALPHA']], 
                    spread_height.inputs[1]
                )

                create_link(mat.node_tree, spread_height.outputs[0], emit.inputs[0])

            else:
                spread_height = None
                create_link(mat.node_tree, node.outputs[root_ch.name + io_suffix['HEIGHT']], emit.inputs[0])
            tex.image = disp_img

            # Bake
            print('BAKE CHANNEL: Baking displacement image of ' + root_ch.name + ' channel...')
            bake_object_op()

            if target_layer:
                # Get max height value
                max_height_value = get_bake_max_height(root_ch, mat, node, tex, emit)
                if ch: set_entity_prop_value(ch, 'bump_distance', max_height_value)
            else:

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
    if bsdf: simple_remove_node(mat.node_tree, bsdf)
    if norm: simple_remove_node(mat.node_tree, norm)

    # Recover displacement link
    if ori_disp_from_node != '':
        nod = mat.node_tree.nodes.get(ori_disp_from_node)
        if nod: 
            soc = nod.outputs.get(ori_disp_from_socket)
            if soc:
                mat.node_tree.links.new(soc, output.inputs['Displacement'])

    # Recover original bsdf
    mat.node_tree.links.new(ori_bsdf, output.inputs[0])

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

def is_object_bakeable(obj):
    if obj.type != 'MESH': return False
    if hasattr(obj, 'hide_viewport') and obj.hide_viewport: return False
    if len(get_uv_layers(obj)) == 0: return False
    if len(obj.data.polygons) == 0: return False

    return True

def get_bakeable_objects_and_meshes(mat, cage_object=None):
    objs = []
    meshes = []

    for ob in get_scene_objects():
        if not is_object_bakeable(ob): continue
        if cage_object and cage_object == ob: continue

        # Do not bake objects with hide_render on
        if ob.hide_render: continue
        if not in_renderable_layer_collection(ob): continue

        for i, m in enumerate(ob.data.materials):
            if m == mat:
                ob.active_material_index = i
                if ob not in objs and ob.data not in meshes:
                    objs.append(ob)
                    meshes.append(ob.data)

    return objs, meshes

def bake_to_entity(bprops, overwrite_img=None, segment=None):

    T = time.time()
    mat = get_active_material()
    node = get_active_ypaint_node()
    yp = node.node_tree.yp
    scene = bpy.context.scene
    obj = bpy.context.object
    channel_idx = int(bprops.channel_idx) if 'channel_idx' in bprops and len(yp.channels) > 0 else -1

    rdict = {}
    rdict['message'] = ''

    if not obj:
        rdict['message'] = "There's no active object!"
        return rdict

    if bprops.type == 'SELECTED_VERTICES' and obj.mode != 'EDIT':
        rdict['message'] = "Should be in edit mode!"
        return rdict

    if bprops.target_type == 'MASK' and len(yp.layers) == 0:
        rdict['message'] = "Mask need active layer!"
        return rdict

    if bprops.type in {'BEVEL_NORMAL', 'BEVEL_MASK'} and not is_bl_newer_than(2, 80):
        rdict['message'] = "Blender 2.80+ is needed to use this feature!"
        return rdict

    if bprops.type in {'MULTIRES_NORMAL', 'MULTIRES_DISPLACEMENT'} and not is_bl_newer_than(2, 80):
        rdict['message'] = "Blender 2.80+ is needed to use this feature!"
        return rdict

    if (hasattr(obj, 'hide_viewport') and obj.hide_viewport) or obj.hide_render:
        rdict['message'] = "Please unhide render and viewport of the active object!"
        return rdict

    if bprops.type == 'FLOW' and (bprops.uv_map == '' or bprops.uv_map_1 == '' or bprops.uv_map == bprops.uv_map_1):
        rdict['message'] = "UVMap and Straight UVMap cannot be the same or empty!"
        return rdict

    # Get cage object
    cage_object = None
    if bprops.type.startswith('OTHER_OBJECT_') and bprops.use_cage and bprops.cage_object_name != '':
        cage_object = bpy.data.objects.get(bprops.cage_object_name)
        if cage_object:

            if any([mod for mod in cage_object.modifiers if mod.type not in {'ARMATURE'}]) or any([mod for mod in obj.modifiers if mod.type not in {'ARMATURE'}]):
                rdict['message'] = "Mesh modifiers is not working with cage object for now!"
                return rdict

            if len(cage_object.data.polygons) != len(obj.data.polygons):
                rdict['message'] = "Invalid cage object, the cage mesh must have the same number of faces as the active object!"
                return rdict

    objs = [obj] if is_object_bakeable(obj) else []
    if mat.users > 1:
        objs, meshes = get_bakeable_objects_and_meshes(mat, cage_object)

    # Count multires objects
    multires_count = 0
    if bprops.type.startswith('MULTIRES_'):
        for ob in objs:
            if get_multires_modifier(ob):
                multires_count += 1

    if not objs or (bprops.type.startswith('MULTIRES_') and multires_count == 0):
        rdict['message'] = "No valid objects found to bake!"
        return rdict

    do_overwrite = False
    overwrite_image_name = ''
    if overwrite_img:
        do_overwrite = True
        overwrite_image_name = overwrite_img.name

    # Get other objects for other object baking
    other_objs = []
    
    if bprops.type.startswith('OTHER_OBJECT_'):

        # Get other objects based on selected objects with different material
        for o in bpy.context.selected_objects:
            if o in objs or not o.data or not hasattr(o.data, 'materials'): continue
            if mat.name not in o.data.materials:
                other_objs.append(o)

        # Try to get other_objects from bake info
        if overwrite_img:

            bi = segment.bake_info if segment else overwrite_img.y_bake_info

            scene_objs = get_scene_objects()
            for oo in bi.other_objects:
                if is_bl_newer_than(2, 79):
                    ooo = oo.object
                else: ooo = scene_objs.get(oo.object_name)

                if ooo:
                    if is_bl_newer_than(2, 80):
                        # Check if object is on current view layer
                        layer_cols = get_object_parent_layer_collections([], bpy.context.view_layer.layer_collection, ooo)
                        if ooo not in other_objs and any(layer_cols):
                            other_objs.append(ooo)
                    else:
                        o = scene_objs.get(ooo.name)
                        if o and o not in other_objs:
                            other_objs.append(o)

        if bprops.type == 'OTHER_OBJECT_EMISSION':
            other_mats, other_sockets, other_defaults, other_alpha_sockets, other_alpha_defaults, ori_mat_no_nodes = prepare_other_objs_colors(yp, other_objs)

        elif bprops.type == 'OTHER_OBJECT_CHANNELS':
            ch_other_objects, ch_other_mats, ch_other_sockets, ch_other_defaults, ch_other_default_weights, ch_other_alpha_sockets, ch_other_alpha_defaults, ori_mat_no_nodes = prepare_other_objs_channels(yp, other_objs)

        if not other_objs:
            if overwrite_img:
                rdict['message'] = "No source objects found! They're probably deleted!"
                return rdict
            else: 
                rdict['message'] = "Source objects must be selected and it should have different material!"
                return rdict

    # Get tile numbers
    tilenums = [1001]
    if bprops.use_udim:
        tilenums = UDIM.get_tile_numbers(objs, bprops.uv_map)

    # Remember things
    book = remember_before_bake(yp, mat=mat)

    # FXAA doesn't work with hdr image
    # FXAA also does not works well with baked image with alpha, so other object bake will use SSAA instead
    use_fxaa = not bprops.hdr and bprops.fxaa and not bprops.type.startswith('OTHER_OBJECT_')

    # For now SSAA only works with other object baking
    use_ssaa = bprops.ssaa and bprops.type.startswith('OTHER_OBJECT_')

    # Denoising only available for AO bake for now
    use_denoise = bprops.denoise and bprops.type in {'AO', 'BEVEL_MASK', 'BEVEL_NORMAL'} and is_bl_newer_than(2, 81)

    # SSAA will multiply size by 2 then resize it back
    if use_ssaa:
        width = bprops.width * 2
        height = bprops.height * 2
    else:
        width = bprops.width
        height = bprops.height

    # If use baked disp, need to bake normal and height map first
    subdiv_setup_changes = False
    height_root_ch = get_root_height_channel(yp)
    if height_root_ch and bprops.use_baked_disp and not bprops.type.startswith('MULTIRES_'):

        if not height_root_ch.enable_subdiv_setup:
            height_root_ch.enable_subdiv_setup = True
            subdiv_setup_changes = True

    # To hold temporary objects
    temp_objs = []

    # Sometimes Cavity bake will create temporary objects
    if (bprops.type == 'CAVITY' and (bprops.subsurf_influence or bprops.use_baked_disp)):

        # NOTE: Baking cavity with subdiv setup can only happen if there's only one object and no UDIM
        if is_bl_newer_than(4, 2) and len(objs) == 1 and not bprops.use_udim and height_root_ch and height_root_ch.enable_subdiv_setup:

            # Check if there's VDM layer
            vdm_layer = get_first_vdm_layer(yp)
            vdm_uv_name = vdm_layer.uv_name if vdm_layer else bprops.uv_map

            # Get baked combined vdm image
            combined_vdm_image = vector_displacement.get_combined_vdm_image(objs[0], vdm_uv_name, width=bprops.width, height=bprops.height)

            # Bake tangent and bitangent
            # NOTE: Only bake the first object tangent since baking combined mesh can cause memory leak at the moment
            tanimage, bitimage = vector_displacement.get_tangent_bitangent_images(objs[0], bprops.uv_map)

            # Duplicate object
            objs = temp_objs = [get_merged_mesh_objects(scene, objs, True, disable_problematic_modifiers=False)]

            # Use VDM loader geometry nodes
            # NOTE: Geometry nodes currently does not support UDIM, so using UDIM will cause wrong bake result
            set_active_object(objs[0])
            vdm_loader = vector_displacement_lib.get_vdm_loader_geotree(bprops.uv_map, combined_vdm_image, tanimage, bitimage, 1.0)
            bpy.ops.object.modifier_add(type='NODES')
            geomod = objs[0].modifiers[-1]
            geomod.node_group = vdm_loader
            bpy.ops.object.modifier_apply(modifier=geomod.name)

            # Remove temporary datas
            remove_datablock(bpy.data.node_groups, vdm_loader)
            remove_datablock(bpy.data.images, combined_vdm_image)

        else:
            objs = temp_objs = get_duplicated_mesh_objects(scene, objs, True)

    # Join objects then extend with other objects
    elif bprops.type.startswith('OTHER_OBJECT_'):
        if len(objs) > 1:
            objs = [get_merged_mesh_objects(scene, objs)]
            temp_objs = objs.copy()

        objs.extend(other_objs)

    # Join objects if the number of objects is higher than one
    elif not bprops.type.startswith('MULTIRES_') and len(objs) > 1 and not is_join_objects_problematic(yp):
        objs = temp_objs = [get_merged_mesh_objects(scene, objs, True)]

    fill_mode = 'FACE'
    obj_vertex_indices = {}
    if bprops.type == 'SELECTED_VERTICES':
        if bpy.context.tool_settings.mesh_select_mode[0] or bpy.context.tool_settings.mesh_select_mode[1]:
            fill_mode = 'VERTEX'

        if is_bl_newer_than(2, 80):
            edit_objs = [o for o in objs if o.mode == 'EDIT']
        else: edit_objs = [obj]

        for ob in edit_objs:
            mesh = ob.data
            bm = bmesh.from_edit_mesh(mesh)

            bm.verts.ensure_lookup_table()
            #bm.edges.ensure_lookup_table()
            bm.faces.ensure_lookup_table()

            v_indices = []
            if fill_mode == 'FACE':
                for face in bm.faces:
                    if face.select:
                        v_indices.append(face.index)
                        #for loop in face.loops:
                        #    v_indices.append(loop.index)

            else:
                for vert in bm.verts:
                    if vert.select:
                        v_indices.append(vert.index)

            obj_vertex_indices[ob.name] = v_indices

        bpy.ops.object.mode_set(mode = 'OBJECT')
        for ob in objs:
            try:
                vcol = new_vertex_color(ob, TEMP_VCOL, color_fill=(0.0, 0.0, 0.0, 1.0))
                set_active_vertex_color(ob, vcol)
            except: pass
        bpy.ops.object.mode_set(mode = 'EDIT')
        bpy.ops.mesh.y_vcol_fill(color_option ='WHITE')
        bpy.ops.object.mode_set(mode = 'OBJECT')

    # Check if there's channel using alpha
    alpha_outp = None
    for c in yp.channels:
        if c.enable_alpha:
            alpha_outp = node.outputs.get(c.name + io_suffix['ALPHA'])
            if alpha_outp: break

    # Prepare bake settings
    if bprops.type == 'AO':
        if alpha_outp:
            # If there's alpha channel use standard AO bake, which has lesser quality denoising
            bake_type = 'AO'
        else: 
            # When there is no alpha channel use combined render bake, which has better denoising
            bake_type = 'COMBINED'
    elif bprops.type == 'MULTIRES_NORMAL':
        bake_type = 'NORMALS'
    elif bprops.type == 'MULTIRES_DISPLACEMENT':
        bake_type = 'DISPLACEMENT'
    elif bprops.type in {'OTHER_OBJECT_NORMAL', 'OBJECT_SPACE_NORMAL', 'BEVEL_NORMAL'}:
        bake_type = 'NORMAL'
    else: 
        bake_type = 'EMIT'

    # If use only local, hide other objects
    hide_other_objs = bprops.type != 'AO' or bprops.only_local

    # Fit tilesize to bake resolution if samples is equal 1
    if bprops.samples <= 1:
        tile_x = width
        tile_y = height
    else:
        tile_x = 256
        tile_y = 256

    prepare_bake_settings(
        book, objs, yp, samples=bprops.samples, margin=bprops.margin, 
        uv_map=bprops.uv_map, bake_type=bake_type, #disable_problematic_modifiers=True, 
        bake_device=bprops.bake_device, hide_other_objs=hide_other_objs, 
        bake_from_multires=bprops.type.startswith('MULTIRES_'), tile_x = tile_x, tile_y = tile_y, 
        use_selected_to_active=bprops.type.startswith('OTHER_OBJECT_'),
        max_ray_distance=bprops.max_ray_distance, cage_extrusion=bprops.cage_extrusion,
        source_objs=other_objs, use_denoising=False, margin_type=bprops.margin_type,
        use_cage = bprops.use_cage, cage_object_name = bprops.cage_object_name,
        normal_space = 'TANGENT' if bprops.type != 'OBJECT_SPACE_NORMAL' else 'OBJECT'
    )
    # Set multires level
    #ori_multires_levels = {}
    if bprops.type.startswith('MULTIRES_'): #or bprops.type == 'AO':
        for ob in objs:
            mod = get_multires_modifier(ob)

            #mod.render_levels = mod.total_levels
            if mod and bprops.type.startswith('MULTIRES_'):
                mod.render_levels = bprops.multires_base
                mod.levels = bprops.multires_base

            #ori_multires_levels[ob.name] = mod.render_levels

    # Setup for cavity
    if bprops.type == 'CAVITY':

        tt = time.time()
        print('BAKE TO LAYER: Applying subsurf/multires for Cavity bake...')

        # Set vertex color for cavity
        for ob in objs:

            set_active_object(ob)

            if bprops.subsurf_influence or bprops.use_baked_disp:
                need_to_be_applied_modifiers = []
                for m in ob.modifiers:
                    if m.type in {'SUBSURF', 'MULTIRES'} and m.levels > 0 and m.show_viewport:

                        # Set multires to the highest level
                        if m.type == 'MULTIRES':
                            m.levels = m.total_levels

                        need_to_be_applied_modifiers.append(m)

                    # Also apply displace
                    if m.type == 'DISPLACE' and m.show_viewport:
                        need_to_be_applied_modifiers.append(m)

                # Apply shape keys and modifiers
                if any(need_to_be_applied_modifiers):
                    if ob.data.shape_keys:
                        if is_bl_newer_than(3, 3):
                            bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
                        else: bpy.ops.object.shape_key_remove(all=True)

                    for m in need_to_be_applied_modifiers:
                        bpy.ops.object.modifier_apply(modifier=m.name)

            # Create new vertex color for dirt
            try:
                vcol = new_vertex_color(ob, TEMP_VCOL, color_fill=(1.0, 1.0, 1.0, 1.0))
                set_active_vertex_color(ob, vcol)
            except: pass

            bpy.ops.paint.vertex_color_dirt(dirt_angle=math.pi / 2)

        print('BAKE TO LAYER: Applying subsurf/multires is done in', '{:0.2f}'.format(time.time() - tt), 'seconds!')

    # Setup for flow
    if bprops.type == 'FLOW':
        bpy.ops.object.mode_set(mode = 'OBJECT')
        for ob in objs:
            uv_layers = get_uv_layers(ob)
            main_uv = uv_layers.get(bprops.uv_map)
            straight_uv = uv_layers.get(bprops.uv_map_1)

            if main_uv and straight_uv:
                flow_vcol = get_flow_vcol(ob, main_uv, straight_uv)

    # Flip normals setup
    if bprops.flip_normals:
        #ori_mode[obj.name] = obj.mode
        if is_bl_newer_than(2, 80):
            # Deselect other objects first
            for o in other_objs:
                o.select_set(False)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.reveal()
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.flip_normals()
            bpy.ops.object.mode_set(mode='OBJECT')
            # Reselect other objects
            for o in other_objs:
                o.select_set(True)
        else:
            for ob in objs:
                if ob in other_objs: continue
                scene.objects.active = ob
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.reveal()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.flip_normals()
                bpy.ops.object.mode_set(mode='OBJECT')

    # More setup
    ori_mods = {}
    ori_viewport_mods = {}
    ori_mat_ids = {}
    ori_loop_locs = {}
    ori_multires_levels = {}

    # Do not disable modifiers for surface based bake types
    disable_problematic_modifiers = bprops.type not in {'CAVITY', 'POINTINESS', 'BEVEL_NORMAL', 'BEVEL_MASK'}

    for ob in objs:

        # Disable few modifiers
        ori_mods[ob.name] = [m.show_render for m in ob.modifiers]
        ori_viewport_mods[ob.name] = [m.show_viewport for m in ob.modifiers]
        if bprops.type.startswith('MULTIRES_'):
            mul = get_multires_modifier(ob)
            multires_index = 99
            if mul:
                for i, m in enumerate(ob.modifiers):
                    if m == mul: multires_index = i
                    if i > multires_index: 
                        m.show_render = False
                        m.show_viewport = False
        elif disable_problematic_modifiers and ob not in other_objs:
            for m in get_problematic_modifiers(ob):
                m.show_render = False

        ori_mat_ids[ob.name] = []
        ori_loop_locs[ob.name] = []

        if bprops.subsurf_influence and not bprops.use_baked_disp and not bprops.type.startswith('MULTIRES_'):
            for m in ob.modifiers:
                if m.type == 'MULTIRES':
                    ori_multires_levels[ob.name] = m.render_levels
                    m.render_levels = m.total_levels
                    break

        if len(ob.data.materials) > 1:
            active_mat_id = [i for i, m in enumerate(ob.data.materials) if m == mat]
            if active_mat_id: active_mat_id = active_mat_id[0]
            else: continue

            uv_layers = get_uv_layers(ob)
            uvl = uv_layers.get(bprops.uv_map)

            for p in ob.data.polygons:

                # Set uv location to (0,0) if not using current material
                if uvl and not bprops.force_bake_all_polygons:
                    uv_locs = []
                    for li in p.loop_indices:
                        uv_locs.append(uvl.data[li].uv.copy())
                        if p.material_index != active_mat_id:
                            uvl.data[li].uv = Vector((0.0, 0.0))

                    ori_loop_locs[ob.name].append(uv_locs)

                # Need to assign all polygon to active material if there are multiple materials
                ori_mat_ids[ob.name].append(p.material_index)
                p.material_index = active_mat_id

    # Create bake nodes
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    bsdf = None
    map_range = None
    geometry = None
    vector_math = None
    vector_math_1 = None
    if bprops.type == 'BEVEL_NORMAL':
        bsdf = mat.node_tree.nodes.new('ShaderNodeBsdfDiffuse')
    elif bprops.type == 'BEVEL_MASK':
        geometry = mat.node_tree.nodes.new('ShaderNodeNewGeometry')
        vector_math = mat.node_tree.nodes.new('ShaderNodeVectorMath')
        if bprops.bevel_grayscale_method == 'CROSS':
            vector_math.operation = 'CROSS_PRODUCT'
            if is_bl_newer_than(2, 81):
                vector_math_1 = mat.node_tree.nodes.new('ShaderNodeVectorMath')
                vector_math_1.operation = 'LENGTH'
        else:
            vector_math.operation = 'DOT_PRODUCT'
            vector_math_1 = mat.node_tree.nodes.new('ShaderNodeMath')
            vector_math_1.operation = 'SUBTRACT'
            vector_math_1.inputs[0].default_value = 1.0

    if not bsdf:
        bsdf = mat.node_tree.nodes.new('ShaderNodeEmission')

    # Get output node and remember original bsdf input
    output = get_material_output(mat, create_one=True)
    ori_bsdf = output.inputs[0].links[0].from_socket

    if bprops.type == 'AO':
        # If there's alpha channel use standard AO bake, which has lesser quality denoising
        if alpha_outp:
            src = None

            if hasattr(scene.cycles, 'use_fast_gi'):
                scene.cycles.use_fast_gi = True

            if scene.world:
                scene.world.light_settings.distance = bprops.ao_distance
        # When there is no alpha channel use combined render bake, which has better denoising
        else:
            src = mat.node_tree.nodes.new('ShaderNodeAmbientOcclusion')

            if 'Distance' in src.inputs:
                src.inputs['Distance'].default_value = bprops.ao_distance

            # Links
            if not is_bl_newer_than(2, 80):
                mat.node_tree.links.new(src.outputs[0], output.inputs[0])
            else:
                mat.node_tree.links.new(src.outputs['AO'], bsdf.inputs[0])
                mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

    elif bprops.type == 'POINTINESS':
        src = mat.node_tree.nodes.new('ShaderNodeNewGeometry')

        pointy = src.outputs['Pointiness']

        # Map range node
        if is_bl_newer_than(2, 83) and bprops.normalize:
            map_range = mat.node_tree.nodes.new('ShaderNodeMapRange')
            mat.node_tree.links.new(pointy, map_range.inputs[0])
            pointy = map_range.outputs[0]

        # Links
        mat.node_tree.links.new(pointy, bsdf.inputs[0])
        mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

    elif bprops.type == 'CAVITY':
        src = mat.node_tree.nodes.new('ShaderNodeGroup')
        src.node_tree = get_node_tree_lib(lib.CAVITY)

        # Set vcol
        vcol_node = src.node_tree.nodes.get('vcol')
        vcol_node.attribute_name = TEMP_VCOL

        mat.node_tree.links.new(src.outputs[0], bsdf.inputs[0])
        mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

    elif bprops.type == 'DUST':
        src = mat.node_tree.nodes.new('ShaderNodeGroup')
        src.node_tree = get_node_tree_lib(lib.DUST)

        mat.node_tree.links.new(src.outputs[0], bsdf.inputs[0])
        mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

    elif bprops.type == 'PAINT_BASE':
        src = mat.node_tree.nodes.new('ShaderNodeGroup')
        src.node_tree = get_node_tree_lib(lib.PAINT_BASE)

        mat.node_tree.links.new(src.outputs[0], bsdf.inputs[0])
        mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

    elif bprops.type == 'BEVEL_NORMAL':
        src = mat.node_tree.nodes.new('ShaderNodeBevel')

        src.samples = bprops.bevel_samples
        src.inputs[0].default_value = bprops.bevel_radius

        mat.node_tree.links.new(src.outputs[0], bsdf.inputs['Normal'])
        mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

    elif bprops.type == 'BEVEL_MASK':
        src = mat.node_tree.nodes.new('ShaderNodeBevel')

        src.samples = bprops.bevel_samples
        src.inputs[0].default_value = bprops.bevel_radius

        mat.node_tree.links.new(geometry.outputs['Normal'], vector_math.inputs[0])
        mat.node_tree.links.new(src.outputs[0], vector_math.inputs[1])
        #mat.node_tree.links.new(src.outputs[0], bsdf.inputs['Normal'])
        if bprops.bevel_grayscale_method == 'CROSS':
            if is_bl_newer_than(2, 81):
                mat.node_tree.links.new(vector_math.outputs[0], vector_math_1.inputs[0])
                mat.node_tree.links.new(vector_math_1.outputs[1], bsdf.inputs[0])
            else:
                mat.node_tree.links.new(vector_math.outputs[1], bsdf.inputs[0])
        else:
            mat.node_tree.links.new(vector_math.outputs['Value'], vector_math_1.inputs[1])
            mat.node_tree.links.new(vector_math_1.outputs[0], bsdf.inputs[0])

        mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

    elif bprops.type == 'SELECTED_VERTICES':
        if is_bl_newer_than(2, 80):
            src = mat.node_tree.nodes.new('ShaderNodeVertexColor')
            src.layer_name = TEMP_VCOL
        else:
            src = mat.node_tree.nodes.new('ShaderNodeAttribute')
            src.attribute_name = TEMP_VCOL
        mat.node_tree.links.new(src.outputs[0], bsdf.inputs[0])
        mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

    elif bprops.type == 'FLOW':
        # Set vcol
        src = mat.node_tree.nodes.new('ShaderNodeAttribute')
        src.attribute_name = FLOW_VCOL

        mat.node_tree.links.new(src.outputs[0], bsdf.inputs[0])
        mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

    else:
        src = None
        mat.node_tree.links.new(bsdf.outputs[0], output.inputs[0])

    # Get number of target images
    ch_ids = [0]
    
    # Other object channels related
    all_other_mats = []
    ori_from_nodes = {}
    ori_from_sockets = {}

    if bprops.type == 'OTHER_OBJECT_CHANNELS':
        ch_ids = [i for i, coo in enumerate(ch_other_objects) if len(coo) > 0]

        # Get all other materials
        for oo in other_objs:
            for m in oo.data.materials:
                if m == None or not m.use_nodes: continue
                if m not in all_other_mats:
                    all_other_mats.append(m)

        # Remember original socket connected to outputs
        for m in all_other_mats:
            soc = None
            from_node = ''
            from_socket = ''
            mout = get_material_output(m)
            if mout: 
                for l in mout.inputs[0].links:
                    soc = l.from_socket
                    from_node = l.from_node.name
                    from_socket = l.from_socket.name

                # Create temporary emission
                temp_emi = m.node_tree.nodes.get(TEMP_EMISSION)
                if not temp_emi:
                    temp_emi = m.node_tree.nodes.new('ShaderNodeEmission')
                    temp_emi.name = TEMP_EMISSION
                    m.node_tree.links.new(temp_emi.outputs[0], mout.inputs[0])

            ori_from_nodes[m.name] = from_node
            ori_from_sockets[m.name] = from_socket

    elif bprops.type == 'OTHER_OBJECT_EMISSION':
        # Remember original socket connected to outputs
        for m in other_mats:
            soc = None
            from_node = ''
            from_socket = ''
            mout = get_material_output(m)
            if mout: 
                for l in mout.inputs[0].links:
                    soc = l.from_socket
                    from_node = l.from_node.name
                    from_socket = l.from_socket.name

                # Create temporary emission
                temp_emi = m.node_tree.nodes.get(TEMP_EMISSION)
                if not temp_emi:
                    temp_emi = m.node_tree.nodes.new('ShaderNodeEmission')
                    temp_emi.name = TEMP_EMISSION
                    m.node_tree.links.new(temp_emi.outputs[0], mout.inputs[0])

            ori_from_nodes[m.name] = from_node
            ori_from_sockets[m.name] = from_socket

    # Newly created layer index and image
    active_id = None
    image = None

    for idx in ch_ids:

        # Image name and colorspace
        image_name = bprops.name
        colorspace = get_srgb_name()

        if bprops.type == 'OTHER_OBJECT_EMISSION':

            # Set emission connection
            for i, m in enumerate(other_mats):
                default = other_defaults[i]
                socket = other_sockets[i]

                temp_emi = m.node_tree.nodes.get(TEMP_EMISSION)
                if not temp_emi: continue

                if default != None:
                    # Set default
                    if type(default) == float:
                        temp_emi.inputs[0].default_value = (default, default, default, 1.0)
                    else: temp_emi.inputs[0].default_value = (default[0], default[1], default[2], 1.0)

                elif socket:
                    m.node_tree.links.new(socket, temp_emi.inputs[0])

        elif bprops.type == 'OTHER_OBJECT_CHANNELS':

            root_ch = yp.channels[idx]
            image_name += ' ' + yp.channels[idx].name

            # Hide irrelevant objects
            for oo in other_objs:
                if oo not in ch_other_objects[idx]:
                    oo.hide_render = True
                else: oo.hide_render = False

            if root_ch.type == 'NORMAL':
                bake_type = 'NORMAL'

                # Set back original socket
                for m in all_other_mats:
                    mout = get_material_output(m)
                    if mout: 
                        nod = m.node_tree.nodes.get(ori_from_nodes[m.name])
                        if nod:
                            soc = nod.outputs.get(ori_from_sockets[m.name])
                            if soc: m.node_tree.links.new(soc, mout.inputs[0])

            else:
                bake_type = 'EMIT'

                # Set emission connection
                connected_mats = []
                for j, m in enumerate(ch_other_mats[idx]):
                    if m in connected_mats: continue
                    default = ch_other_defaults[idx][j]
                    default_weight = ch_other_default_weights[idx][j]
                    socket = ch_other_sockets[idx][j]

                    temp_emi = m.node_tree.nodes.get(TEMP_EMISSION)
                    if not temp_emi: continue

                    # Make sure temporary emission node is connected
                    if len(temp_emi.outputs[0].links) == 0:
                        mout = get_material_output(m)
                        m.node_tree.links.new(temp_emi.outputs[0], mout.inputs[0])

                    if default != None:
                        # Set default
                        if type(default) == float:
                            temp_emi.inputs[0].default_value = (default, default, default, 1.0)
                        else: temp_emi.inputs[0].default_value = (default[0], default[1], default[2], 1.0)

                        # Break link
                        for l in temp_emi.inputs[0].links:
                            m.node_tree.links.remove(l)
                    elif socket:
                        m.node_tree.links.new(socket, temp_emi.inputs[0])

                    # Set default weight
                    temp_emi.inputs[1].default_value = default_weight

                    connected_mats.append(m)

            colorspace = get_noncolor_name() if root_ch.colorspace == 'LINEAR' else get_srgb_name()

        elif bprops.type in {'BEVEL_NORMAL', 'MULTIRES_NORMAL', 'OTHER_OBJECT_NORMAL', 'OBJECT_SPACE_NORMAL'}:
            colorspace = get_noncolor_name()

        # Using float image will always make the image linear/non-color
        if bprops.hdr:
            colorspace = get_noncolor_name() 

        # Base color of baked image
        if bprops.type == 'AO':
            color = [1.0, 1.0, 1.0, 1.0] 
        elif bake_type in {'NORMAL', 'NORMALS'}:
            color = [0.5, 0.5, 1.0, 1.0] 
        elif bprops.type == 'FLOW':
            color = [0.5, 0.5, 0.0, 1.0]
        else:
            color = [0.5, 0.5, 0.5, 1.0]

        # Make image transparent if its baked from other objects
        if bprops.type.startswith('OTHER_OBJECT_'):
            color = [0.0, 0.0, 0.0, 0.0]

        # New target image
        if bprops.use_udim:
            image = bpy.data.images.new(
                name=image_name, width=width, height=height, 
                alpha=True, float_buffer=bprops.hdr, tiled=True
            )

            # Fill tiles
            for tilenum in tilenums:
                UDIM.fill_tile(image, tilenum, color, width, height)
            UDIM.initial_pack_udim(image, color)

            # Remember base color
            image.yui.base_color = color
        else:
            image = bpy.data.images.new(
                name=image_name, width=width, height=height,
                alpha=True, float_buffer=bprops.hdr
            )

        image.generated_color = color
        image.colorspace_settings.name = colorspace

        # Set image filepath if overwrite image is found
        if do_overwrite:
            # Get overwrite image again to avoid pointer error
            overwrite_img = bpy.data.images.get(overwrite_image_name)
            #if idx == 0:
            if idx == min(ch_ids):
                if not overwrite_img.packed_file and overwrite_img.filepath != '':
                    image.filepath = overwrite_img.filepath
            else:
                layer = yp.layers[yp.active_layer_index]
                root_ch = yp.channels[idx]
                ch = layer.channels[idx]

                if root_ch.type == 'NORMAL':
                    source = get_channel_source_1(ch, layer)
                else: source = get_channel_source(ch, layer)

                if source and hasattr(source, 'image') and source.image and not source.image.packed_file and source.image.filepath != '':
                    image.filepath = source.image.filepath

        # Set bake image
        tex.image = image
        mat.node_tree.nodes.active = tex

        # Bake!
        try:
            if bprops.type.startswith('MULTIRES_'):
                bpy.ops.object.bake_image()
            else:
                if bake_type != 'EMIT':
                    bpy.ops.object.bake(type=bake_type)
                else: bpy.ops.object.bake()
        except Exception as e:

            # Try to use CPU if GPU baking is failed
            if bprops.bake_device == 'GPU':
                print('EXCEPTIION: GPU baking failed! Trying to use CPU...')
                bprops.bake_device = 'CPU'
                scene.cycles.device = 'CPU'

                if bprops.type.startswith('MULTIRES_'):
                    bpy.ops.object.bake_image()
                else:
                    if bake_type != 'EMIT':
                        bpy.ops.object.bake(type=bake_type)
                    else: bpy.ops.object.bake()
            else:
                print('EXCEPTIION:', e)

        if use_fxaa: fxaa_image(image, False, bake_device=bprops.bake_device)

        if bprops.type == 'POINTINESS' and bprops.normalize and is_bl_newer_than(2, 83):
            # Check for highest and lowest value of the baked image
            min_val, max_val = get_pointiness_image_minmax_value(image)

            # Set map range
            map_range.inputs[1].default_value = min_val
            map_range.inputs[2].default_value = max_val

            # Rebake the image again
            bpy.ops.object.bake(type='EMIT')

        # Bake other object alpha
        if bprops.type in {'OTHER_OBJECT_NORMAL', 'OTHER_OBJECT_CHANNELS', 'OTHER_OBJECT_EMISSION'}:
            
            alpha_found = False
            if bprops.type == 'OTHER_OBJECT_CHANNELS':

                # Set emission connection
                for j, m in enumerate(ch_other_mats[idx]):
                    alpha_default = ch_other_alpha_defaults[idx][j]
                    alpha_socket = ch_other_alpha_sockets[idx][j]

                    temp_emi = m.node_tree.nodes.get(TEMP_EMISSION)
                    if not temp_emi: continue

                    if alpha_socket:
                        alpha_found = True
                        m.node_tree.links.new(alpha_socket, temp_emi.inputs[0])

                    else:
                        if alpha_default != 1.0:
                            alpha_found = True

                        # Set alpha_default
                        if type(alpha_default) == float:
                            temp_emi.inputs[0].default_value = (alpha_default, alpha_default, alpha_default, 1.0)
                        else: temp_emi.inputs[0].default_value = (alpha_default[0], alpha_default[1], alpha_default[2], 1.0)

                        # Break link
                        for l in temp_emi.inputs[0].links:
                            m.node_tree.links.remove(l)

            elif bprops.type == 'OTHER_OBJECT_EMISSION':

                # Set emission connection
                for i, m in enumerate(other_mats):
                    alpha_default = other_alpha_defaults[i]
                    alpha_socket = other_alpha_sockets[i]

                    temp_emi = m.node_tree.nodes.get(TEMP_EMISSION)
                    if not temp_emi: continue

                    if alpha_socket:
                        alpha_found = True
                        m.node_tree.links.new(alpha_socket, temp_emi.inputs[0])

                    else: 
                        if alpha_default != 1.0:
                            alpha_found = True

                        # Set alpha_default
                        if type(alpha_default) == float:
                            temp_emi.inputs[0].default_value = (alpha_default, alpha_default, alpha_default, 1.0)
                        else: temp_emi.inputs[0].default_value = (alpha_default[0], alpha_default[1], alpha_default[2], 1.0)

            else:
                alpha_found = True

            if alpha_found:

                temp_img = image.copy()
                temp_img.colorspace_settings.name = get_noncolor_name()
                tex.image = temp_img

                # Set temp filepath
                if image.source == 'TILED':
                    temp_img.name = '__TEMP__'
                    UDIM.initial_pack_udim(temp_img)

                # Need to use clear so there's alpha on the baked image
                scene.render.bake.use_clear = True

                # Bake emit can will create alpha image
                bpy.ops.object.bake(type='EMIT')

                # Set tile pixels
                for tilenum in tilenums:

                    # Swap tile
                    if tilenum != 1001:
                        UDIM.swap_tile(image, 1001, tilenum)
                        UDIM.swap_tile(temp_img, 1001, tilenum)

                    # Copy alpha to RGB channel, so it can be fxaa-ed
                    if bprops.type == 'OTHER_OBJECT_NORMAL':
                        copy_image_channel_pixels(temp_img, temp_img, 3, 0)

                    # FXAA alpha
                    fxaa_image(temp_img, False, bprops.bake_device, first_tile_only=True)

                    # Copy alpha to actual image
                    copy_image_channel_pixels(temp_img, image, 0, 3)

                    # Swap tile again to recover
                    if tilenum != 1001:
                        UDIM.swap_tile(image, 1001, tilenum)
                        UDIM.swap_tile(temp_img, 1001, tilenum)

                # Remove temp image
                remove_datablock(bpy.data.images, temp_img, user=tex, user_prop='image')

        # HACK: On Blender 4.5, tex node can be mistakenly use previous index image as current one when resize_image is called
        # Set the tex node image to None before resize_image can resolve this
        tex.image = None

        # Back to original size if using SSAA
        if use_ssaa:
            image, temp_segment = resize_image(
                image, bprops.width, bprops.height, image.colorspace_settings.name,
                alpha_aware=True, bake_device=bprops.bake_device
            )

        # Denoise AO image
        if use_denoise:
            image = denoise_image(image)

        new_segment_created = False

        if bprops.use_image_atlas:

            need_to_create_new_segment = False
            if segment:
                ia_image = segment.id_data
                if bprops.use_udim:
                    need_to_create_new_segment = ia_image.is_float != bprops.hdr
                    if need_to_create_new_segment:
                        UDIM.remove_udim_atlas_segment_by_name(ia_image, segment.name, yp)
                else:
                    need_to_create_new_segment = bprops.width != segment.width or bprops.height != segment.height or ia_image.is_float != bprops.hdr
                    if need_to_create_new_segment:
                        segment.unused = True

            if not segment or need_to_create_new_segment:

                if bprops.use_udim:
                    segment = UDIM.get_set_udim_atlas_segment(
                        tilenums, color=(0, 0, 0, 0), colorspace=get_srgb_name(), hdr=bprops.hdr, yp=yp
                    )
                else:
                    # Clearing unused image atlas segments
                    img_atlas = ImageAtlas.check_need_of_erasing_segments(yp, 'TRANSPARENT', bprops.width, bprops.height, bprops.hdr)
                    if img_atlas: ImageAtlas.clear_unused_segments(img_atlas.yia)

                    segment = ImageAtlas.get_set_image_atlas_segment(
                        bprops.width, bprops.height, 'TRANSPARENT', bprops.hdr, yp=yp
                    )

                new_segment_created = True

            ia_image = segment.id_data

            # Set baked image to segment
            if bprops.use_udim:
                offset = get_udim_segment_mapping_offset(segment) * 10
                copy_dict = {}
                for tilenum in tilenums:
                    copy_dict[tilenum] = tilenum + offset
                UDIM.copy_tiles(image, ia_image, copy_dict)
            else: copy_image_pixels(image, ia_image, segment)
            temp_img = image
            image = ia_image

            # Remove original baked image
            remove_datablock(bpy.data.images, temp_img)

        # Index 0 is the main image
        if idx == min(ch_ids):
            if do_overwrite:

                # Get overwrite image again to avoid pointer error
                overwrite_img = bpy.data.images.get(overwrite_image_name)

                active_id = yp.active_layer_index

                if overwrite_img != image:
                    if segment and not bprops.use_image_atlas:
                        entities = ImageAtlas.replace_segment_with_image(yp, segment, image)
                        segment = None
                    else: entities = replace_image(overwrite_img, image, yp, bprops.uv_map)
                elif segment: entities = ImageAtlas.get_entities_with_specific_segment(yp, segment)
                else: entities = get_entities_with_specific_image(yp, image)

                for ent in entities:
                    if new_segment_created:
                        ent.segment_name = segment.name
                        ImageAtlas.set_segment_mapping(ent, segment, image)

                    if ent.uv_name != bprops.uv_map:
                        ent.uv_name = bprops.uv_map

                    if bprops.type == 'AO' and ent.type == 'AO':
                        set_entity_prop_value(ent, 'ao_distance', bprops.ao_distance)
                    elif bprops.type == 'BEVEL_MASK' and ent.type == 'EDGE_DETECT':
                        set_entity_prop_value(ent, 'edge_detect_radius', bprops.bevel_radius)
                        ent.edge_detect_method = bprops.bevel_grayscale_method

                if bprops.target_type == 'LAYER':
                    layer_ids = [i for i, l in enumerate(yp.layers) if l in entities]
                    if entities and yp.active_layer_index not in layer_ids:
                        active_id = layer_ids[0]

                    # Refresh uv
                    refresh_temp_uv(bpy.context.object, yp.layers[active_id])

                    # Refresh Neighbor UV resolution
                    set_uv_neighbor_resolution(yp.layers[active_id])

                elif bprops.target_type == 'MASK':
                    masks = []
                    for l in yp.layers:
                        masks.extend([m for m in l.masks if m in entities])
                    if masks: 
                        masks[0].active_edit = True

                        # Refresh uv
                        refresh_temp_uv(bpy.context.object, masks[0])

                        # Refresh Neighbor UV resolution
                        set_uv_neighbor_resolution(masks[0])

            elif bprops.target_type == 'LAYER':

                layer_name = image.name if not bprops.use_image_atlas else bprops.name

                if bprops.use_image_atlas:
                    layer_name = get_unique_name(layer_name, yp.layers)

                yp.halt_update = True
                layer = Layer.add_new_layer(
                    group_tree=node.node_tree, layer_name=layer_name,
                    layer_type='IMAGE', channel_idx=channel_idx,
                    blend_type=bprops.blend_type, normal_blend_type=bprops.normal_blend_type,
                    normal_map_type=bprops['normal_map_type'], texcoord_type='UV',
                    uv_name=bprops.uv_map, image=image, vcol=None, segment=segment,
                    interpolation = bprops.interpolation,
                    normal_space = 'OBJECT' if bprops.type == 'OBJECT_SPACE_NORMAL' else 'TANGENT'
                )
                yp.halt_update = False
                active_id = yp.active_layer_index

                if segment:
                    ImageAtlas.set_segment_mapping(layer, segment, image)

                # Refresh uv
                refresh_temp_uv(bpy.context.object, layer)

                # Refresh Neighbor UV resolution
                set_uv_neighbor_resolution(layer)


            else:
                active_layer = yp.layers[yp.active_layer_index]

                mask_name = image.name if not bprops.use_image_atlas else bprops.name

                if bprops.use_image_atlas:
                    mask_name = get_unique_name(mask_name, active_layer.masks)

                mask = Mask.add_new_mask(
                    active_layer, mask_name, 'IMAGE', 'UV', bprops.uv_map,
                    image, '', segment
                )
                mask.active_edit = True

                reconnect_layer_nodes(active_layer)
                rearrange_layer_nodes(active_layer)

                active_id = yp.active_layer_index

                if segment:
                    ImageAtlas.set_segment_mapping(mask, segment, image)

                # Refresh uv
                refresh_temp_uv(bpy.context.object, mask)

                # Refresh Neighbor UV resolution
                set_uv_neighbor_resolution(mask)

        # Indices > 0 are for channel override images
        else:
            # Set images to channel override
            layer = yp.layers[yp.active_layer_index]
            root_ch = yp.channels[idx]
            ch = layer.channels[idx]
            if not ch.enable: ch.enable = True

            # Normal channel will use second override
            if root_ch.type == 'NORMAL':
                if ch.normal_map_type != 'NORMAL_MAP': ch.normal_map_type = 'NORMAL_MAP'
                if not ch.override_1: ch.override_1 = True
                if ch.override_1_type != 'IMAGE': ch.override_1_type = 'IMAGE'
                source = get_channel_source_1(ch, layer)
            else:
                if not ch.override: ch.override = True
                if ch.override_type != 'IMAGE': ch.override_type = 'IMAGE'
                source = get_channel_source(ch, layer)

            # If image already exists on source
            old_image = None
            if source.image and image != source.image:
                old_image = source.image
                source_name = old_image.name
                current_name = image.name

                old_image.name = '_____temp'
                image.name = source_name
                old_image.name = current_name
                
            # Set image to source
            source.image = image
            source.interpolation = bprops.interpolation

            # Remove image if it's not used anymore
            if old_image: safe_remove_image(old_image)

        # Set bake info to image/segment
        bi = segment.bake_info if segment else image.y_bake_info

        if not bi.is_baked: bi.is_baked = True
        if bi.bake_type != bprops.type: bi.bake_type = bprops.type
        for attr in dir(bi):
            if attr.startswith('__'): continue
            if attr.startswith('bl_'): continue
            if attr in {'rna_type'}: continue
            try: setattr(bi, attr, bprops[attr])
            except: pass

        if other_objs:

            # Remember other objects to bake info
            for o in other_objs:
                if is_bl_newer_than(2, 79): 
                    oo_recorded = any([oo for oo in bi.other_objects if oo.object == o])
                else: oo_recorded = any([oo for oo in bi.other_objects if oo.object_name == o.name])

                if not oo_recorded:
                    oo = bi.other_objects.add()
                    if is_bl_newer_than(2, 79): 
                        oo.object = o
                    oo.object_name = o.name

            # Remove unused other objects on bake info
            for i, oo in reversed(list(enumerate(bi.other_objects))):
                if is_bl_newer_than(2, 79):
                    ooo = oo.object
                else: ooo = bpy.data.objects.get(oo.object_name)

                if ooo not in other_objs:
                    bi.other_objects.remove(i)

        if bprops.type == 'SELECTED_VERTICES':
            #fill_mode = 'FACE'
            #obj_vertex_indices = {}
            bi.selected_face_mode = True if fill_mode == 'FACE' else False

            # Clear selected objects first
            bi.selected_objects.clear()

            # Collect object to bake info
            for obj_name, v_indices in obj_vertex_indices.items():
                ob = bpy.data.objects.get(obj_name)
                bso = bi.selected_objects.add()
                if is_bl_newer_than(2, 79):
                    bso.object = ob
                bso.object_name = ob.name

                # Collect selected vertex data to bake info
                for vi in v_indices:
                    bvi = bso.selected_vertex_indices.add()
                    bvi.index = vi

    # Recover other yps
    if bprops.type in {'OTHER_OBJECT_CHANNELS', 'OTHER_OBJECT_EMISSION'}:

        mats = all_other_mats if bprops.type == 'OTHER_OBJECT_CHANNELS' else other_mats
        for m in mats:
            # Set back original socket
            mout = get_material_output(m)
            if mout: 
                nod = m.node_tree.nodes.get(ori_from_nodes[m.name])
                if nod:
                    soc = nod.outputs.get(ori_from_sockets[m.name])
                    if soc: m.node_tree.links.new(soc, mout.inputs[0])

            # Remove temp emission
            temp_emi = m.node_tree.nodes.get(TEMP_EMISSION)
            if temp_emi: m.node_tree.nodes.remove(temp_emi)

        # Recover other objects material settings
        recover_other_objs_channels(other_objs, ori_mat_no_nodes)

    # Remove temp bake nodes
    simple_remove_node(mat.node_tree, tex)
    simple_remove_node(mat.node_tree, bsdf)
    if src: simple_remove_node(mat.node_tree, src)
    if geometry: simple_remove_node(mat.node_tree, geometry)
    if map_range: simple_remove_node(mat.node_tree, map_range)
    if vector_math: simple_remove_node(mat.node_tree, vector_math)
    if vector_math_1: simple_remove_node(mat.node_tree, vector_math_1)

    # Recover original bsdf
    mat.node_tree.links.new(ori_bsdf, output.inputs[0])

    for ob in objs:
        # Recover modifiers
        for i, m in enumerate(ob.modifiers):
            #print(ob.name, i)
            if i >= len(ori_mods[ob.name]): break
            if ori_mods[ob.name][i] != m.show_render:
                m.show_render = ori_mods[ob.name][i]
            if i >= len(ori_viewport_mods[ob.name]): break
            if ori_viewport_mods[ob.name][i] != m.show_render:
                m.show_viewport = ori_viewport_mods[ob.name][i]

        # Recover multires levels
        for m in ob.modifiers:
            if m.type == 'MULTIRES' and ob.name in ori_multires_levels:
                m.render_levels = ori_multires_levels[ob.name]
                break

        # Recover material index
        if ori_mat_ids[ob.name]:
            for i, p in enumerate(ob.data.polygons):
                if ori_mat_ids[ob.name][i] != p.material_index:
                    p.material_index = ori_mat_ids[ob.name][i]

        if ori_loop_locs[ob.name]:

            # Get uv map
            uv_layers = get_uv_layers(ob)
            uvl = uv_layers.get(bprops.uv_map)

            # Recover uv locations
            if uvl:
                for i, p in enumerate(ob.data.polygons):
                    for j, li in enumerate(p.loop_indices):
                        uvl.data[li].uv = ori_loop_locs[ob.name][i][j]

        # Delete temp vcol
        vcols = get_vertex_colors(ob)
        if vcols:
            vcol = vcols.get(TEMP_VCOL)
            if vcol: vcols.remove(vcol)

    # Recover flip normals setup
    if bprops.flip_normals:
        #bpy.ops.object.mode_set(mode = 'EDIT')
        #bpy.ops.mesh.flip_normals()
        #bpy.ops.mesh.select_all(action='DESELECT')
        #bpy.ops.object.mode_set(mode = ori_mode)
        if is_bl_newer_than(2, 80):
            # Deselect other objects first
            for o in other_objs:
                o.select_set(False)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.reveal()
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.flip_normals()
            bpy.ops.object.mode_set(mode='OBJECT')
            # Reselect other objects
            for o in other_objs:
                o.select_set(True)
        else:
            for ob in objs:
                if ob in other_objs: continue
                scene.objects.active = ob
                bpy.ops.object.mode_set(mode='EDIT')
                bpy.ops.mesh.reveal()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.flip_normals()
                bpy.ops.object.mode_set(mode='OBJECT')

    # Recover subdiv setup
    if height_root_ch and subdiv_setup_changes:
        height_root_ch.enable_subdiv_setup = not height_root_ch.enable_subdiv_setup

    # Remove flow vcols
    if bprops.type == 'FLOW':
        for ob in objs:
            vcols = get_vertex_colors(ob)
            flow_vcol = vcols.get(FLOW_VCOL)
            if flow_vcol:
                vcols.remove(flow_vcol)

    # Recover bake settings
    recover_bake_settings(book, yp, mat=mat)

    # Hide other objects after baking
    if is_bl_newer_than(2, 79) and bprops.type.startswith('OTHER_OBJECT_') and other_objs:
        for oo in other_objs:
            oo.hide_viewport = True

    # Remove temporary objects
    if temp_objs:
        for o in temp_objs:
            remove_mesh_obj(o)

    # Check linear nodes becuse sometimes bake results can be linear or srgb
    check_yp_linear_nodes(yp, reconnect=True)

    # Reconnect and rearrange nodes
    #reconnect_yp_layer_nodes(node.node_tree)
    reconnect_yp_nodes(node.node_tree)
    rearrange_yp_nodes(node.node_tree)

    # Refresh mapping and stuff
    #yp.active_layer_index = yp.active_layer_index

    time_elapsed = time.time() - T

    if image: print('BAKE TO LAYER: Baking', image.name, 'is done in', '{:0.2f}'.format(time_elapsed), 'seconds!')
    else: print('BAKE TO LAYER: No image created! Executed in', '{:0.2f}'.format(time_elapsed), 'seconds!')

    rdict['active_id'] = active_id
    rdict['image'] = image
    rdict['time_elapsed'] = time_elapsed

    return rdict

def put_image_to_image_atlas(yp, image, tilenums=[]):

    if image.source == 'TILED':
        segment = UDIM.get_set_udim_atlas_segment(
            tilenums, color=(0, 0, 0, 1), colorspace=get_noncolor_name(), hdr=image.is_float, yp=yp
        )
    else:
        # Clearing unused image atlas segments
        img_atlas = ImageAtlas.check_need_of_erasing_segments(yp, 'BLACK', image.size[0], image.size[1], image.is_float)
        if img_atlas: ImageAtlas.clear_unused_segments(img_atlas.yia)

        segment = ImageAtlas.get_set_image_atlas_segment(
            image.size[0], image.size[1], 'BLACK', image.is_float, yp=yp
        )

    ia_image = segment.id_data

    # Set baked image to segment
    if image.source == 'TILED':
        offset = get_udim_segment_mapping_offset(segment) * 10
        copy_dict = {}
        for tilenum in tilenums:
            copy_dict[tilenum] = tilenum + offset
        UDIM.copy_tiles(image, ia_image, copy_dict)
    else: copy_image_pixels(image, ia_image, segment)

    # Remove original baked image
    remove_datablock(bpy.data.images, image)

    return ia_image, segment

def bake_entity_as_image(entity, bprops, set_image_to_entity=False):

    rdict = {}
    rdict['message'] = ''

    yp = entity.id_data.yp
    mat = get_active_material()
    obj = bpy.context.object

    if not obj:
        rdict['message'] = "There's no active object!"
        return rdict

    if (hasattr(obj, 'hide_viewport') and obj.hide_viewport) or obj.hide_render:
        rdict['message'] = "Please unhide render and viewport of the active object!"
        return rdict

    objs = [obj] if is_object_bakeable(obj) else []
    if mat.users > 1:
        objs, _ = get_bakeable_objects_and_meshes(mat)

    if not objs:
        rdict['message'] = "No valid objects found to bake!"
        return rdict

    # Get tile numbers
    tilenums = [1001]
    if bprops.use_udim:
        tilenums = UDIM.get_tile_numbers(objs, bprops.uv_map)

    m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'^yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    ori_use_baked = False
    ori_enabled_mods = []

    #ori_enable_blur = False
    modifiers_disabled = False
    if m1: 
        layer = yp.layers[int(m1.group(1))]
        mask = None
        source_tree = get_source_tree(layer)
    elif m2: 
        layer = yp.layers[int(m2.group(1))]
        mask = layer.masks[int(m2.group(2))]
        source_tree = get_mask_tree(mask)

    else: 
        rdict['message'] = "Wrong entity!"
        return rdict

    # Disable use baked first
    if entity.use_baked: 
        ori_use_baked = True
        entity.use_baked = False

    # Setting image to entity will disable modifiers
    if set_image_to_entity:
        for mod in entity.modifiers:
            if mod.enable:
                ori_enabled_mods.append(mod)
                mod.enable = False
        modifiers_disabled = True
        #ori_enable_blur = entity.enable_blur_vector
        #entity.enable_blur_vector = False

    # Get existing baked image
    existing_image = None
    baked_source = source_tree.nodes.get(entity.baked_source)
    if baked_source: existing_image = baked_source.image

    # Remember things
    book = remember_before_bake(yp)

    # FXAA doesn't work with hdr image
    # FXAA also does not works well with baked image with alpha, so other object bake will use SSAA instead
    use_fxaa = not bprops.hdr and bprops.fxaa

    # Remember before doing preview
    ori_channel_index = yp.active_channel_index
    ori_preview_mode = yp.preview_mode
    ori_layer_preview_mode = yp.layer_preview_mode
    ori_layer_preview_mode_type = yp.layer_preview_mode_type

    ori_layer_intensity_value = 1.0
    changed_layer_channel_index = -1
    ori_layer_channel_intensity_value = 1.0
    ori_layer_channel_blend_type = 'MIX'
    ori_layer_channel_override = None
    ori_layer_enable_masks = None

    # Make sure layer is enabled
    ori_layer_enable = layer.enable
    layer.enable = True
    layer_opacity = get_entity_prop_value(layer, 'intensity_value')
    if layer_opacity != 1.0:
        ori_layer_intensity_value = layer_opacity
        set_entity_prop_value(layer, 'intensity_value', 1.0)
    
    # Make sure layer is active one
    ori_layer_idx = yp.active_layer_index
    layer_idx = get_layer_index(layer)
    if yp.active_layer_index != layer_idx:
        yp.active_layer_index = layer_idx

    if mask: 
        # Set up active edit
        ori_mask_enable = mask.enable
        mask.enable = True
        mask.active_edit = True
    else:
        # Disable masks
        ori_layer_enable_masks = layer.enable_masks
        if layer.enable_masks:
            layer.enable_masks = False
        for m in layer.masks:
            if m.active_edit: m.active_edit = False

    # Preview setup
    yp.layer_preview_mode_type = 'SPECIFIC_MASK' if mask else 'LAYER'
    yp.layer_preview_mode = True

    # Set active channel so preview will output right value
    for i, ch in enumerate(layer.channels):
        if mask:
            if ch.enable and mask.channels[i].enable:
                yp.active_channel_index = i
                break
        else:
            if ch.enable:
                yp.active_channel_index = i

                # Make sure intensity value is 1.0
                intensity_value = get_entity_prop_value(ch, 'intensity_value')
                if intensity_value != 1.0:
                    changed_layer_channel_index = i
                    ori_layer_channel_intensity_value = intensity_value
                    set_entity_prop_value(ch, 'intensity_value', 1.0)

                if ch.blend_type != 'MIX':
                    changed_layer_channel_index = i
                    ori_layer_channel_blend_type = ch.blend_type
                    ch.blend_type = 'MIX'

                if ch.override:
                    changed_layer_channel_index = i
                    ori_layer_channel_override = True
                    ch.override = False

                break

    # Modifier setups
    ori_mods = {}
    ori_viewport_mods = {}

    for obj in objs:

        # Disable few modifiers
        ori_mods[obj.name] = [m.show_render for m in obj.modifiers]
        ori_viewport_mods[obj.name] = [m.show_viewport for m in obj.modifiers]

        for m in get_problematic_modifiers(obj):
            m.show_render = False

    prepare_bake_settings(
        book, objs, yp, samples=bprops.samples, margin=bprops.margin, 
        uv_map=bprops.uv_map, bake_type='EMIT', bake_device=bprops.bake_device, 
        margin_type = bprops.margin_type
    )

    # Create bake nodes
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')

    if mask:
        color = (0, 0, 0, 1)
        color_str = 'BLACK'
        colorspace = get_noncolor_name()
    else: 
        color = (0, 0, 0, 0)
        color_str = 'TRANSPARENT'
        colorspace = get_noncolor_name() if bprops.hdr else get_srgb_name()

    # Use existing image colorspace if available
    if existing_image:
        colorspace = existing_image.colorspace_settings.name

    # Create image
    if bprops.use_udim:
        image = bpy.data.images.new(
            name=bprops.name, width=bprops.width, height=bprops.height,
            alpha=True, float_buffer=bprops.hdr, tiled=True
        )

        # Fill tiles
        for tilenum in tilenums:
            UDIM.fill_tile(image, tilenum, color, bprops.width, bprops.height)
        UDIM.initial_pack_udim(image, color)

        # Remember base color
        image.yia.color = color_str
    else:
        image = bpy.data.images.new(
            name=bprops.name, width=bprops.width, height=bprops.height,
            alpha=True, float_buffer=bprops.hdr
        )

    image.generated_color = color
    image.colorspace_settings.name = colorspace

    # Set bake image
    tex.image = image
    mat.node_tree.nodes.active = tex

    # Bake!
    bpy.ops.object.bake()

    if bprops.blur: 
        samples = 4096 if is_bl_newer_than(3) else 128
        if bprops.blur_type == 'NOISE':
            noise_blur_image(image, False, bake_device=bprops.bake_device, factor=bprops.blur_factor, samples=samples)
        else: blur_image(image, filter_type=bprops.blur_type, size=bprops.blur_size)
    if bprops.denoise:
        denoise_image(image)
    if use_fxaa: fxaa_image(image, False, bake_device=bprops.bake_device)

    # Remove temp bake nodes
    simple_remove_node(mat.node_tree, tex, remove_data=False)

    # Recover bake settings
    recover_bake_settings(book, yp)

    # Recover modifiers
    for obj in objs:
        # Recover modifiers
        for i, m in enumerate(obj.modifiers):
            #print(obj.name, i)
            if i >= len(ori_mods[obj.name]): break
            if ori_mods[obj.name][i] != m.show_render:
                m.show_render = ori_mods[obj.name][i]
            if i >= len(ori_viewport_mods[obj.name]): break
            if ori_viewport_mods[obj.name][i] != m.show_render:
                m.show_viewport = ori_viewport_mods[obj.name][i]

    # Recover preview
    yp.active_channel_index = ori_channel_index
    if yp.preview_mode != ori_preview_mode:
        yp.preview_mode = ori_preview_mode
    if yp.layer_preview_mode != ori_layer_preview_mode:
        yp.layer_preview_mode = ori_layer_preview_mode
    if yp.layer_preview_mode_type != ori_layer_preview_mode_type:
        yp.layer_preview_mode_type = ori_layer_preview_mode_type

    if changed_layer_channel_index != -1:
        ch = layer.channels[changed_layer_channel_index]

        if ori_layer_channel_intensity_value != 1.0:
            set_entity_prop_value(ch, 'intensity_value', ori_layer_channel_intensity_value)

        if ori_layer_channel_blend_type != 'MIX':
            ch.blend_type = ori_layer_channel_blend_type

        if ori_layer_channel_override != None and ch.override != ori_layer_channel_override:
            ch.override = ori_layer_channel_override

    if ori_layer_intensity_value != 1.0:
        set_entity_prop_value(layer, 'intensity_value', ori_layer_intensity_value)

    if ori_layer_enable_masks != None and layer.enable_masks != ori_layer_enable_masks:
        layer.enable_masks = ori_layer_enable_masks

    if ori_layer_idx != yp.active_layer_index:
        yp.active_layer_index = ori_layer_idx

    if ori_layer_enable != layer.enable:
        layer.enable = ori_layer_enable

    if mask and ori_mask_enable != mask.enable:
        mask.enable = ori_mask_enable

    if modifiers_disabled:
        for mod in ori_enabled_mods:
            mod.enable = True

        #if ori_enable_blur:
        #    mask.enable_blur_vector = True

    if ori_use_baked:
        entity.use_baked = True

    # Set up image atlas segment
    segment = None
    if bprops.use_image_atlas:
        image, segment = put_image_to_image_atlas(yp, image, tilenums)

    if set_image_to_entity:

        layer_tree = get_tree(layer)
        if mask: source_tree = get_mask_tree(mask)
        else: source_tree = get_source_tree(layer)

        yp.halt_update = True

        # Set bake info to image/segment
        bi = segment.bake_info if segment else image.y_bake_info

        bi.is_baked = True
        bi.is_baked_entity = True
        bi.baked_entity_type = entity.type
        for attr in dir(bi):
            if attr.startswith('__'): continue
            if attr.startswith('bl_'): continue
            if attr in {'rna_type'}: continue
            try: setattr(bi, attr, bprops[attr])
            except: pass

        # Set bake type for some types
        if entity.type == 'EDGE_DETECT':
            bi.bake_type = 'BEVEL_MASK'
            bi.bevel_radius = get_entity_prop_value(entity, 'edge_detect_radius')
            bi.bevel_grayscale_method = entity.edge_detect_method
        elif entity.type == 'AO':
            source = get_entity_source(entity)
            bi.bake_type = 'AO'
            bi.ao_distance = get_entity_prop_value(entity, 'ao_distance')
            bi.only_local = source.only_local

        # Get baked source
        overwrite_image = None
        baked_source = source_tree.nodes.get(entity.baked_source)
        if baked_source:
            overwrite_image = baked_source.image

            # Remove old segment
            if entity.baked_segment_name != '':
                if overwrite_image.yia.is_image_atlas:
                    old_segment = overwrite_image.yia.segments.get(entity.baked_segment_name)
                    old_segment.unused = True
                elif overwrite_image.yua.is_udim_atlas:
                    UDIM.remove_udim_atlas_segment_by_name(overwrite_image, entity.baked_segment_name, yp=yp)

                # Remove baked segment name
                entity.baked_segment_name = ''
        else:
            baked_source = new_node(source_tree, entity, 'baked_source', 'ShaderNodeTexImage', 'Baked Mask Source')

        # Set image to baked node
        if overwrite_image and not segment:
            replace_image(overwrite_image, image)
        else: baked_source.image = image

        height_ch = get_height_channel(layer)
        if height_ch and height_ch.enable:
            baked_source.interpolation = 'Cubic'

        # Set entity props
        entity.baked_uv_name = bprops.uv_map
        entity.use_baked = True

        yp.halt_update = False

        if segment:
            # Set up baked mapping
            mapping = check_new_node(layer_tree, entity, 'baked_mapping', 'ShaderNodeMapping', 'Baked Mapping')
            clear_mapping(entity, use_baked=True)
            ImageAtlas.set_segment_mapping(entity, segment, image, use_baked=True)

            # Set baked segment name to entity
            entity.baked_segment_name = segment.name
        else:
            remove_node(layer_tree, entity, 'baked_mapping')

        # Refresh uv
        refresh_temp_uv(bpy.context.object, entity)

        # Refresh Neighbor UV resolution
        set_uv_neighbor_resolution(entity)

        # Update global uv
        check_uv_nodes(yp)

        # Update layer tree inputs
        check_all_layer_channel_io_and_nodes(layer)
        check_start_end_root_ch_nodes(yp.id_data)

    rdict['image'] = image
    rdict['segment'] = segment

    return rdict

def rebake_baked_images(yp, specific_layers=[]):
    tt = time.time()
    print('INFO: Rebaking images is started...')

    entities, images, segment_names, segment_name_props = get_yp_entities_images_and_segments(yp, specific_layers=specific_layers)

    baked_counts = 0

    for i, image in enumerate(images):
        print('INFO: Rebaking image \''+image.name+'\'...')

        if image.yia.is_image_atlas:
            segment = image.yia.segments.get(segment_names[i])
        elif image.yua.is_udim_atlas: 
            segment = image.yua.segments.get(segment_names[i])
        else: segment = None

        if ((segment and segment.bake_info.is_baked and not segment.bake_info.is_baked_channel) or 
            (not segment and image.y_bake_info.is_baked and not image.y_bake_info.is_baked_channel)
            ):

            bi = image.y_bake_info if not segment else segment.bake_info

            # Skip outdated bake type
            if bi.bake_type == 'SELECTED_VERTICES':
                continue

            entity = entities[i][0]
            entity_path = entity.path_from_id()
            segment_name_prop = segment_name_props[i][0]

            m1 = re.match(r'^yp\.layers\[(\d+)\]$', entity_path)
            m2 = re.match(r'^yp\.layers\[(\d+)\]\.channels\[(\d+)\]$', entity_path)

            bake_properties = dotdict()
            for attr in dir(bi):
                if attr.startswith('__'): continue
                if attr.startswith('bl_'): continue
                if attr in {'rna_type'}: continue
                try: bake_properties[attr] = getattr(bi, attr)
                except: pass

            bake_properties.update({
                'type': bi.bake_type,
                'target_type': 'LAYER' if m1 or m2 else 'MASK',
                'name': image.name,
                'width': image.size[0] if not segment else segment.width,
                'height': image.size[1] if not segment else segment.height,
                'uv_map': entity.uv_name if not entity.use_baked else entity.baked_uv_name
            })

            # 'baked_segment_name' meant the entity is baked as image
            if segment_name_prop == 'baked_segment_name':
                bake_entity_as_image(entity, bprops=bake_properties, set_image_to_entity=True)
            else: bake_to_entity(bprops=bake_properties, overwrite_img=image, segment=segment)

            baked_counts += 1

    print('INFO: Rebaking images is done at ', '{:0.2f}'.format(time.time() - tt), 'seconds!')

    return baked_counts

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

    print('INFO: Duplicating mesh(es) is done in', '{:0.2f}'.format(time.time() - tt), 'seconds!')
    return new_objs

def get_merged_mesh_objects(scene, objs, hide_original=False, disable_problematic_modifiers=True):

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
        problematic_modifiers = get_problematic_modifiers(obj) if disable_problematic_modifiers else []

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
        # This is needed since it always produce 3D vector in Blender 3.5
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

    print('INFO: Merging mesh(es) is done in', '{:0.2f}'.format(time.time() - tt), 'seconds!')
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
    bpy.ops.object.mode_set(mode='OBJECT')
    plane_obj = create_plane_on_object_mode()

    prepare_bake_settings(book, [plane_obj], samples=samples, margin=margin, bake_device=bake_device)

    mat = bpy.data.materials.new('__TEMP__')
    mat.use_nodes = True
    plane_obj.active_material = mat

    output = get_material_output(mat, create_one=True)
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
                width, height, image.yia.color, image.is_float, yp=yp
            )
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
            scaled_img = bpy.data.images.new(
                name='__TEMP__', width=width, height=height,
                alpha=True, float_buffer=image.is_float
            )
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
            alpha_img = bpy.data.images.new(
                name='__TEMP_ALPHA__', width=width, height=height,
                alpha=True, float_buffer=image.is_float
            )
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

    # Remove temp data
    if straight_over.node_tree.users == 1:
        remove_datablock(bpy.data.node_groups, straight_over.node_tree, user=straight_over, user_prop='node_tree')
    remove_datablock(bpy.data.materials, mat)
    remove_mesh_obj(plane_obj)

    # Recover settings
    recover_bake_settings(book)

    # Recover original active layer collection
    if is_bl_newer_than(2, 80):
        bpy.context.view_layer.active_layer_collection = ori_layer_collection

    print('RESIZE IMAGE:', image_name, 'Resize image is done in', '{:0.2f}'.format(time.time() - T), 'seconds!')

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
        output = get_material_output(mat, create_one=True)
        emi = mat.node_tree.nodes.new('ShaderNodeEmission')
        mat.node_tree.links.new(emi.outputs[0], output.inputs[0])

    return mat

def remove_temp_emit_white_mat():
    mat = bpy.data.materials.get(TEMP_EMIT_WHITE)
    if mat: 
        remove_datablock(bpy.data.materials, mat)

def get_output_uv_names_from_geometry_nodes(obj):
    if not is_bl_newer_than(3, 5): return []

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
        name = 'Bake Device',
        description = 'Device to use for baking',
        items = (
            ('GPU', 'GPU Compute', ''),
            ('CPU', 'CPU', '')
        ),
        default = 'CPU'
    )
    
    samples : IntProperty(
        name = 'Bake Samples', 
        description = 'Bake Samples, more means less jagged on generated textures', 
        default=1, min=1
    )

    margin : IntProperty(
        name = 'Bake Margin',
        description = 'Bake margin in pixels',
        default = 5,
        subtype = 'PIXEL'
    )

    margin_type : EnumProperty(
        name = 'Margin Type',
        description = '',
        items = (
            ('ADJACENT_FACES', 'Adjacent Faces', 'Use pixels from adjacent faces across UV seams.'),
            ('EXTEND', 'Extend', 'Extend border pixels outwards')
        ),
        default = 'ADJACENT_FACES'
    )

    width : IntProperty(name='Width', default=1024, min=1, max=16384)
    height : IntProperty(name='Height', default=1024, min=1, max=16384)

    image_resolution : EnumProperty(
        name = 'Image Resolution',
        items = image_resolution_items,
        default = '1024'
    )
    
    use_custom_resolution : BoolProperty(
        name = 'Custom Resolution',
        description = 'Use custom Resolution to adjust the width and height individually',
        default = False
    )

    def invoke_operator(self, context):
        ypup = get_user_preferences()

        # Set up default bake device
        if ypup.default_bake_device != 'DEFAULT':
            self.bake_device = ypup.default_bake_device

        # Use user preference default image size
        if ypup.default_image_resolution == 'CUSTOM':
            self.use_custom_resolution = True
            self.width = self.height = ypup.default_new_image_size
        elif ypup.default_image_resolution != 'DEFAULT':
            self.image_resolution = ypup.default_image_resolution

    def check_operator(self, context):
        if not self.use_custom_resolution:
            self.height = self.width = int(self.image_resolution)

    def is_cycles_exist(self, context):
        if not hasattr(context.scene, 'cycles'):
            self.report({'ERROR'}, "Cycles Render Engine need to be enabled in user preferences!")
            return False
        return True
