import bpy, time
from .common import *
from .node_connections import *
from . import lib, Layer, ImageAtlas

BL28_HACK = True

problematic_modifiers = {
        'MIRROR',
        'SOLIDIFY',
        'ARRAY',
        }

def remember_before_bake(yp=None):
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
    if hasattr(scene.render, 'tile_x'):
        book['ori_tile_x'] = scene.render.tile_x
        book['ori_tile_y'] = scene.render.tile_y
    book['ori_use_selected_to_active'] = scene.render.bake.use_selected_to_active
    if is_greater_than_280():
        book['ori_max_ray_distance'] = scene.render.bake.max_ray_distance
    book['ori_cage_extrusion'] = scene.render.bake.cage_extrusion
    book['ori_use_cage'] = scene.render.bake.use_cage

    if hasattr(scene.cycles, 'use_denoising'):
        book['ori_use_denoising'] = scene.cycles.use_denoising

    if hasattr(scene.render.bake, 'target'):
        book['ori_bake_target'] = scene.render.bake.target

    if is_greater_than_280():
        book['ori_material_override'] = bpy.context.view_layer.material_override
    else: book['ori_material_override'] = scene.render.layers.active.material_override

    # Multires related
    book['ori_use_bake_multires'] = scene.render.use_bake_multires
    book['ori_use_bake_clear'] = scene.render.use_bake_clear
    book['ori_render_bake_type'] = scene.render.bake_type
    book['ori_bake_margin'] = scene.render.bake_margin

    if is_greater_than_281() and not is_greater_than_300() and scene.cycles.device == 'GPU' and 'compute_device_type' in bpy.context.preferences.addons['cycles'].preferences:
        book['compute_device_type'] = bpy.context.preferences.addons['cycles'].preferences['compute_device_type']

    # Remember uv
    book['ori_active_uv'] = uv_layers.active.name
    active_render_uvs = [u for u in uv_layers if u.active_render]
    if active_render_uvs:
        book['ori_active_render_uv'] = active_render_uvs[0].name

    # Remember scene objects
    if is_greater_than_280():
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

    # Remember world settings
    if is_greater_than_280() and scene.world:
        book['ori_distance'] = scene.world.light_settings.distance

    # Remember ypui
    #book['ori_disable_temp_uv'] = ypui.disable_auto_temp_uv_update

    # Remember yp
    if yp:
        book['parallax_ch'] = get_root_parallax_channel(yp)
    else: book['parallax_ch'] = None

    return book

def prepare_bake_settings(book, objs, yp=None, samples=1, margin=5, uv_map='', bake_type='EMIT', 
        disable_problematic_modifiers=False, force_use_cpu=False, hide_other_objs=True, bake_from_multires=False, 
        tile_x=64, tile_y=64, use_selected_to_active=False, max_ray_distance=0.0, cage_extrusion=0.0,
        bake_target = 'IMAGE_TEXTURES',
        source_objs=[]):

    #scene = self.scene
    scene = bpy.context.scene
    #obj = bpy.context.object
    ypui = bpy.context.window_manager.ypui

    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.render.threads_mode = 'AUTO'
    scene.render.bake.margin = margin
    #scene.render.bake.use_clear = True
    scene.render.bake.use_clear = False
    scene.render.bake.use_selected_to_active = use_selected_to_active
    if is_greater_than_280():
        scene.render.bake.max_ray_distance = max_ray_distance
    scene.render.bake.cage_extrusion = cage_extrusion
    scene.render.bake.use_cage = False
    scene.render.use_simplify = False
    if hasattr(scene.render, 'tile_x'):
        scene.render.tile_x = tile_x
        scene.render.tile_y = tile_y

    if hasattr(scene.cycles, 'use_denoising'):
        scene.cycles.use_denoising = False

    if hasattr(scene.render.bake, 'target'):
        scene.render.bake.target = bake_target

    if is_greater_than_280():
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

    # Use CPU if being forced
    if force_use_cpu:
        scene.cycles.device = 'CPU'
    # Use CUDA bake if Optix is selected
    elif (is_greater_than_281() and not is_greater_than_300() and 'compute_device_type' in bpy.context.preferences.addons['cycles'].preferences and
            bpy.context.preferences.addons['cycles'].preferences['compute_device_type'] == 3):
        #scene.cycles.device = 'CPU'
        bpy.context.preferences.addons['cycles'].preferences['compute_device_type'] = 1

    if bake_type == 'NORMAL':
        scene.render.bake.normal_space = 'TANGENT'

    # Disable other object selections and select only active object
    if is_greater_than_280():

        # Disable exclude only works on source objects
        for o in source_objs:
            layer_cols = get_object_parent_layer_collections([], bpy.context.view_layer.layer_collection, o)
            for lc in layer_cols:
                lc.exclude = False

        # Show viewport and render of object layer collection
        for o in objs:
            o.hide_render = False
            o.hide_viewport = False
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
            obj.select_set(True)
            #print(obj.name, obj.hide_render, obj.select_get())

        # Disable material override
        book['material_override'] = bpy.context.view_layer.material_override
        bpy.context.view_layer.material_override = None

    else:

        for obj in objs:
            obj.hide_render = False
            obj.hide = False

        if hide_other_objs:
            for o in scene.objects:
                if o not in objs:
                    o.hide_render = True

        for o in scene.objects:
            o.select = False

        for obj in objs:
            obj.hide_select = False
            obj.select = True

    if disable_problematic_modifiers:
        book['disabled_mods'] = []
        book['disabled_viewport_mods'] = []
        for obj in objs:
            for mod in obj.modifiers:

                if mod.show_render and mod.type in problematic_modifiers: #{'MIRROR', 'SOLIDIFY'}:
                    mod.show_render = False
                    book['disabled_mods'].append(mod)

                if mod.show_viewport and mod.type in problematic_modifiers: #{'MIRROR', 'SOLIDIFY'}:
                    mod.show_viewport = False
                    book['disabled_viewport_mods'].append(mod)

    # Set active uv layers
    if uv_map != '':
        for obj in objs:
            #set_active_uv_layer(obj, uv_map)
            uv_layers = get_uv_layers(obj)
            uv = uv_layers.get(uv_map)
            if uv: 
                uv_layers.active = uv
                uv.active_render = True

    # Disable auto temp uv update
    #ypui.disable_auto_temp_uv_update = True

    # Set to object mode
    try: bpy.ops.object.mode_set(mode = 'OBJECT')
    except: pass

    # Disable parallax channel
    #parallax_ch = get_root_parallax_channel(yp)
    if book['parallax_ch']:
        book['parallax_ch'].enable_parallax = False

def recover_bake_settings(book, yp=None, recover_active_uv=False):
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
    if hasattr(scene.render, 'tile_x'):
        scene.render.tile_x = book['ori_tile_x']
        scene.render.tile_y = book['ori_tile_y']
    if hasattr(scene.cycles, 'use_denoising'):
        scene.cycles.use_denoising = book['ori_use_denoising']
    if hasattr(scene.render.bake, 'target'):
        scene.render.bake.target = book['ori_bake_target']
    scene.render.bake.use_selected_to_active = book['ori_use_selected_to_active']
    if is_greater_than_280():
        scene.render.bake.max_ray_distance = book['ori_max_ray_distance']
    scene.render.bake.cage_extrusion = book['ori_cage_extrusion']
    scene.render.bake.use_cage = book['ori_use_cage']

    if is_greater_than_280():
        bpy.context.view_layer.material_override = book['ori_material_override']
    else: scene.render.layers.active.material_override = book['ori_material_override']

    # Multires related
    scene.render.use_bake_multires = book['ori_use_bake_multires']
    scene.render.use_bake_clear = book['ori_use_bake_clear']
    scene.render.bake_type = book['ori_render_bake_type']
    scene.render.bake_margin = book['ori_bake_margin']

    if 'compute_device_type' in book:
        bpy.context.preferences.addons['cycles'].preferences['compute_device_type'] = book['compute_device_type']

    if is_greater_than_280() and 'material_override' in book:
        bpy.context.view_layer.material_override = book['material_override']

    # Recover world settings
    if is_greater_than_280() and scene.world:
        scene.world.light_settings.distance = book['ori_distance']

    # Recover uv
    if recover_active_uv:
        uvl = uv_layers.get(book['ori_active_uv'])
        if uvl: uv_layers.active = uvl
        if 'ori_active_render_uv' in book:
            uvl = uv_layers.get(book['ori_active_render_uv'])
            if uvl: uvl.active_render = True

    #return

    # Recover active object and mode
    if is_greater_than_280():
        bpy.context.view_layer.objects.active = obj
    else: scene.objects.active = obj
    bpy.ops.object.mode_set(mode = book['mode'])

    # Disable other object selections
    if is_greater_than_280():

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

        #for o in scene.objects:
        for o in bpy.context.view_layer.objects:
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

    # Recover active object

    # Recover ypui
    #ypui.disable_auto_temp_uv_update = book['ori_disable_temp_uv']

    # Recover parallax
    if book['parallax_ch']:
        book['parallax_ch'].enable_parallax = True

    # Recover modifiers
    if 'disabled_mods' in book:
        for mod in book['disabled_mods']:
            mod.show_render = True

    if 'disabled_viewport_mods' in book:
        for mod in book['disabled_viewport_mods']:
            mod.show_viewport = True

def fxaa_image(image, alpha_aware=True, force_use_cpu=False):
    T = time.time()
    print('FXAA: Doing FXAA pass on', image.name + '...')
    book = remember_before_bake()

    width = image.size[0]
    height = image.size[1]

    # Copy image
    pixels = list(image.pixels)
    image_copy = image.copy()
    image_copy.pixels = pixels

    # Set active collection to be root collection
    if is_greater_than_280():
        ori_layer_collection = bpy.context.view_layer.active_layer_collection
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection

    # Create new plane
    bpy.ops.object.mode_set(mode = 'OBJECT')
    bpy.ops.mesh.primitive_plane_add(calc_uvs=True)
    if is_greater_than_280():
        plane_obj = bpy.context.view_layer.objects.active
    else: plane_obj = bpy.context.scene.objects.active

    prepare_bake_settings(book, [plane_obj], samples=1, margin=0, force_use_cpu=force_use_cpu)

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

    # Straight over won't work if using fxaa nodes, need another bake pass
    if alpha_aware:
        uv_map = mat.node_tree.nodes.new('ShaderNodeUVMap')
        uv_map.uv_map = 'UVMap'
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
        bpy.ops.object.bake()

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
    fxaa_uv_map.uv_map = 'UVMap'
    tex.image = image_copy
    if not is_greater_than_280() :
        if image.colorspace_settings.name == 'sRGB':
            tex.color_space = 'COLOR'
        else: tex.color_space = 'NONE'

    # Connect nodes again
    mat.node_tree.links.new(fxaa.outputs[0], emi.inputs[0])
    mat.node_tree.links.new(emi.outputs[0], output.inputs[0])

    print('FXAA: Baking FXAA on', image.name + '...')
    #return
    bpy.ops.object.bake()

    # Copy original alpha to baked image
    if alpha_aware:
        print('FXAA: Copying original alpha to FXAA result of', image.name + '...')
        target_pxs = list(image.pixels)
        start_x = 0
        start_y = 0

        for y in range(height):
            temp_offset_y = width * 4 * y
            offset_y = width * 4 * (y + start_y)
            for x in range(width):
                temp_offset_x = 4 * x
                offset_x = 4 * (x + start_x)
                target_pxs[offset_y + offset_x + 3] = pixels[temp_offset_y + temp_offset_x + 3]

        image.pixels = target_pxs

    # Remove temp datas
    print('FXAA: Removing temporary data of FXAA pass')
    if alpha_aware:
        if straight_over.node_tree.users == 1:
            bpy.data.node_groups.remove(straight_over.node_tree)

    if fxaa.node_tree.users == 1:
        bpy.data.node_groups.remove(tex_node.node_tree)
        bpy.data.node_groups.remove(fxaa.node_tree)

    bpy.data.images.remove(image_copy)
    bpy.data.materials.remove(mat)
    plane = plane_obj.data
    bpy.ops.object.delete()
    bpy.data.meshes.remove(plane)

    # Recover settings
    recover_bake_settings(book)

    # Recover original active layer collection
    if is_greater_than_280():
        bpy.context.view_layer.active_layer_collection = ori_layer_collection

    print('FXAA:', image.name, 'FXAA pass is done at', '{:0.2f}'.format(time.time() - T), 'seconds!')

    return image

def bake_to_vcol(mat, node, root_ch, extra_channel=None, extra_multiplier=1.0):

    # Create setup nodes
    emit = mat.node_tree.nodes.new('ShaderNodeEmission')

    if root_ch.type == 'NORMAL':

        norm = mat.node_tree.nodes.new('ShaderNodeGroup')
        norm.node_tree = get_node_tree_lib(lib.BAKE_NORMAL_ACTIVE_UV)

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
        mul = mat.node_tree.nodes.new('ShaderNodeMixRGB')
        mul.inputs[0].default_value = 1.0
        mul.inputs[2].default_value = (extra_multiplier, extra_multiplier, extra_multiplier, 1.0)
        mul.blend_type = 'MULTIPLY'

        extra_rgb = node.outputs[extra_channel.name]
        extra_rgb = create_link(mat.node_tree, extra_rgb, mul.inputs[1])[0]

        add = mat.node_tree.nodes.new('ShaderNodeMixRGB')
        add.inputs[0].default_value = 1.0
        add.blend_type = 'ADD'

        rgb = create_link(mat.node_tree, rgb, add.inputs[1])[0]
        create_link(mat.node_tree, extra_rgb, add.inputs[2])

    mat.node_tree.links.new(rgb, emit.inputs[0])

    # Bake!
    bpy.ops.object.bake()

    # Remove temp nodes
    simple_remove_node(mat.node_tree, emit)
    if root_ch.type == 'NORMAL':
        simple_remove_node(mat.node_tree, norm)

    if extra_channel:
        simple_remove_node(mat.node_tree, mul)
        simple_remove_node(mat.node_tree, add)

    # Recover original bsdf
    mat.node_tree.links.new(ori_bsdf, output.inputs[0])

def bake_channel(uv_map, mat, node, root_ch, width=1024, height=1024, target_layer=None, use_hdr=False, aa_level=1):

    print('BAKE CHANNEL: Baking', root_ch.name + ' channel...')

    tree = node.node_tree
    yp = tree.yp

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
        else:
            img_name = source.image.name
            img = source.image.copy()
            img.name = img_name

        ch = target_layer.channels[get_channel_index(root_ch)]

    # Create setup nodes
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    emit = mat.node_tree.nodes.new('ShaderNodeEmission')

    if root_ch.type == 'NORMAL':

        norm = mat.node_tree.nodes.new('ShaderNodeGroup')
        norm.node_tree = get_node_tree_lib(lib.BAKE_NORMAL_ACTIVE_UV)

    # Set tex as active node
    mat.node_tree.nodes.active = tex

    # Get output node and remember original bsdf input
    output = get_active_mat_output_node(mat.node_tree)
    ori_bsdf = output.inputs[0].links[0].from_socket

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
        filepath = img.filepath

    if not target_layer:
        # Set nodes
        baked = tree.nodes.get(root_ch.baked)
        if not baked:
            baked = new_node(tree, root_ch, 'baked', 'ShaderNodeTexImage', 'Baked ' + root_ch.name)
        if hasattr(baked, 'color_space'):
            if root_ch.colorspace == 'LINEAR' or root_ch.type == 'NORMAL':
                baked.color_space = 'NONE'
            else: baked.color_space = 'COLOR'
        
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
            filepath = baked.image.filepath
            baked.image.name = '____TEMP'
            #if baked.image.users == 1:
            #    bpy.data.images.remove(baked.image)

    if not img:

        if segment:
            width = segment.width
            height = segment.height

        #Create new image
        img = bpy.data.images.new(name=img_name,
                width=width, height=height, alpha=True) #, alpha=True, float_buffer=hdr)
        img.generated_type = 'BLANK'

        if hasattr(img, 'use_alpha'):
            img.use_alpha = True

        if segment:
            if source.image.yia.color == 'WHITE':
                img.generated_color = (1.0, 1.0, 1.0, 1.0)
            elif source.image.yia.color == 'BLACK':
                img.generated_color = (0.0, 0.0, 0.0, 1.0)
            else: img.generated_color = (0.0, 0.0, 0.0, 0.0)

        elif root_ch.type == 'NORMAL':
            img.generated_color = (0.5, 0.5, 1.0, 1.0)

        elif root_ch.type == 'VALUE':
            val = node.inputs[root_ch.name].default_value
            img.generated_color = (val, val, val, 1.0)

        elif root_ch.enable_alpha:
            img.generated_color = (0.0, 0.0, 0.0, 1.0)

        else:
            col = node.inputs[root_ch.name].default_value
            col = Color((col[0], col[1], col[2]))
            col = linear_to_srgb(col)
            img.generated_color = (col.r, col.g, col.b, 1.0)

        # Set filepath
        if filepath != '':
            img.filepath = filepath

        # Use hdr if not baking normal
        if root_ch.type != 'NORMAL' and use_hdr:
            img.use_generated_float = True
            img.colorspace_settings.name = 'Linear'

        # Set colorspace to linear
        if root_ch.colorspace == 'LINEAR' or root_ch.type == 'NORMAL':
            img.colorspace_settings.name = 'Linear'

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

        #if root_ch.type == 'NORMAL':
        #    return

        # Bake!
        print('BAKE CHANNEL: Baking main image of ' + root_ch.name + ' channel...')
        bpy.ops.object.bake()

    # Bake displacement
    if root_ch.type == 'NORMAL': # and root_ch.enable_parallax:

        if not target_layer:

            ### Normal overlay only
            if is_overlay_normal_empty(yp):
                # Remove baked_normal_overlay
                remove_node(tree, root_ch, 'baked_normal_overlay')
            else:

                baked_normal_overlay = tree.nodes.get(root_ch.baked_normal_overlay)
                if not baked_normal_overlay:
                    baked_normal_overlay = new_node(tree, root_ch, 'baked_normal_overlay', 'ShaderNodeTexImage', 
                            'Baked ' + root_ch.name + ' Overlay Only')
                    if hasattr(baked_normal_overlay, 'color_space'):
                        baked_normal_overlay.color_space = 'NONE'

                if baked_normal_overlay.image:
                    norm_img_name = baked_normal_overlay.image.name
                    filepath = baked_normal_overlay.image.filepath
                    baked_normal_overlay.image.name = '____NORM_TEMP'
                else:
                    norm_img_name = tree.name + ' ' + root_ch.name + ' Overlay Only'
                # Create target image
                norm_img = bpy.data.images.new(name=norm_img_name, width=width, height=height) 
                norm_img.generated_color = (0.5, 0.5, 1.0, 1.0)
                norm_img.colorspace_settings.name = 'Linear'
                norm_img.filepath = filepath

                tex.image = norm_img

                # Bake setup (doing little bit doing hacky reconnection here)
                end = tree.nodes.get(TREE_END)
                ori_soc = end.inputs[root_ch.name].links[0].from_socket
                end_linear = tree.nodes.get(root_ch.end_linear)
                soc = end_linear.inputs['Normal Overlay'].links[0].from_socket
                create_link(tree, soc, end.inputs[root_ch.name])
                #create_link(mat.node_tree, node.outputs[root_ch.name], emit.inputs[0])

                # Bake
                print('BAKE CHANNEL: Baking normal overlay image of ' + root_ch.name + ' channel...')
                bpy.ops.object.bake()

                #return

                # Recover connection
                create_link(tree, ori_soc, end.inputs[root_ch.name])

                # Set baked normal overlay image
                if baked_normal_overlay.image:
                    temp = baked_normal_overlay.image
                    img_users = get_all_image_users(baked_normal_overlay.image)
                    for user in img_users:
                        user.image = norm_img
                    bpy.data.images.remove(temp)
                else:
                    baked_normal_overlay.image = norm_img

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
                baked_disp.image.name = '____DISP_TEMP'
            else:
                disp_img_name = tree.name + ' ' + root_ch.name + ' Displacement'

            disp_img = bpy.data.images.new(name=disp_img_name, width=width, height=height) 
            disp_img.generated_color = (0.5, 0.5, 0.5, 1.0)
            disp_img.colorspace_settings.name = 'Linear'
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
            bpy.ops.object.bake()

            if not target_layer:

                # Set baked displacement image
                if baked_disp.image:
                    temp = baked_disp.image
                    img_users = get_all_image_users(baked_disp.image)
                    for user in img_users:
                        user.image = disp_img
                    bpy.data.images.remove(temp)
                else:
                    baked_disp.image = disp_img

            if spread_height:
                simple_remove_node(mat.node_tree, spread_height)

    # Bake alpha
    #if root_ch.type != 'NORMAL' and root_ch.enable_alpha:
    if root_ch.enable_alpha:
        # Create temp image
        alpha_img = bpy.data.images.new(name='__TEMP__', width=width, height=height) 
        alpha_img.colorspace_settings.name = 'Linear'
        create_link(mat.node_tree, node.outputs[root_ch.name + io_suffix['ALPHA']], emit.inputs[0])

        tex.image = alpha_img

        #return

        # Bake
        print('BAKE CHANNEL: Baking alpha of ' + root_ch.name + ' channel...')
        bpy.ops.object.bake()

        # Copy alpha pixels to main image alpha channel
        img_pxs = list(img.pixels)
        alp_pxs = list(alpha_img.pixels)

        for y in range(height):
            offset_y = width * 4 * y
            for x in range(width):
                a = alp_pxs[offset_y + (x*4)]
                #a = srgb_to_linear_per_element(a)
                img_pxs[offset_y + (x*4) + 3] = a

        img.pixels = img_pxs

        #return

        # Remove temp image
        bpy.data.images.remove(alpha_img)

    if not target_layer:
        # Set image to baked node and replace all previously original users
        if baked.image:
            temp = baked.image
            img_users = get_all_image_users(baked.image)
            for user in img_users:
                user.image = img
            bpy.data.images.remove(temp)
        else:
            baked.image = img

    simple_remove_node(mat.node_tree, tex)
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
            start_x = width * segment.tile_x
            start_y = height * segment.tile_y

            target_pxs = list(ori_img.pixels)
            temp_pxs = list(img.pixels)

            for y in range(height):
                temp_offset_y = width * 4 * y
                offset_y = ori_img.size[0] * 4 * (y + start_y)
                for x in range(width):
                    temp_offset_x = 4 * x
                    offset_x = 4 * (x + start_x)
                    for i in range(4):
                        target_pxs[offset_y + offset_x + i] = temp_pxs[temp_offset_y + temp_offset_x + i]

            ori_img.pixels = target_pxs

            # Remove temp image
            bpy.data.images.remove(img)
        else:
            source.image = img

            if ori_img.users == 0:
                bpy.data.images.remove(ori_img)

        return True

def temp_bake(context, entity, width, height, hdr, samples, margin, uv_map, force_use_cpu=False):

    m1 = re.match(r'yp\.layers\[(\d+)\]$', entity.path_from_id())
    m2 = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]$', entity.path_from_id())

    if not m1 and not m2: return

    yp = entity.id_data.yp
    obj = context.object
    #scene = context.scene

    # Prepare bake settings
    book = remember_before_bake(yp)
    prepare_bake_settings(book, [obj], yp, samples, margin, uv_map, force_use_cpu=force_use_cpu)

    mat = get_active_material()
    name = entity.name + ' Temp'

    # New target image
    image = bpy.data.images.new(name=name,
            width=width, height=height, alpha=True, float_buffer=hdr)
    image.colorspace_settings.name = 'Linear'

    if entity.type == 'HEMI':

        if m1: source = get_layer_source(entity)
        else: source = get_mask_source(entity)

        # Create bake nodes
        source_copy = mat.node_tree.nodes.new(source.bl_idname)
        source_copy.node_tree = source.node_tree

        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        emit = mat.node_tree.nodes.new('ShaderNodeEmission')
        output = get_active_mat_output_node(mat.node_tree)
        ori_bsdf = output.inputs[0].links[0].from_socket

        # Connect emit to output material
        mat.node_tree.links.new(emit.outputs[0], output.inputs[0])
        mat.node_tree.links.new(source_copy.outputs[0], output.inputs[0])

        # Set active texture
        tex.image = image
        mat.node_tree.nodes.active = tex

        # Bake
        bpy.ops.object.bake()

        # Recover link
        mat.node_tree.links.new(ori_bsdf, output.inputs[0])

        # Remove temp nodes
        mat.node_tree.nodes.remove(tex)
        simple_remove_node(mat.node_tree, emit)
        simple_remove_node(mat.node_tree, source_copy)

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

def copy_and_join_objects(objs):

    temp_objs = []
    for obj in objs:
        temp_obj = obj.copy()
        link_object(bpy.context.scene, temp_obj)
        temp_obj.data = temp_obj.data.copy()
        temp_objs.append(temp_obj)

    return join_objects(temp_objs)

def join_objects(objs):

    if len(objs) == 0: return None

    objs = [o for o in objs if o.type == 'MESH']

    # Deselect all objects
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')

    max_levels = -1
    hi_obj = None
    for obj in objs:

        set_object_select(obj, True)

        for mod in obj.modifiers:

            # Disable all problematic modifiers
            if mod.type in problematic_modifiers:
                mod.show_render = False
                mod.show_viewport = False

            # Check who has highest multires if available
            if mod.type == 'MULTIRES':
                if mod.render_levels > max_levels:
                    max_levels = mod.render_levels
                    hi_obj = obj

    # Check who has highest subsurf if multires modifier is not found
    if not hi_obj:
        for obj in objs:
            if mod.type == 'SUBSURF':
                if mod.levels > max_levels:
                    max_levels = mod.levels
                    hi_obj = obj

    if not hi_obj: hi_obj = objs[0]

    # Set active object
    set_active_object(hi_obj)
    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.join()

    return bpy.context.object

def resize_image(image, width, height, colorspace='Linear', samples=1, margin=0, segment=None, alpha_aware=True, force_use_cpu=False, yp=None):

    T = time.time()
    image_name = image.name
    print('RESIZE IMAGE: Doing resize image pass on', image_name + '...')

    book = remember_before_bake()

    if segment:
        ori_width = segment.width
        ori_height = segment.height
    else:
        ori_width = image.size[0]
        ori_height = image.size[1]

    if ori_width == width and ori_height == height:
        return

    if segment:
        new_segment = ImageAtlas.get_set_image_atlas_segment(
                    width, height, image.yia.color, image.is_float, yp=yp) #, ypup.image_atlas_size)
        scaled_img = new_segment.id_data

        ori_start_x = segment.width * segment.tile_x
        ori_start_y = segment.height * segment.tile_y

        start_x = width * new_segment.tile_x
        start_y = height * new_segment.tile_y
    else:
        scaled_img = bpy.data.images.new(name='__TEMP__', 
            width=width, height=height, alpha=True, float_buffer=image.is_float)
        scaled_img.colorspace_settings.name = colorspace
        if image.filepath != '' and not image.packed_file:
            scaled_img.filepath = image.filepath

        start_x = 0
        start_y = 0

        new_segment = None

    # Set active collection to be root collection
    if is_greater_than_280():
        ori_layer_collection = bpy.context.view_layer.active_layer_collection
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection

    # Create new plane
    bpy.ops.object.mode_set(mode = 'OBJECT')
    bpy.ops.mesh.primitive_plane_add(calc_uvs=True)
    if is_greater_than_280():
        plane_obj = bpy.context.view_layer.objects.active
    else: plane_obj = bpy.context.scene.objects.active

    prepare_bake_settings(book, [plane_obj], samples=samples, margin=margin, force_use_cpu=force_use_cpu)

    # If using image atlas, transform uv
    if segment:
        uv_layers = get_uv_layers(plane_obj)

        # Transform current uv using previous segment
        #uv_layer = uv_layers.active
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

    #return{'FINISHED'}

    mat = bpy.data.materials.new('__TEMP__')
    mat.use_nodes = True
    plane_obj.active_material = mat

    output = get_active_mat_output_node(mat.node_tree)
    emi = mat.node_tree.nodes.new('ShaderNodeEmission')
    uv_map = mat.node_tree.nodes.new('ShaderNodeUVMap')
    uv_map.uv_map = 'UVMap'
    target_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    target_tex.image = scaled_img
    source_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    source_tex.image = image

    if not is_greater_than_280() :
        if image.colorspace_settings.name == 'sRGB':
            source_tex.color_space = 'COLOR'
        else: source_tex.color_space = 'NONE'

    straight_over = mat.node_tree.nodes.new('ShaderNodeGroup')
    straight_over.node_tree = get_node_tree_lib(lib.STRAIGHT_OVER)
    straight_over.inputs[1].default_value = 0.0

    # Connect nodes
    mat.node_tree.links.new(uv_map.outputs[0], source_tex.inputs[0])
    mat.node_tree.links.new(source_tex.outputs[0], straight_over.inputs[2])
    mat.node_tree.links.new(source_tex.outputs[1], straight_over.inputs[3])
    mat.node_tree.links.new(straight_over.outputs[0], emi.inputs[0])
    mat.node_tree.links.new(emi.outputs[0], output.inputs[0])
    mat.node_tree.nodes.active = target_tex

    # Bake
    print('RESIZE IMAGE: Baking resized image on', image_name + '...')
    bpy.ops.object.bake()

    if alpha_aware:

        # Create alpha image as bake target
        alpha_img = bpy.data.images.new(name='__TEMP_ALPHA__',
                width=width, height=height, alpha=True, float_buffer=image.is_float)
        alpha_img.colorspace_settings.name = 'Linear'

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
        bpy.ops.object.bake()

        # Copy alpha image to scaled image
        target_pxs = list(scaled_img.pixels)
        temp_pxs = list(alpha_img.pixels)

        for y in range(height):
            temp_offset_y = width * 4 * y
            offset_y = scaled_img.size[0] * 4 * (y + start_y)
            for x in range(width):
                temp_offset_x = 4 * x
                offset_x = 4 * (x + start_x)
                target_pxs[offset_y + offset_x + 3] = temp_pxs[temp_offset_y + temp_offset_x]

        scaled_img.pixels = target_pxs

        # Remove alpha image
        bpy.data.images.remove(alpha_img)

    # Replace original image to scaled image
    if not new_segment:
        replace_image(image, scaled_img)

    # Remove temp datas
    if straight_over.node_tree.users == 1:
        bpy.data.node_groups.remove(straight_over.node_tree)
    bpy.data.materials.remove(mat)
    plane = plane_obj.data
    bpy.ops.object.delete()
    bpy.data.meshes.remove(plane)

    # Recover settings
    recover_bake_settings(book)

    # Recover original active layer collection
    if is_greater_than_280():
        bpy.context.view_layer.active_layer_collection = ori_layer_collection

    print('RESIZE IMAGE:', image_name, 'Resize image is done at', '{:0.2f}'.format(time.time() - T), 'seconds!')

    return scaled_img, new_segment

TEMP_EMIT_WHITE = '__EMIT_WHITE__'

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
    if mat: bpy.data.materials.remove(mat)

