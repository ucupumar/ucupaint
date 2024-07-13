import bpy, numpy, time
from . import lib
from .common import *
from .bake_common import *
from .vector_displacement_lib import *
from .input_outputs import *

TEMP_MULTIRES_NAME = '_YP_TEMP_MULTIRES'
TEMP_TANGENT_IMAGE_SUFFIX = '_YP_TEMP_TANGENT'
TEMP_BITANGENT_IMAGE_SUFFIX = '_YP_TEMP_BITANGENT'
TEMP_COMBINED_VDM_IMAGE_SUFFIX = '_YP_TEMP_COMBINED_VDM'
TEMP_LAYER_DISABLED_VDM_IMAGE_SUFFIX = '_YP_LAYER_DISABLED_VDM'

def _remember_before_bake(obj):
    book = {}
    book['scene'] = scene = bpy.context.scene
    book['obj'] = obj
    book['mode'] = obj.mode
    uv_layers = obj.data.uv_layers
    ypui = bpy.context.window_manager.ypui

    # Remember render settings
    book['ori_engine'] = scene.render.engine
    book['ori_bake_type'] = scene.cycles.bake_type
    book['ori_samples'] = scene.cycles.samples
    book['ori_threads_mode'] = scene.render.threads_mode
    book['ori_margin'] = scene.render.bake.margin
    book['ori_margin_type'] = scene.render.bake.margin_type
    book['ori_use_clear'] = scene.render.bake.use_clear
    book['ori_normal_space'] = scene.render.bake.normal_space
    book['ori_simplify'] = scene.render.use_simplify
    book['ori_device'] = scene.cycles.device
    book['ori_use_selected_to_active'] = scene.render.bake.use_selected_to_active
    book['ori_max_ray_distance'] = scene.render.bake.max_ray_distance
    book['ori_cage_extrusion'] = scene.render.bake.cage_extrusion
    book['ori_use_cage'] = scene.render.bake.use_cage
    book['ori_use_denoising'] = scene.cycles.use_denoising
    book['ori_bake_target'] = scene.render.bake.target
    book['ori_material_override'] = bpy.context.view_layer.material_override

    # Multires related
    book['ori_use_bake_multires'] = scene.render.use_bake_multires
    book['ori_use_bake_clear'] = scene.render.use_bake_clear
    book['ori_render_bake_type'] = scene.render.bake_type
    book['ori_bake_margin'] = scene.render.bake_margin

    # Remember world settings
    book['ori_distance'] = scene.world.light_settings.distance

    # Remember image editor images
    book['editor_images'] = [a.spaces[0].image for a in bpy.context.screen.areas if a.type == 'IMAGE_EDITOR']
    book['editor_pins'] = [a.spaces[0].use_image_pin for a in bpy.context.screen.areas if a.type == 'IMAGE_EDITOR']

    # Remember uv
    book['ori_active_uv'] = uv_layers.active.name
    active_render_uvs = [u for u in uv_layers if u.active_render]
    if active_render_uvs:
        book['ori_active_render_uv'] = active_render_uvs[0].name

    return book

def _prepare_bake_settings(book, obj, uv_map='', samples=1, margin=15, bake_device='CPU'):

    scene = bpy.context.scene
    ypui = bpy.context.window_manager.ypui

    scene.render.engine = 'CYCLES'
    scene.render.threads_mode = 'AUTO'
    scene.render.bake.margin = margin
    scene.render.bake.margin_type = 'EXTEND'
    scene.render.bake.use_clear = False
    scene.render.bake.use_selected_to_active = False
    scene.render.bake.max_ray_distance = 0.0
    scene.render.bake.cage_extrusion = 0.0
    scene.render.bake.use_cage = False
    scene.render.use_simplify = False
    scene.render.bake.target = 'IMAGE_TEXTURES'
    scene.render.use_bake_multires = False
    scene.render.bake_margin = margin
    scene.render.use_bake_clear = False
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.cycles.bake_type = 'EMIT'
    scene.cycles.device = bake_device
    bpy.context.view_layer.material_override = None

    # Show viewport and render of object layer collection
    obj.hide_select = False
    obj.hide_viewport = False
    obj.hide_render = False
    obj.hide_set(False)
    layer_cols = get_object_parent_layer_collections([], bpy.context.view_layer.layer_collection, obj)
    for lc in layer_cols:
        lc.hide_viewport = False
        lc.collection.hide_viewport = False
        lc.collection.hide_render = False

    # Set object to active
    bpy.context.view_layer.objects.active = obj
    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode = 'OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)

    # Set active uv layers
    if uv_map != '':
        uv_layers = obj.data.uv_layers
        uv = uv_layers.get(uv_map)
        if uv: 
            uv_layers.active = uv
            uv.active_render = True

def _recover_bake_settings(book, recover_active_uv=False):
    scene = book['scene']
    obj = book['obj']
    uv_layers = obj.data.uv_layers
    ypui = bpy.context.window_manager.ypui

    scene.render.engine = book['ori_engine']
    scene.cycles.samples = book['ori_samples']
    scene.cycles.bake_type = book['ori_bake_type']
    scene.render.threads_mode = book['ori_threads_mode']
    scene.render.bake.margin = book['ori_margin']
    scene.render.bake.margin_type = book['ori_margin_type']
    scene.render.bake.use_clear = book['ori_use_clear']
    scene.render.use_simplify = book['ori_simplify']
    scene.cycles.device = book['ori_device']
    scene.cycles.use_denoising = book['ori_use_denoising']
    scene.render.bake.target = book['ori_bake_target']
    scene.render.bake.use_selected_to_active = book['ori_use_selected_to_active']
    scene.render.bake.max_ray_distance = book['ori_max_ray_distance']
    scene.render.bake.cage_extrusion = book['ori_cage_extrusion']
    scene.render.bake.use_cage = book['ori_use_cage']
    bpy.context.view_layer.material_override = book['ori_material_override']

    # Multires related
    scene.render.use_bake_multires = book['ori_use_bake_multires']
    scene.render.use_bake_clear = book['ori_use_bake_clear']
    scene.render.bake_type = book['ori_render_bake_type']
    scene.render.bake_margin = book['ori_bake_margin']

    # Recover world settings
    scene.world.light_settings.distance = book['ori_distance']

    # Recover image editors
    for i, area in enumerate([a for a in bpy.context.screen.areas if a.type == 'IMAGE_EDITOR']):
        # Some image can be deleted after baking process so use try except
        try: area.spaces[0].image = book['editor_images'][i]
        except: area.spaces[0].image = None

        area.spaces[0].use_image_pin = book['editor_pins'][i]

    # Recover uv
    if recover_active_uv:
        uvl = uv_layers.get(book['ori_active_uv'])
        if uvl: uv_layers.active = uvl
        if 'ori_active_render_uv' in book:
            uvl = uv_layers.get(book['ori_active_render_uv'])
            if uvl: uvl.active_render = True

def get_offset_attributes(base, sclupted_mesh, layer_disabled_mesh=None, intensity=1.0):

    print('INFO: Getting offset attributes...')

    if len(base.data.vertices) != len(sclupted_mesh.data.vertices):
        return None, None

    # Get coordinates for each vertices
    base_arr = numpy.zeros(len(base.data.vertices)*3, dtype=numpy.float32)
    base.data.vertices.foreach_get('co', base_arr)

    sculpted_arr = numpy.zeros(len(sclupted_mesh.data.vertices)*3, dtype=numpy.float32)
    sclupted_mesh.data.vertices.foreach_get('co', sculpted_arr)

    if layer_disabled_mesh:

        layer_disabled_arr = numpy.zeros(len(layer_disabled_mesh.data.vertices)*3, dtype=numpy.float32)
        layer_disabled_mesh.data.vertices.foreach_get('co', layer_disabled_arr)
    
        sculpted_arr = numpy.subtract(sculpted_arr, base_arr)
        layer_disabled_arr = numpy.subtract(layer_disabled_arr, base_arr)
    
        # Subtract to get offset
        offset = numpy.subtract(sculpted_arr, layer_disabled_arr)

        # Free numpy memory
        del layer_disabled_arr

    else:
        offset = numpy.subtract(sculpted_arr, base_arr)

    if intensity != 1.0 or intensity != 0.0:
        offset = numpy.divide(offset, intensity)

    max_value = numpy.abs(offset).max()  
    offset.shape = (offset.shape[0]//3, 3)
    
    # Create new attribute to store the offset
    att = base.data.attributes.get(OFFSET_ATTR)
    if not att:
        att = base.data.attributes.new(OFFSET_ATTR, 'FLOAT_VECTOR', 'POINT')
    att.data.foreach_set('vector', offset.ravel())

    # Free numpy array memory just in case
    del base_arr
    del sculpted_arr
    del offset

    print('INFO: Geting offset attributes finished!')

    return att, max_value

def bake_multires_image(obj, image, uv_name, intensity=1.0):

    context = bpy.context
    scene = context.scene

    # Get combined but active layer disabled image
    layer_disabled_vdm_image = None
    node = get_active_ypaint_node(obj)
    if node:
        yp = node.node_tree.yp
        if is_multi_disp_used(yp):
            layer_disabled_vdm_image = get_combined_vdm_image(obj, uv_name, width=image.size[0], height=image.size[1], disable_current_layer=True)

    set_active_object(obj)
    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')

    if len(context.selected_objects) > 1:
        bpy.ops.object.select_all(action='DESELECT')
    if not obj.select_get():
        set_object_select(obj, True)

    # Disable other modifiers
    ori_mod_show_viewport = []
    ori_mod_show_render = []
    for mod in obj.modifiers:
        if mod.type == 'MULTIRES' or mod.type == 'SUBSURF': continue
        if mod.show_viewport:
            mod.show_viewport = False
            ori_mod_show_viewport.append(mod.name)
        if mod.show_render:
            mod.show_render = False
            ori_mod_show_render.append(mod.name)

    # Temp object 0: Base
    temp0 = obj.copy()
    link_object(scene, temp0)
    temp0.data = temp0.data.copy()
    temp0.location = obj.location + Vector(((obj.dimensions[0]+0.1)*1, 0.0, 0.0))     

    # Delete multires and shape keys
    set_active_object(temp0)
    if temp0.data.shape_keys: bpy.ops.object.shape_key_remove(all=True)
    max_level = 0
    for mod in temp0.modifiers:
        if mod.type == 'MULTIRES':
            max_level = mod.total_levels
            bpy.ops.object.modifier_remove(modifier=mod.name)
            break

    # Apply subsurf
    tsubsurf = get_subsurf_modifier(temp0)
    if not tsubsurf:
        bpy.ops.object.modifier_add(type='SUBSURF')
        tsubsurf = [m for m in temp0.modifiers if m.type == 'SUBSURF'][0]
    tsubsurf.show_viewport = True
    tsubsurf.levels = max_level
    tsubsurf.render_levels = max_level
    bpy.ops.object.modifier_apply(modifier=tsubsurf.name)

    # Temp object 2: Sculpted/Multires mesh
    temp2 = obj.copy()
    link_object(scene, temp2)
    temp2.data = temp2.data.copy()
    temp2.location = obj.location + Vector(((obj.dimensions[0]+0.1)*3, 0.0, 0.0))
    
    # Apply multires
    set_active_object(temp2)
    if temp2.data.shape_keys: bpy.ops.object.shape_key_remove(all=True)
    for mod in temp2.modifiers:
        if mod.type == 'MULTIRES':
            mod.levels = max_level
            bpy.ops.object.modifier_apply(modifier=mod.name)
            break  

    # Get tangent and bitangent images
    tanimage, bitimage = get_tangent_bitangent_images(obj, uv_name)

    # Temp object 1: Half combined vdm mesh
    temp1 = None
    if layer_disabled_vdm_image:
        temp1 = temp0.copy()
        link_object(scene, temp1)
        temp1.data = temp1.data.copy()
        temp1.location = obj.location + Vector(((obj.dimensions[0]+0.1)*2, 0.0, 0.0))
        set_active_object(temp1)

        vdm_loader = get_vdm_loader_geotree(uv_name, layer_disabled_vdm_image, tanimage, bitimage)
        bpy.ops.object.modifier_add(type='NODES')
        geomod = temp1.modifiers[-1]
        geomod.node_group = vdm_loader
        temp1.modifiers.active = geomod

        # Apply geomod
        bpy.ops.object.modifier_apply(modifier=geomod.name)

        # Remove vdm loader group
        bpy.data.node_groups.remove(vdm_loader)

    # Calculate offset from two temp objects
    att, max_value = get_offset_attributes(temp0, temp2, temp1, intensity)

    # Set material to temp object 0
    temp0.data.materials.clear()
    mat = get_offset_bake_mat(uv_name, target_image=image, bitangent_image=bitimage)
    temp0.data.materials.append(mat)

    # Bake preparations
    book = _remember_before_bake(obj)
    _prepare_bake_settings(book, temp0, uv_name)

    # Bake offest
    print('INFO: Baking vdm...')
    bpy.ops.object.bake()
    print('INFO: Baking vdm is finished!')

    # Pack image
    #image.pack()

    # Recover bake settings
    _recover_bake_settings(book, True) 

    # Remove temp data
    remove_mesh_obj(temp0)
    remove_mesh_obj(temp2)
    if temp1: remove_mesh_obj(temp1)
    #bpy.data.images.remove(tanimage)
    #bpy.data.images.remove(bitimage)
    if layer_disabled_vdm_image:
        bpy.data.images.remove(layer_disabled_vdm_image)

    # Remove material
    if mat.users <= 1: bpy.data.materials.remove(mat, do_unlink=True)

    # Recover disabled modifiers
    for mod in obj.modifiers:
        if mod.name in ori_mod_show_viewport:
            mod.show_viewport = True
        if mod.name in ori_mod_show_render:
            mod.show_render = True

    # Set back object to active
    set_active_object(obj)
    set_object_select(obj, True)

def get_combined_vdm_image(obj, uv_name, width=1024, height=1024, disable_current_layer=False):
    # Bake preparations
    book = _remember_before_bake(obj)
    _prepare_bake_settings(book, obj, uv_name)     

    mat = get_active_material(obj)
    node = get_active_ypaint_node(obj)
    if not mat or not node: return None
    #mtree = mat.tree
    tree = node.node_tree
    yp = tree.yp
    height_root_ch = get_root_height_channel(yp)
    if not height_root_ch: return None

    # Get active layer
    try: cur_layer = yp.layers[yp.active_layer_index]
    except Exception as e:
        print(e)
        return None

    # Disable sculpt mode first
    ori_sculpt_mode = yp.sculpt_mode
    if yp.sculpt_mode:
        yp.sculpt_mode = False

    # Disable current layer
    ori_layer_enable = cur_layer.enable
    if disable_current_layer:
        cur_layer.enable = False

    # Disable all flip Y/Z
    ori_flip_yzs = {}
    for i, l in enumerate(yp.layers):
        height_ch = get_height_channel(l)
        if not height_ch.enable or height_ch.normal_map_type != 'VECTOR_DISPLACEMENT_MAP': continue
        ori_flip_yzs[str(i)] = height_ch.vdisp_enable_flip_yz
        height_ch.vdisp_enable_flip_yz = False

    # Make sure vdm output exists
    if not height_root_ch.enable_subdiv_setup:
        check_all_channel_ios(yp, force_height_io=True)

    # Combined VDM image name
    if disable_current_layer:
        image_name = obj.name + '_' + uv_name + TEMP_LAYER_DISABLED_VDM_IMAGE_SUFFIX
    else: image_name = obj.name + '_' + uv_name + TEMP_COMBINED_VDM_IMAGE_SUFFIX

    # Create combined vdm image
    image = bpy.data.images.new(name=image_name,
            width=width, height=height, alpha=False, float_buffer=True)
    image.generated_color = (0,0,0,1)

    # Get output node and remember original bsdf input
    mat_out = get_active_mat_output_node(mat.node_tree)
    ori_bsdf = mat_out.inputs[0].links[0].from_socket

    # Create setup nodes
    tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
    emit = mat.node_tree.nodes.new('ShaderNodeEmission')

    # Get combined vdm calculation node
    calc = mat.node_tree.nodes.new('ShaderNodeGroup')
    calc.node_tree = get_node_tree_lib(lib.COMBINED_VDM)

    # Set tex as active node
    mat.node_tree.nodes.active = tex
    tex.image = image

    # Emission connection
    disp_outp = node.outputs.get(height_root_ch.name + io_suffix['HEIGHT'])
    max_height_outp = node.outputs.get(height_root_ch.name + io_suffix['MAX_HEIGHT'])
    vdisp_outp = node.outputs.get(height_root_ch.name + io_suffix['VDISP'])

    # Connection
    #mat.node_tree.links.new(vdisp_outp, emit.inputs[0])
    mat.node_tree.links.new(disp_outp, calc.inputs['Height'])
    mat.node_tree.links.new(max_height_outp, calc.inputs['Scale'])
    mat.node_tree.links.new(vdisp_outp, calc.inputs['Vector Displacement'])
    mat.node_tree.links.new(calc.outputs[0], emit.inputs[0])
    mat.node_tree.links.new(emit.outputs[0], mat_out.inputs[0])

    # Bake!
    bpy.ops.object.bake()

    # Set fake user for the bake result so it won't disappear
    #image.use_fake_user = True
    #image.pack()

    # Recover original bsdf
    mat.node_tree.links.new(ori_bsdf, mat_out.inputs[0])

    # Remove bake nodes
    simple_remove_node(mat.node_tree, tex, remove_data=False)
    simple_remove_node(mat.node_tree, emit)
    simple_remove_node(mat.node_tree, calc)

    # Recover active layer
    if ori_layer_enable != cur_layer.enable:
        cur_layer.enable = ori_layer_enable

    # Recover input outputs
    if not height_root_ch.enable_subdiv_setup:
        check_all_channel_ios(yp)

    # Recover flip yzs
    for key, val in ori_flip_yzs.items():
        l = yp.layers[int(key)]
        height_ch = get_height_channel(l)
        if height_ch.vdisp_enable_flip_yz != val:
            height_ch.vdisp_enable_flip_yz = val

    # Recover sculpt mode
    if ori_sculpt_mode:
        yp.sculpt_mode = True

    # Revover bake settings
    _recover_bake_settings(book, True)

    return image

def get_tangent_bitangent_images(obj, uv_name):

    tanimage_name = obj.name + '_' + uv_name + TEMP_TANGENT_IMAGE_SUFFIX
    bitimage_name = obj.name + '_' + uv_name + TEMP_BITANGENT_IMAGE_SUFFIX

    tanimage = bpy.data.images.get(tanimage_name)
    bitimage = bpy.data.images.get(bitimage_name)

    # Check mesh hash
    mh = get_mesh_hash(obj)
    if obj.yp.mesh_hash != mh:
        obj.yp.mesh_hash = mh

        # Remove current images if hash doesn't match
        if tanimage: bpy.data.images.remove(tanimage)
        if bitimage: bpy.data.images.remove(bitimage)

        tanimage = None
        bitimage = None

    if not tanimage or not bitimage:
        context = bpy.context
        scene = context.scene 

        # Copy object first
        temp = obj.copy()
        link_object(scene, temp)
        temp.data = temp.data.copy()
        context.view_layer.objects.active = temp
        temp.location += Vector(((obj.dimensions[0]+0.1)*1, 0.0, 0.0))     

        # Set active uv
        uv_layers = get_uv_layers(temp)
        uv_layers.active = uv_layers.get(uv_name)

        # Mesh with ngons will can't calculate tangents
        try:
            temp.data.calc_tangents()
        except:
            # Triangulate ngon faces on temp object
            bpy.ops.object.select_all(action='DESELECT')
            temp.select_set(True)
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.reveal()
            bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.mesh.select_mode(type="FACE")
            bpy.ops.mesh.select_face_by_sides(number=4, type='GREATER')
            bpy.ops.mesh.quads_convert_to_tris()
            bpy.ops.mesh.tris_convert_to_quads()
            bpy.ops.object.mode_set(mode='OBJECT')

            temp.data.calc_tangents()   

        # Bitangent sign attribute's
        bs_att = temp.data.attributes.get(BSIGN_ATTR)
        if not bs_att:
            bs_att = temp.data.attributes.new(BSIGN_ATTR, 'FLOAT', 'CORNER')
        arr = numpy.zeros(len(temp.data.loops), dtype=numpy.float32)
        temp.data.loops.foreach_get('bitangent_sign', arr)
        bs_att.data.foreach_set('value', arr.ravel())    

        # Disable multires modifiers if there's any
        for mod in temp.modifiers:
            if mod.type == 'MULTIRES':
                mod.show_viewport = False
                mod.show_render = False

        # Get subsurf modifiers of temp object
        tsubsurf = get_subsurf_modifier(temp)
        if not tsubsurf:
            bpy.ops.object.modifier_add(type='SUBSURF')
            tsubsurf = [m for m in temp.modifiers if m.type == 'SUBSURF'][0]
        tsubsurf.show_viewport = True
        tsubsurf.show_render = True

        # Disable non subsurf modifiers
        for m in temp.modifiers:
            if m != tsubsurf:
                m.show_viewport = False
                m.show_render = False

        # Set subsurf to max levels
        #tsubsurf.levels = tsubsurf.render_levels

        # Bake preparations
        book = _remember_before_bake(temp)
        _prepare_bake_settings(book, temp, uv_name)     

        if not tanimage:
            tanimage = bpy.data.images.new(name=tanimage_name,
                    width=1024, height=1024, alpha=False, float_buffer=True)
            tanimage.generated_color = (0,0,0,1)

            # Set bake tangent material
            temp.data.materials.clear()
            mat = get_tangent_bake_mat(uv_name, target_image=tanimage)
            temp.data.materials.append(mat)   

            # Bake tangent
            bpy.ops.object.bake()

            # Remove temp mat
            if mat.users <= 1: bpy.data.materials.remove(mat, do_unlink=True)

        if not bitimage:

            bitimage = bpy.data.images.new(name=bitimage_name,
                    width=1024, height=1024, alpha=False, float_buffer=True)
            bitimage.generated_color = (0,0,0,1)

            # Set bake bitangent material
            temp.data.materials.clear()
            mat = get_bitangent_bake_mat(uv_name, target_image=bitimage)
            temp.data.materials.append(mat)

            # Bake bitangent
            bpy.ops.object.bake()

            # Remove temp mat
            if mat.users <= 1: bpy.data.materials.remove(mat, do_unlink=True)

        # Pack tangent and bitangent images so they won't lost their data
        tanimage.pack()
        bitimage.pack()
        #tanimage.use_fake_user=True
        #bitimage.use_fake_user=True

        # Revover bake settings
        _recover_bake_settings(book, True)

        # Remove temp object
        remove_mesh_obj(temp)  

        # Back to original object
        set_active_object(obj)
        set_object_select(obj, True)

    return tanimage, bitimage

def get_vdm_intensity(layer, ch):
    layer_intensity = get_entity_prop_value(layer, 'intensity_value')
    ch_intensity = get_entity_prop_value(ch, 'intensity_value')
    ch_strength = get_entity_prop_value(ch, 'vdisp_strength')
    return layer_intensity * ch_intensity * ch_strength

def is_multi_disp_used(yp):

    num_disps = 0

    # Check if there's another vdm layer
    for l in yp.layers:
        if not l.enable: continue
        hch = get_height_channel(l)
        if not hch or not hch.enable or hch.normal_map_type not in {'BUMP_MAP', 'BUMP_NORMAL_MAP', 'VECTOR_DISPLACEMENT_MAP'}: continue
        num_disps += 1

    return num_disps > 1

class YSculptImage(bpy.types.Operator):
    bl_idname = "sculpt.y_sculpt_image"
    bl_label = "Sculpt Vector Displacement Image"
    bl_description = "Sculpt vector displacement image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node() and context.object and context.object.type == 'MESH' and hasattr(context, 'image') and context.image

    def execute(self, context):
        T = time.time()

        mat = get_active_material()
        obj = context.object
        scene = context.scene
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        layer = yp.layers[yp.active_layer_index]

        if layer.type != 'IMAGE':
            self.report({'ERROR'}, "This is not an image layer!")
            return {'CANCELLED'}

        source = get_layer_source(layer)
        image = source.image

        if not image:
            self.report({'ERROR'}, "This layer image is missing!")
            return {'CANCELLED'}

        uv_name = layer.uv_name
        mapping = get_layer_mapping(layer)

        height_root_ch = get_root_height_channel(yp)
        if not height_root_ch:
            self.report({'ERROR'}, "Need normal channel!")
            return {'CANCELLED'}

        height_ch = get_height_channel(layer)
        intensity = get_vdm_intensity(layer, height_ch) if height_ch else 1.0

        if mapping and is_transformed(mapping):
            self.report({'ERROR'}, "Cannot sculpt VDM with transformed mapping!")
            return {'CANCELLED'}

        # Get combined VDM image
        combined_vdm_image = None
        if is_multi_disp_used(yp):
            combined_vdm_image = get_combined_vdm_image(obj, uv_name, width=image.size[0], height=image.size[1])

        # Enable sculpt mode to disable all vector displacement layers
        yp.sculpt_mode = True

        # Get related modifiers
        subsurf = get_subsurf_modifier(obj)
        multires = get_multires_modifier(obj)

        if multires:
            multires.levels = multires.total_levels
            subsurf = multires
        elif not subsurf:
            # Create new subsurf modifier if there's none
            bpy.ops.object.modifier_add(type='SUBSURF')
            subsurf = [m for m in obj.modifiers if m.type == 'SUBSURF'][0]
            # NOTE: This just random default subdivision levels
            subsurf.levels = 3
            subsurf.render_levels = 3
            if is_mesh_flat_shaded(obj.data):
                subsurf.subdivision_type = 'SIMPLE'
        
        # Disable other modifiers
        ori_show_viewports = {}
        ori_show_renders = {}
        for m in obj.modifiers:
            if m != subsurf:
                ori_show_viewports[m.name] = m.show_viewport
                ori_show_renders[m.name] = m.show_render
                m.show_viewport = False
                m.show_render = False
            else:
                m.show_viewport = True
                m.show_render = True   

        # Bake tangent and bitangent first
        tanimage, bitimage = get_tangent_bitangent_images(obj, uv_name)

        # Create a temporary object
        temp = obj.copy()
        link_object(scene, temp)
        temp.data = temp.data.copy()
        context.view_layer.objects.active = temp
        temp.location += Vector(((obj.dimensions[0]+0.1)*1, 0.0, 0.0))     

        # Select temp object
        set_active_object(temp)
        set_object_select(temp, True)

        # Create geometry nodes to load vdm
        sculpt_image = image
        if combined_vdm_image:
            sculpt_image = combined_vdm_image
            intensity = 1.0

        vdm_loader = get_vdm_loader_geotree(uv_name, sculpt_image, tanimage, bitimage, intensity)
        bpy.ops.object.modifier_add(type='NODES')
        geomod = temp.modifiers[-1]
        geomod.node_group = vdm_loader
        temp.modifiers.active = geomod

        # Select back active object
        set_active_object(obj)
        set_object_select(obj, True)

        # Add multires modifier
        multires = get_multires_modifier(obj) #, TEMP_MULTIRES_NAME)
        if not multires:
            bpy.ops.object.modifier_add(type='MULTIRES')
            multires = [m for m in obj.modifiers if m.type == 'MULTIRES'][0]
            multires.name = TEMP_MULTIRES_NAME

        # Disable subsurf
        subsurf = get_subsurf_modifier(obj)
        if subsurf:
            subsurf.show_viewport = False
            subsurf.show_render = False
            levels = subsurf.levels
            subdiv_type = subsurf.subdivision_type
        else:
            levels = multires.total_levels
            subdiv_type = 'SIMPLE' if is_mesh_flat_shaded(obj.data) else 'CATMULL_CLARK'

        # Set to max levels
        for i in range(levels-multires.total_levels):
            bpy.ops.object.multires_subdivide(modifier=multires.name, mode=subdiv_type)      
        multires.levels = multires.total_levels
        multires.sculpt_levels = multires.total_levels
        multires.render_levels = multires.total_levels

        # Reshape multires
        bpy.ops.object.multires_reshape(modifier=multires.name)

        # Remove temp data
        remove_mesh_obj(temp) 
        #bpy.data.images.remove(tanimage)
        #bpy.data.images.remove(bitimage)
        bpy.data.node_groups.remove(vdm_loader)
        if combined_vdm_image:
            bpy.data.images.remove(combined_vdm_image)

        # Enable some modifiers again
        for mod_name, ori_show_viewport in ori_show_viewports.items():
            m = obj.modifiers.get(mod_name)
            if m: m.show_viewport = ori_show_viewport
        for mod_name, ori_show_render in ori_show_renders.items():
            m = obj.modifiers.get(mod_name)
            if m: m.show_render = ori_show_render  

        # Set armature to the top
        arm = get_armature_modifier(obj)
        if arm: bpy.ops.object.modifier_move_to_index(modifier=arm.name, index=0)

        bpy.ops.object.mode_set(mode='SCULPT')

        print('INFO: Sculpt mode is entered at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

        return {'FINISHED'}

class YApplySculptToImage(bpy.types.Operator):
    bl_idname = "sculpt.y_apply_sculpt_to_image"
    bl_label = "Apply Sculpt to Image"
    bl_description = "Apply sculpt to image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        T = time.time()

        obj = context.object
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp
        layer = yp.layers[yp.active_layer_index]
        height_ch = get_height_channel(layer)

        if height_ch:

            source = get_layer_source(layer)
            image = source.image
            uv_name = layer.uv_name

            intensity = get_vdm_intensity(layer, height_ch)

            # Bake multires image
            bake_multires_image(obj, image, uv_name, intensity)

        # Remove multires
        multires = get_multires_modifier(obj)
        levels = -1
        if multires:
            levels = multires.total_levels
            bpy.ops.object.modifier_remove(modifier=multires.name)

        # Enable subsurf back
        subsurf = get_subsurf_modifier(obj)
        if subsurf:
            subsurf.show_viewport = True
            subsurf.show_render = True
        else:
            bpy.ops.object.modifier_add(type='SUBSURF')
            subsurf = [m for m in obj.modifiers if m.type == 'SUBSURF'][0]
            if levels != -1:
                subsurf.levels = levels
                subsurf.render_levels = levels

        # Disable sculpt mode to bring back all vector displacement layers
        yp.sculpt_mode = False
        bpy.ops.object.mode_set(mode='OBJECT')

        # Go back to material view
        space = bpy.context.space_data
        if space.type == 'VIEW_3D' and space.shading.type not in {'MATERIAL', 'RENDERED'}:
            space.shading.type = 'MATERIAL'

        print('INFO: Applying sculpt to VDM is done at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

        return {'FINISHED'}

class YCancelSculptToImage(bpy.types.Operator):
    bl_idname = "sculpt.y_cancel_sculpt_to_image"
    bl_label = "Cancel Sculpt to Image"
    bl_description = "Cancel sculpt to image"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        obj = context.object
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp
        layer = yp.layers[yp.active_layer_index]
        height_ch = get_height_channel(layer)

        # Remove multires
        multires = get_multires_modifier(obj, TEMP_MULTIRES_NAME)
        if multires:
            bpy.ops.object.modifier_remove(modifier=multires.name)

        # Enable subsurf back
        subsurf = get_subsurf_modifier(obj)
        if not subsurf: subsurf = get_multires_modifier(obj)
        if subsurf:
            subsurf.show_viewport = True
            subsurf.show_render = True

        # Disable sculpt mode to bring back all vector displacement layers
        yp.sculpt_mode = False
        bpy.ops.object.mode_set(mode='OBJECT')

        # Go back to material view
        space = bpy.context.space_data
        if space.type == 'VIEW_3D' and space.shading.type not in {'MATERIAL', 'RENDERED'}:
            space.shading.type = 'MATERIAL'

        return {'FINISHED'}

class YFixVDMMismatchUV(bpy.types.Operator):
    bl_idname = "object.y_fix_vdm_missmatch_uv"
    bl_label = "Fix Missmatch VDM UV"
    bl_description = "Active VDM layer has different UV than the active render UV, use this operator to fix it"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        obj = context.object
        mat = get_active_material(obj)
        node = get_active_ypaint_node()
        yp = node.node_tree.yp
        layer = yp.layers[yp.active_layer_index]

        # Set uv map active render
        objs = get_all_objects_with_same_materials(mat)
        for obj in objs:
            uv_layers = get_uv_layers(obj)
            uv = uv_layers.get(layer.uv_name)
            if uv and not uv.active_render:
                uv.active_render = True

        return {'FINISHED'}

def register():
    bpy.utils.register_class(YSculptImage)
    bpy.utils.register_class(YApplySculptToImage)
    bpy.utils.register_class(YCancelSculptToImage)
    bpy.utils.register_class(YFixVDMMismatchUV)

def unregister():
    bpy.utils.unregister_class(YSculptImage)
    bpy.utils.unregister_class(YApplySculptToImage)
    bpy.utils.unregister_class(YCancelSculptToImage)
    bpy.utils.unregister_class(YFixVDMMismatchUV)
