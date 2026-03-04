import bpy, numpy, time, math, bmesh
from bpy.props import *
from . import Layer, lib, ListItem
from .common import *
from .vector_displacement_lib import *
from .input_outputs import *

TEMP_MULTIRES_NAME = '_YP_TEMP_MULTIRES'
TEMP_COMBINED_VDM_IMAGE_SUFFIX = '_YP_TEMP_COMBINED_VDM'
TEMP_LAYER_DISABLED_VDM_IMAGE_SUFFIX = '_YP_LAYER_DISABLED_VDM'

def _remember_before_bake(obj):
    book = dotdict()
    book.scene = scene = bpy.context.scene
    book.obj = obj
    book.mode = obj.mode
    uv_layers = obj.data.uv_layers
    ypui = bpy.context.window_manager.ypui

    # Remember render settings
    book.engine = scene.render.engine
    book.bake_type = scene.cycles.bake_type
    book.samples = scene.cycles.samples
    book.threads_mode = scene.render.threads_mode
    book.margin = scene.render.bake.margin
    book.margin_type = scene.render.bake.margin_type
    book.use_clear = scene.render.bake.use_clear
    book.normal_space = scene.render.bake.normal_space
    book.simplify = scene.render.use_simplify
    book.dither_intensity = scene.render.dither_intensity
    book.device = scene.cycles.device
    book.use_selected_to_active = scene.render.bake.use_selected_to_active
    book.max_ray_distance = scene.render.bake.max_ray_distance
    book.cage_extrusion = scene.render.bake.cage_extrusion
    book.use_cage = scene.render.bake.use_cage
    book.use_denoising = scene.cycles.use_denoising
    book.bake_target = scene.render.bake.target
    book.material_override = bpy.context.view_layer.material_override

    # Multires related
    book.use_bake_multires = get_scene_bake_multires(scene)
    book.use_bake_clear = get_scene_bake_clear(scene)
    book.render_bake_type = get_scene_render_bake_type(scene)
    book.bake_margin = get_scene_bake_margin(scene)
    book.view_transform = scene.view_settings.view_transform

    if is_bl_newer_than(5):
        book.displacement_space = scene.render.bake.displacement_space
        book.use_lores_mesh = scene.render.bake.use_lores_mesh

    # Remember world settings
    if scene.world:
        book.distance = scene.world.light_settings.distance

    # Remember image editor images
    book.editor_images = [a.spaces[0].image for a in bpy.context.screen.areas if a.type == 'IMAGE_EDITOR']
    book.editor_pins = [a.spaces[0].use_image_pin for a in bpy.context.screen.areas if a.type == 'IMAGE_EDITOR']

    # Remember uv
    book.active_uv = uv_layers.active.name
    active_render_uvs = [u for u in uv_layers if u.active_render]
    if active_render_uvs:
        book.active_render_uv = active_render_uvs[0].name

    # Remember object hides
    book.hide_viewports = {}
    book.hide_renders = {}
    book.hide_selects = {}
    book.hides = {}
    for ob in get_scene_objects():
        book.hide_viewports[ob.name] = ob.hide_viewport
        book.hide_renders[ob.name] = ob.hide_render
        book.hide_selects[ob.name] = ob.hide_select
        book.hides[ob.name] = get_object_hide(ob)

    return book

def _prepare_bake_settings(book, obj, uv_map='', samples=1, margin=15, bake_device='CPU', bake_type='EMIT'):

    scene = bpy.context.scene
    ypui = bpy.context.window_manager.ypui
    wmyp = bpy.context.window_manager.ypprops

    # Hack function on depsgraph update can cause crash, so halt it before baking
    wmyp.halt_hacks = True

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
    scene.render.dither_intensity = 0.0
    set_scene_bake_margin(scene, margin)
    set_scene_bake_clear(scene, False)
    scene.cycles.samples = samples
    scene.cycles.use_denoising = False
    scene.cycles.device = bake_device
    scene.view_settings.view_transform = 'Standard' if is_bl_newer_than(2, 80) else 'Default'
    bpy.context.view_layer.material_override = None

    if bake_type == 'VECTOR_DISPLACEMENT':
        set_scene_bake_multires(scene, True)
        set_scene_render_bake_type(scene, bake_type)
        scene.render.bake.displacement_space = 'TANGENT'
        scene.render.bake.use_lores_mesh = False
    else:
        set_scene_bake_multires(scene, False)
        scene.cycles.bake_type = bake_type

    # Disable all other objects for better performance
    for ob in get_scene_objects():
        if ob == obj: continue
        ob.hide_viewport = True
        ob.hide_render = True
        ob.hide_select = True
        set_object_hide(ob, True)

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
        bpy.ops.object.mode_set(mode='OBJECT')
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
    scene = book.scene
    obj = book.obj
    uv_layers = obj.data.uv_layers
    ypui = bpy.context.window_manager.ypui
    wmyp = bpy.context.window_manager.ypprops

    scene.render.engine = book.engine
    scene.cycles.samples = book.samples
    scene.cycles.bake_type = book.bake_type
    scene.render.threads_mode = book.threads_mode
    scene.render.bake.margin = book.margin
    scene.render.bake.margin_type = book.margin_type
    scene.render.bake.use_clear = book.use_clear
    scene.render.use_simplify = book.simplify
    scene.render.dither_intensity = book.dither_intensity
    scene.cycles.device = book.device
    scene.cycles.use_denoising = book.use_denoising
    scene.render.bake.target = book.bake_target
    scene.render.bake.use_selected_to_active = book.use_selected_to_active
    scene.render.bake.max_ray_distance = book.max_ray_distance
    scene.render.bake.cage_extrusion = book.cage_extrusion
    scene.render.bake.use_cage = book.use_cage
    scene.view_settings.view_transform = book.view_transform
    bpy.context.view_layer.material_override = book.material_override

    # Multires related
    set_scene_bake_multires(scene, book.use_bake_multires)
    set_scene_bake_clear(scene, book.use_bake_clear)
    set_scene_render_bake_type(scene, book.render_bake_type)
    set_scene_bake_margin(scene, book.bake_margin)

    if is_bl_newer_than(5):
        scene.render.bake.displacement_space = book.displacement_space
        scene.render.bake.use_lores_mesh = book.use_lores_mesh

    # Recover world settings
    if scene.world:
        scene.world.light_settings.distance = book.distance

    # Recover image editors
    for i, area in enumerate([a for a in bpy.context.screen.areas if a.type == 'IMAGE_EDITOR']):
        # Some image can be deleted after baking process so use try except
        try: area.spaces[0].image = book.editor_images[i]
        except: area.spaces[0].image = None

        area.spaces[0].use_image_pin = book.editor_pins[i]

    # Recover uv
    if recover_active_uv:
        uvl = uv_layers.get(book.active_uv)
        if uvl: uv_layers.active = uvl
        if 'active_render_uv' in book:
            uvl = uv_layers.get(book.active_render_uv)
            if uvl: uvl.active_render = True

    # Recover object hides
    for ob in get_scene_objects():
        if ob.name not in book.hide_viewports: continue
        ob.hide_viewport = book.hide_viewports[ob.name]
        ob.hide_render = book.hide_renders[ob.name]
        ob.hide_select = book.hide_selects[ob.name]
        set_object_hide(ob, book.hides[ob.name])

    # Bring back the hack functions
    wmyp.halt_hacks = False

def copy_props_to_dict(source, target_dict, debug=False):
    if debug: print()

    for prop in dir(source):
        if prop in {'bl_rna', 'rna_type'}: continue
        if prop.startswith('__'): continue

        val = getattr(source, prop)
        attr_type = str(type(val))

        if attr_type.startswith("<class 'bpy_func"): continue
        if attr_type.startswith("<class 'NoneType"): continue
        #if attr_type.startswith("<class 'bpy_prop"): continue

        if debug: print(prop, attr_type)

        if 'bpy_prop_collection' in attr_type:
            target_dict[prop] = []
            for c in val:
                subdict = {}
                copy_props_to_dict(c, subdict, debug)
                target_dict[prop].append(subdict)
        else:
            try: target_dict[prop] = val
            except Exception as e: pass

    if debug: print()

''' Applying modifier with shape keys. Based on implementation by Przemysław Bągard.'''
def apply_modifiers_with_shape_keys(obj, selected_modifiers, disable_armatures=True):

    list_properties = []
    properties = ["interpolation", "mute", "name", "relative_key", "slider_max", "slider_min", "value", "vertex_group"]
    T = time.time()

    scene = bpy.context.scene

    disabled_armature_modifiers = []
    if disable_armatures:
        for modifier in obj.modifiers:
            if modifier.name not in selected_modifiers and modifier.type == 'ARMATURE' and modifier.show_viewport == True:
                disabled_armature_modifiers.append(modifier)
                modifier.show_viewport = False
    
    num_shapes = 0
    if obj.data.shape_keys:
        num_shapes = len(obj.data.shape_keys.key_blocks)

    # Remember original selected objects
    ori_selected_objs = [o for o in bpy.context.selected_objects]
    ori_active = get_active_object()
    set_active_object(obj)
    
    if(num_shapes == 0):
        for mod_name in selected_modifiers:
            try: bpy.ops.object.modifier_apply(modifier=mod_name)
            except Exception as e: print(e)
        if disable_armatures:
            for modifier in disabled_armature_modifiers:
                modifier.show_viewport = True
        set_active_object(ori_active)
        return (True, None)

    # We want to preserve original object, so all shapes will be joined to it.
    if obj.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    set_object_select(obj, True)
    ori_key_idx = obj.active_shape_key_index

    ori_hide = get_object_hide(obj)
    set_object_hide(obj, False)
    
    # Copy object which has the modifiers applied
    applied_obj = obj.copy()
    applied_obj.data = applied_obj.data.copy()
    link_object(scene, applied_obj)

    # Remove shape keys and apply modifiers
    set_active_object(applied_obj)
    bpy.ops.object.shape_key_remove(all=True)
    for mod_name in selected_modifiers:
        try: bpy.ops.object.modifier_apply(modifier=mod_name)
        except Exception as e: print(e)

    # Get applied vertex count
    vert_count = len(applied_obj.data.vertices)

    # Remove applied copy of the object.
    remove_mesh_obj(applied_obj)
    
    # Return selection to original object.
    set_active_object(obj)
    set_object_select(obj, True)

    # Get key objects and save key shape properties
    key_objs = [None]
    for i in range(0, num_shapes):
        key_b = obj.data.shape_keys.key_blocks[i]
        properties_object = {p:None for p in properties}
        properties_object["name"] = key_b.name
        properties_object["mute"] = key_b.mute
        properties_object["interpolation"] = key_b.interpolation
        properties_object["relative_key"] = key_b.relative_key.name
        properties_object["slider_max"] = key_b.slider_max
        properties_object["slider_min"] = key_b.slider_min
        properties_object["value"] = key_b.value
        properties_object["vertex_group"] = key_b.vertex_group
        list_properties.append(properties_object)

        if i == 0: continue

        # Copy as key object.
        key_obj = obj.copy()
        key_obj.data = key_obj.data.copy()
        link_object(scene, key_obj)
        set_active_object(key_obj)
        bpy.ops.object.shape_key_remove(all=True)
        
        # Get right shape-key.
        obj.active_shape_key_index = i
        bpy.ops.object.shape_key_transfer()
        key_obj.active_shape_key_index = 0
        bpy.ops.object.shape_key_remove()
        bpy.ops.object.shape_key_remove(all=True)
        
        # Apply modifier on temporary object
        for mod_name in selected_modifiers:
            try: bpy.ops.object.modifier_apply(modifier=mod_name)
            except Exception as e: print(e)

        # Get shape key vertex count
        key_vert_count = len(key_obj.data.vertices)

        # Store key objects
        key_objs.append(key_obj)

        # Deselect key object
        set_object_select(key_obj, False)
        
        # Verify number of vertices.
        if vert_count != key_vert_count:

            # Remove temporary objects
            for o in reversed(key_objs): 
                if o != None: remove_mesh_obj(o)

            # Recover selected objects
            bpy.ops.object.select_all(action='DESELECT')
            for o in ori_selected_objs:
                set_object_select(o, True)
            set_active_object(ori_active)
    
            # Enable armatures back
            if disable_armatures:
                for modifier in disabled_armature_modifiers:
                    modifier.show_viewport = True

            # Recover hide
            set_object_hide(obj, ori_hide)

            errorInfo = ("Shape keys ended up with different number of vertices!\n"
                         "All shape keys needs to have the same number of vertices after modifier is applied.\n"
                         "Otherwise joining such shape keys will fail!")
            return (False, errorInfo)

    # Save animation data
    ori_fcurves = []
    ori_action_name = ''
    if obj.data.shape_keys.animation_data and obj.data.shape_keys.animation_data.action:
        ori_action_name = obj.data.shape_keys.animation_data.action.name
        sk_fcurves = get_datablock_fcurves(obj.data.shape_keys)
        for fc in sk_fcurves:
            fc_dic = {}

            for prop in dir(fc):
                copy_props_to_dict(fc, fc_dic) #, True)

            ori_fcurves.append(fc_dic)

    # Handle base shape in original object
    print("apply_modifiers_with_shape_keys: Applying base shape key")

    # Return selection to original object.
    set_active_object(obj)
    set_object_select(obj, True)

    # Make sure active shape key index is set to avoid error
    obj.active_shape_key_index = 0

    bpy.ops.object.shape_key_remove(all=True)
    for mod_name in selected_modifiers:
        try: bpy.ops.object.modifier_apply(modifier=mod_name)
        except Exception as e: print(e)
    bpy.ops.object.shape_key_add(from_mix=False)

    # Create new shape keys based on key objects
    for i in range(1, num_shapes):

        # Select key object
        key_obj = key_objs[i]
        set_object_select(key_obj, True)

        # Join with original object
        bpy.ops.object.join_shapes()

        # Deselect again
        set_object_select(key_obj, False)
    
    # Restore shape key properties like name, mute etc.
    for i in range(0, num_shapes):
        key_b = obj.data.shape_keys.key_blocks[i]
        key_b.name = list_properties[i]["name"]
        key_b.interpolation = list_properties[i]["interpolation"]
        key_b.mute = list_properties[i]["mute"]
        key_b.slider_max = list_properties[i]["slider_max"]
        key_b.slider_min = list_properties[i]["slider_min"]
        key_b.value = list_properties[i]["value"]
        key_b.vertex_group = list_properties[i]["vertex_group"]
        rel_key = list_properties[i]["relative_key"]
    
        for j in range(0, num_shapes):
            key_brel = obj.data.shape_keys.key_blocks[j]
            if rel_key == key_brel.name:
                key_b.relative_key = key_brel
                break
    
    # Remove key objects
    for o in reversed(key_objs):
        if o != None: remove_mesh_obj(o)
    
    # Enable armatures back
    if disable_armatures:
        for modifier in disabled_armature_modifiers:
            modifier.show_viewport = True

    # Set to original key
    obj.active_shape_key_index = ori_key_idx

    # Recover animation data
    if any(ori_fcurves):

        obj.data.shape_keys.animation_data_create()
        obj.data.shape_keys.animation_data.action = bpy.data.actions.new(name=ori_action_name)

        for ofc in ori_fcurves:
            fcurve = new_fcurve(obj.data.shape_keys, ofc['data_path'])

            for key, val in ofc.items():
                if key in {'data_path', 'keyframe_points'}: continue
                try: setattr(fcurve, key, val)
                except Exception as e: pass

            for kp in ofc['keyframe_points']:
                k = fcurve.keyframe_points.insert(
                frame=kp['co'][0],
                value=kp['co'][1]
                )

                for key, val in kp.items():
                    try: setattr(k, key, val)
                    except Exception as e: pass

            for mod in ofc['modifiers']:
                m = fcurve.modifiers.new(type=mod['type'])
                for key, val in mod.items():
                    try: setattr(m, key, val)
                    except Exception as e: pass

    # Recover hide
    set_object_hide(obj, ori_hide)

    # Recover selected objects
    bpy.ops.object.select_all(action='DESELECT')
    for o in ori_selected_objs:
        set_object_select(o, True)
    set_active_object(ori_active)
    
    return (True, None)

def apply_mirror_modifier(obj):
    mirror = None
    mirror_idx = -1

    # Get uv mirrored mirror modifier
    for i, mod in enumerate(obj.modifiers):
        if not mod.show_viewport or not mod.show_render: continue
        if mod.type == 'MIRROR' and (mod.use_mirror_u or mod.use_mirror_v):
            mirror = mod
            mirror_idx = i
            break

    if not mirror: return

    # Check if mirror modifier has only one axis
    axis = [mirror.use_axis[0], mirror.use_axis[1], mirror.use_axis[2]]
    axis_num = 0
    for a in axis:
        if a: axis_num += 1
    if axis_num > 1 or axis_num == 0:
        return

    # Get number of vertices to know which vertices need to deleted after applying the sculpt
    obj.yp_vdm.num_verts = len(obj.data.vertices)

    # Remember mirror properties
    use_mirror_merge = mirror.use_mirror_merge
    use_clip = mirror.use_clip
    use_mirror_vertex_groups = mirror.use_mirror_vertex_groups
    use_mirror_u = mirror.use_mirror_u
    use_mirror_v = mirror.use_mirror_v
    use_mirror_udim = mirror.use_mirror_udim
    mirror_offset_u = mirror.mirror_offset_u
    mirror_offset_v = mirror.mirror_offset_v
    offset_u = mirror.offset_u
    offset_v = mirror.offset_v
    mirror_object = mirror.mirror_object
    merge_threshold = mirror.merge_threshold
    show_in_editmode = mirror.show_in_editmode
    show_on_cage = mirror.show_on_cage

    # Apply modifier
    success, errorInfo = apply_modifiers_with_shape_keys(obj, [mirror.name])
    if not success:
        print('apply_modifiers_with_shape_keys FAILED:', errorInfo)
        obj.yp_vdm.mirror_modifier_name = ''
        return

    # Bring back the mirror but disable it
    bpy.ops.object.modifier_add(type='MIRROR')
    new_mirror = obj.modifiers[-1]
    new_mirror.show_viewport = False
    new_mirror.show_render = False
    obj.yp_vdm.mirror_modifier_name = new_mirror.name

    # Move up new mirror modifier
    bpy.ops.object.modifier_move_to_index(modifier=new_mirror.name, index=mirror_idx)

    # Bring back modifier attributes
    new_mirror.use_axis[0] = axis[0]
    new_mirror.use_axis[1] = axis[1]
    new_mirror.use_axis[2] = axis[2]
    new_mirror.use_mirror_merge = use_mirror_merge
    new_mirror.use_clip = use_clip
    new_mirror.use_mirror_vertex_groups = use_mirror_vertex_groups
    new_mirror.use_mirror_u = use_mirror_u
    new_mirror.use_mirror_v = use_mirror_v
    new_mirror.use_mirror_udim = use_mirror_udim
    new_mirror.mirror_offset_u = mirror_offset_u
    new_mirror.mirror_offset_v = mirror_offset_v
    new_mirror.offset_u = offset_u
    new_mirror.offset_v = offset_v
    new_mirror.mirror_object = mirror_object
    new_mirror.merge_threshold = merge_threshold
    new_mirror.show_in_editmode = show_in_editmode
    new_mirror.show_on_cage = show_on_cage

def recover_mirror_modifier(obj):
    if obj.yp_vdm.mirror_modifier_name == '': return

    # Go to edit mode to delete mirrored verts
    bpy.ops.object.mode_set(mode='EDIT')

    # Get bmesh
    bm = bmesh.from_edit_mesh(obj.data)
    bm.verts.ensure_lookup_table()

    # Deselect all first
    bpy.ops.mesh.select_all(action='DESELECT')

    # Select all vertices outside
    for i in range(obj.yp_vdm.num_verts, len(bm.verts)):
        bm.verts[i].select = True

    # Delete mirrored vertices
    bpy.ops.mesh.delete(type='VERT')

    # Back to object mode
    bpy.ops.object.mode_set(mode='OBJECT')

    # Show up the modifier back
    mirror = obj.modifiers.get(obj.yp_vdm.mirror_modifier_name)
    if mirror:
        mirror.show_viewport = True
        mirror.show_render = True
    
    obj.yp_vdm.mirror_modifier_name = ''
    obj.yp_vdm.num_verts = 0

def get_offset_attributes(base, sclupted_mesh, layer_disabled_mesh=None, intensity=1.0):

    print('INFO: Getting offset attributes...')

    if len(base.data.vertices) != len(sclupted_mesh.data.vertices):
        return None, None

    # Get coordinates for each vertices
    base_arr = numpy.zeros(len(base.data.vertices) * 3, dtype=numpy.float32)
    base.data.vertices.foreach_get('co', base_arr)

    sculpted_arr = numpy.zeros(len(sclupted_mesh.data.vertices) * 3, dtype=numpy.float32)
    sclupted_mesh.data.vertices.foreach_get('co', sculpted_arr)

    if layer_disabled_mesh:

        layer_disabled_arr = numpy.zeros(len(layer_disabled_mesh.data.vertices) * 3, dtype=numpy.float32)
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
    offset.shape = (offset.shape[0] // 3, 3)
    
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

def mute_all_shape_keys(obj):
    ori_shape_key_mutes = []
    if obj and obj.data and obj.data.shape_keys:
        for kb in obj.data.shape_keys.key_blocks:
            ori_shape_key_mutes.append(kb.mute)
            kb.mute = True

    return ori_shape_key_mutes

def recover_shape_key_mutes(obj, ori_shape_key_mutes):
    for i, val in enumerate(ori_shape_key_mutes):
        obj.data.shape_keys.key_blocks[i].mute = val

def bake_multires_image(obj, image, uv_name, intensity=1.0, flip_yz=False):

    context = bpy.context
    scene = context.scene
    mat = obj.active_material

    # Get multires modifier
    multires = get_multires_modifier(obj)
    if not multires: return

    # NOTE: Native baking on mesh with simple subsurf currently produces wrong result (tested in Feb 2026)
    subsurf = get_subsurf_modifier(obj)
    is_simple_subdivision = subsurf.subdivision_type == 'SIMPLE' if subsurf else False

    # Blender 5.0 introduce native VDM baking from multires
    native_baking = is_bl_newer_than(5) and not is_simple_subdivision

    # Get combined but active layer disabled image
    layer_disabled_vdm_image = None
    node = get_active_ypaint_node(obj)
    if node:
        yp = node.node_tree.yp
        if is_multi_disp_used(yp):
            # NOTE: Non-native baking need flipped YZ
            layer_disabled_vdm_image = get_combined_vdm_image(obj, uv_name, width=image.size[0], height=image.size[1], disable_current_layer=True, flip_yz=not native_baking)

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

    # Disable use simplify before apply modifier
    ori_use_simplify = scene.render.use_simplify
    scene.render.use_simplify = False

    # Mute all shape keys
    ori_shape_key_mutes = mute_all_shape_keys(obj)

    # Remember multires levels
    ori_multires_levels = multires.levels

    temp0 = temp1 = temp2 = None
    tanimage = bitimage = None
    temp_mat = None
    tex = None
    if native_baking:
        bake_type = 'VECTOR_DISPLACEMENT'
        bake_obj = obj

        # Target image
        tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = image
        mat.node_tree.nodes.active = tex

        # Need to set the multires level to 0 to make this work
        multires.levels = 0

    else:

        # Temp object 0: Base
        temp0 = obj.copy()
        link_object(scene, temp0)
        temp0.data = temp0.data.copy()
        temp0.location = obj.location + Vector(((obj.dimensions[0] + 0.1) * 1, 0.0, 0.0))     

        bake_type = 'EMIT'
        bake_obj = temp0

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
        temp2.location = obj.location + Vector(((obj.dimensions[0] + 0.1) * 3, 0.0, 0.0))
        
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
            temp1.location = obj.location + Vector(((obj.dimensions[0] + 0.1) * 2, 0.0, 0.0))
            set_active_object(temp1)

            vdm_loader = get_vdm_loader_geotree(uv_name, layer_disabled_vdm_image, tanimage, bitimage)
            bpy.ops.object.modifier_add(type='NODES')
            geomod = temp1.modifiers[-1]
            geomod.node_group = vdm_loader
            temp1.modifiers.active = geomod
            set_modifier_input_value(geomod, 'Flip Y/Z', False)

            # Apply geomod
            bpy.ops.object.modifier_apply(modifier=geomod.name)

            # Remove vdm loader group
            bpy.data.node_groups.remove(vdm_loader)

        # Calculate offset from two temp objects
        att, max_value = get_offset_attributes(temp0, temp2, temp1, intensity)

        # Set material to temp object 0
        temp0.data.materials.clear()
        # NOTE: Flipping YZ is unintuitively necessary when the layer is not flipped
        temp_mat = get_offset_bake_mat(uv_name, target_image=image, bitangent_image=bitimage, flip_yz=not flip_yz)
        temp0.data.materials.append(temp_mat)

    # Bake preparations
    book = _remember_before_bake(obj)
    _prepare_bake_settings(book, bake_obj, uv_name, bake_type=bake_type)

    # Bake offest
    print('INFO: Baking vdm...')
    if native_baking: bpy.ops.object.bake_image()
    else: bpy.ops.object.bake()
    print('INFO: Baking vdm is finished!')

    # Extra pass for native baking
    if native_baking:
        extra_pass = flip_yz or intensity != 1.0 or layer_disabled_vdm_image
        if extra_pass:

            mat_out = get_material_output(mat, create_one=True)
            ori_bsdf = mat_out.inputs[0].links[0].from_socket

            emit = mat.node_tree.nodes.new('ShaderNodeEmission')
            separate_xyz = None
            combine_xyz = None
            divider = None
            layer_disabled_tex = None
            subtractor = None

            # Copy image
            pixels = list(image.pixels)
            image_copy = image.copy()
            image_copy.pixels = pixels

            source_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
            source_tex.image = image_copy

            vec = source_tex.outputs[0]

            if layer_disabled_vdm_image:
                layer_disabled_tex = mat.node_tree.nodes.new('ShaderNodeTexImage')
                layer_disabled_tex.image = layer_disabled_vdm_image

                subtractor = mat.node_tree.nodes.new('ShaderNodeVectorMath')
                subtractor.operation = 'SUBTRACT'

                mat.node_tree.links.new(vec, subtractor.inputs[0])
                mat.node_tree.links.new(layer_disabled_tex.outputs[0], subtractor.inputs[1])
                vec = subtractor.outputs[0]

            if flip_yz:
                separate_xyz = mat.node_tree.nodes.new('ShaderNodeSeparateXYZ')
                combine_xyz = mat.node_tree.nodes.new('ShaderNodeCombineXYZ')

                mat.node_tree.links.new(vec, separate_xyz.inputs[0])
                mat.node_tree.links.new(separate_xyz.outputs[0], combine_xyz.inputs[0])
                mat.node_tree.links.new(separate_xyz.outputs[1], combine_xyz.inputs[2])
                mat.node_tree.links.new(separate_xyz.outputs[2], combine_xyz.inputs[1])
                vec = combine_xyz.outputs[0]

            if intensity != 1.0 or intensity != 0.0:
                divider = mat.node_tree.nodes.new('ShaderNodeVectorMath')
                divider.operation = 'DIVIDE'
                divider.inputs[1].default_value = (intensity, intensity, intensity)

                mat.node_tree.links.new(vec, divider.inputs[0])
                vec = divider.outputs[0]

            mat.node_tree.links.new(vec, emit.inputs[0])
            mat.node_tree.links.new(emit.outputs[0], mat_out.inputs[0])

            # Set bake type
            scene.cycles.bake_type = 'EMIT'

            # Bake
            print('INFO: Baking extra pass for vdm...')
            bpy.ops.object.bake()
            print('INFO: Baking extra pass for vdm is finished!')

            # Remove bake nodes
            if separate_xyz: simple_remove_node(mat.node_tree, separate_xyz)
            if combine_xyz: simple_remove_node(mat.node_tree, combine_xyz)
            if divider: simple_remove_node(mat.node_tree, divider)
            if layer_disabled_tex: simple_remove_node(mat.node_tree, layer_disabled_tex, remove_data=False)
            if subtractor: simple_remove_node(mat.node_tree, subtractor)
            simple_remove_node(mat.node_tree, emit)
            simple_remove_node(mat.node_tree, source_tex, remove_data=True)

            # Recover original bsdf
            mat.node_tree.links.new(ori_bsdf, mat_out.inputs[0])

    # HACK: Native baking need the image to be reloaded
    if native_baking and (image.packed_file or image.filepath == ''):
        image.pack()
        image.reload()

    # Recover bake settings
    _recover_bake_settings(book, True) 

    # Remove temp data
    if temp0: remove_mesh_obj(temp0)
    if temp2: remove_mesh_obj(temp2)
    if temp1: remove_mesh_obj(temp1)
    #if tanimage: bpy.data.images.remove(tanimage)
    #if bitimage: bpy.data.images.remove(bitimage)
    if layer_disabled_vdm_image:
        bpy.data.images.remove(layer_disabled_vdm_image)

    # Remove material
    if temp_mat and temp_mat.users <= 1: bpy.data.materials.remove(temp_mat, do_unlink=True)
    if mat and tex: mat.node_tree.nodes.remove(tex)

    # Recover disabled modifiers
    for mod in obj.modifiers:
        if mod.name in ori_mod_show_viewport:
            mod.show_viewport = True
        if mod.name in ori_mod_show_render:
            mod.show_render = True

    # Recover multires levels
    if multires.levels != ori_multires_levels:
        multires.levels = ori_multires_levels

    # Recover shape keys
    recover_shape_key_mutes(obj, ori_shape_key_mutes)

    # Recover use simplify
    if ori_use_simplify: scene.render.use_simplify = True

    # Set back object to active
    set_active_object(obj)
    set_object_select(obj, True)

def get_combined_vdm_image(obj, uv_name, width=1024, height=1024, disable_current_layer=False, flip_yz=False, only_vdms=False):
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

    # Remember all layers enable
    ori_layer_enables = []
    for l in yp.layers:
        ori_layer_enables.append(l.enable)

    # Disable current layer
    if disable_current_layer:
        cur_layer.enable = False

    # Disable other than vdm layers
    if only_vdms:
        for l in yp.layers:
            height_ch = get_height_channel(l)
            if not height_ch or not height_ch.enable or height_ch.normal_map_type != 'VECTOR_DISPLACEMENT_MAP': continue
            height_ch.vdisp_enable_flip_yz = not height_ch.vdisp_enable_flip_yz

        for l in yp.layers:
            height_ch = get_height_channel(l)
            if not height_ch or not height_ch.enable: continue
            if height_ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':

                # Flip flip Y/Z
                if flip_yz:
                    height_ch.vdisp_enable_flip_yz = not height_ch.vdisp_enable_flip_yz

            # Disable layer other than VDM
            elif only_vdms and l.type != 'GROUP':
                l.enable = False

    # Make sure vdm output exists
    if not height_root_ch.enable_subdiv_setup:
        check_all_channel_ios(yp, force_height_io=True)

    # Combined VDM image name
    if disable_current_layer:
        image_name = obj.name + '_' + uv_name + TEMP_LAYER_DISABLED_VDM_IMAGE_SUFFIX
    else: image_name = obj.name + '_' + uv_name + TEMP_COMBINED_VDM_IMAGE_SUFFIX

    # Create combined vdm image
    image = bpy.data.images.new(
        name=image_name, width=width, height=height,
        alpha=False, float_buffer=True
    )
    image.generated_color = (0, 0, 0, 1)

    # Get output node and remember original bsdf input
    mat_out = get_material_output(mat, create_one=True)
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

    # Recover layer enables
    for i, l in enumerate(yp.layers):
        if l.enable != ori_layer_enables[i]:
            l.enable = ori_layer_enables[i]

    # Recover input outputs
    if not height_root_ch.enable_subdiv_setup:
        check_all_channel_ios(yp)

    # Recover flip yzs
    if flip_yz:
        for i, l in enumerate(yp.layers):
            height_ch = get_height_channel(l)
            if not height_ch or not height_ch.enable or height_ch.normal_map_type != 'VECTOR_DISPLACEMENT_MAP': continue
            height_ch.vdisp_enable_flip_yz = not height_ch.vdisp_enable_flip_yz

    # Recover sculpt mode
    if ori_sculpt_mode:
        yp.sculpt_mode = True

    # Revover bake settings
    _recover_bake_settings(book, True)

    return image

def get_tangent_bitangent_images(obj, uv_name):

    tanimage_name = obj.name + '_' + uv_name + CACHE_TANGENT_IMAGE_SUFFIX
    bitimage_name = obj.name + '_' + uv_name + CACHE_BITANGENT_IMAGE_SUFFIX

    tanimage = bpy.data.images.get(tanimage_name)
    bitimage = bpy.data.images.get(bitimage_name)

    # Check mesh hash
    hash_invalid = False
    mh = get_mesh_hash(obj)
    if obj.yp.mesh_hash != mh:
        obj.yp.mesh_hash = mh
        hash_invalid = True
        #print('Hash invalid because of vertices')

    # Check uv hash
    hash_str = get_uv_hash(obj, uv_name)
    uvh = obj.yp.uv_hashes.get(uv_name)
    if not uvh or uvh.uv_hash != hash_str:

        if not uvh:
            uvh = obj.yp.uv_hashes.add()
            uvh.name = uv_name
        uvh.uv_hash = hash_str

        hash_invalid = True
        #print('Hash invalid because of UV')

    # Remove current images if hash doesn't match
    if hash_invalid:
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
        temp.location += Vector(((obj.dimensions[0] + 0.1) * 1, 0.0, 0.0))     

        # Remove shape keys
        if temp.data.shape_keys: bpy.ops.object.shape_key_remove(all=True)

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
            tanimage = bpy.data.images.new(
                name=tanimage_name, width=1024, height=1024,
                alpha=False, float_buffer=True
            )
            tanimage.generated_color = (0, 0, 0, 1)

            # Set bake tangent material
            temp.data.materials.clear()
            mat = get_tangent_bake_mat(uv_name, target_image=tanimage)
            temp.data.materials.append(mat)   

            # Bake tangent
            bpy.ops.object.bake()

            # Remove temp mat
            if mat.users <= 1: bpy.data.materials.remove(mat, do_unlink=True)

        if not bitimage:

            bitimage = bpy.data.images.new(
                name=bitimage_name, width=1024, height=1024,
                alpha=False, float_buffer=True
            )
            bitimage.generated_color = (0, 0, 0, 1)

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
        tanimage.use_fake_user = True
        bitimage.use_fake_user = True

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
        if (not hch or not hch.enable
            or hch.normal_map_type not in {'BUMP_MAP', 'BUMP_NORMAL_MAP', 'VECTOR_DISPLACEMENT_MAP'} 
            or (not hch.write_height and hch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'})
        ): continue
        num_disps += 1

    return num_disps > 1

def convert_vdm_to_multires(obj, vdm_image, uv_name, intensity=1.0, flip_yz=False, use_temp_multires=False):
    # TODO: Multi objects awareness

    scene = bpy.context.scene

    # Remember active object
    ori_active = get_active_object()

    # Disable other modifiers
    ori_show_viewports = {}
    ori_show_renders = {}
    for m in obj.modifiers:
        if m.type not in {'SUBSURF', 'MULTIRES'}:
            ori_show_viewports[m.name] = m.show_viewport
            ori_show_renders[m.name] = m.show_render
            m.show_viewport = False
            m.show_render = False

    # Bake tangent and bitangent first
    tanimage, bitimage = get_tangent_bitangent_images(obj, uv_name)

    # Create a temporary object
    temp = obj.copy()
    link_object(scene, temp)
    temp.data = temp.data.copy()
    temp.location += Vector(((obj.dimensions[0] + 0.1) * 1, 0.0, 0.0))     

    # Select temp object
    set_active_object(temp)
    set_object_select(temp, True)

    # Remove shape keys
    if temp.data.shape_keys: bpy.ops.object.shape_key_remove(all=True)

    # Create geometry nodes to load vdm
    vdm_loader = get_vdm_loader_geotree(uv_name, vdm_image, tanimage, bitimage, intensity)
    bpy.ops.object.modifier_add(type='NODES')
    geomod = temp.modifiers[-1]
    geomod.node_group = vdm_loader
    temp.modifiers.active = geomod

    # Set flip Y/Z
    set_modifier_input_value(geomod, 'Flip Y/Z', flip_yz)

    # Set active object
    set_active_object(obj)

    # Add multires modifier
    multires = get_multires_modifier(obj)
    if not multires:
        bpy.ops.object.modifier_add(type='MULTIRES')
        multires = [m for m in obj.modifiers if m.type == 'MULTIRES'][0]
        if use_temp_multires:
            multires.name = TEMP_MULTIRES_NAME

    # Disable subsurf
    subsurf = get_subsurf_modifier(obj)
    if subsurf:
        subsurf.show_viewport = False
        subsurf.show_render = False
        levels = subsurf.levels
        subdiv_type = subsurf.subdivision_type
    else:
        if multires.total_levels != 0:
            levels = multires.total_levels
        else:
            node = get_active_ypaint_node()
            height_root_ch = None
            if node:
                yp = node.node_tree.yp
                height_root_ch = get_root_height_channel(yp)

            # Get maximum polygon settings from normal channel
            if height_root_ch:
                max_polys = height_root_ch.subdiv_on_max_polys * 1000
            else: max_polys = 1000000

            num_poly = len(obj.data.polygons)
            levels = int(math.log(max_polys / num_poly, 4))

        subdiv_type = 'SIMPLE' if is_mesh_flat_shaded(obj.data) else 'CATMULL_CLARK'

        # Make sure temp object has subsurf modifier so reshape can happen
        set_active_object(temp)
        bpy.ops.object.modifier_add(type='SUBSURF')
        tsubsurf = get_subsurf_modifier(temp)
        tsubsurf.levels = levels
        tsubsurf.render_levels = levels
        if is_mesh_flat_shaded(obj.data):
            tsubsurf.subdivision_type = 'SIMPLE'
        set_active_object(obj)

    # Set to max levels
    multires.show_viewport = True
    multires.show_render = True
    for i in range(levels-multires.total_levels):
        bpy.ops.object.multires_subdivide(modifier=multires.name, mode=subdiv_type)      
    multires.levels = multires.total_levels
    multires.sculpt_levels = multires.total_levels
    multires.render_levels = multires.total_levels

    # Disable use simplify before reshape
    ori_use_simplify = scene.render.use_simplify
    scene.render.use_simplify = False

    # Mute all shape keys before reshape
    ori_shape_key_mutes = mute_all_shape_keys(obj)

    # Reshape multires
    bpy.ops.object.multires_reshape(modifier=multires.name)

    # Recover use simplify
    if ori_use_simplify: scene.render.use_simplify = True

    # Recover shape keys
    recover_shape_key_mutes(obj, ori_shape_key_mutes)

    # Remove subsurf if multires isn't temporary
    if subsurf and not use_temp_multires:
        bpy.ops.object.modifier_remove(modifier=subsurf.name)

    # Enable some modifiers again
    for mod_name, ori_show_viewport in ori_show_viewports.items():
        m = obj.modifiers.get(mod_name)
        if m: m.show_viewport = ori_show_viewport
    for mod_name, ori_show_render in ori_show_renders.items():
        m = obj.modifiers.get(mod_name)
        if m: m.show_render = ori_show_render  

    # Recover active object
    set_active_object(ori_active)

    # Remove temp data
    remove_mesh_obj(temp) 
    bpy.data.node_groups.remove(vdm_loader)

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

        if mapping and is_transformed(mapping, layer):
            self.report({'ERROR'}, "Cannot sculpt VDM with transformed mapping!")
            return {'CANCELLED'}

        # Get combined VDM image
        combined_vdm_image = None
        if is_multi_disp_used(yp):
            combined_vdm_image = get_combined_vdm_image(obj, uv_name, width=image.size[0], height=image.size[1])

        # Enable sculpt mode to disable all vector displacement layers
        yp.sculpt_mode = True

        # Mirror modifier with mirror U will be temporarily applied
        apply_mirror_modifier(obj)

        # Use combined sculpt image when there's more than one displacement layers
        if combined_vdm_image:
            sculpt_image = combined_vdm_image
            intensity = 1.0
            # NOTE: Geometry nodes need YZ flipped displacement
            flip_yz = True
        else: 
            sculpt_image = image
            height_ch = get_height_channel(layer)
            intensity = get_vdm_intensity(layer, height_ch) if height_ch else 1.0
            flip_yz = not height_ch.vdisp_enable_flip_yz

        # Create object copy with VDM loader geometry nodes
        convert_vdm_to_multires(obj, sculpt_image, uv_name, intensity=intensity, flip_yz=flip_yz, use_temp_multires=True)

        if combined_vdm_image:
            bpy.data.images.remove(combined_vdm_image)

        # Set armature to the top
        arm, arm_idx = get_armature_modifier(obj, return_index=True)
        if arm: 
            # Remember original armature index
            obj.yp_vdm.armature_index = arm_idx-1
            bpy.ops.object.modifier_move_to_index(modifier=arm.name, index=0)

        # Unhide object if it's hidden
        if get_object_hide(obj):
            set_object_hide(obj, False)

        bpy.ops.object.mode_set(mode='SCULPT')

        self.report({'INFO'}, 'Sculpt mode is entered in '+'{:0.2f}'.format(time.time() - T)+' seconds!')

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
            flip_yz = height_ch.vdisp_enable_flip_yz

            # Bake multires image
            bake_multires_image(obj, image, uv_name, intensity, flip_yz=flip_yz)

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

        # Recover mirror modifier
        recover_mirror_modifier(obj)

        # Recover armature index
        arm = get_armature_modifier(obj)
        if arm: bpy.ops.object.modifier_move_to_index(modifier=arm.name, index=obj.yp_vdm.armature_index)

        # Go back to material view
        space = bpy.context.space_data
        if space.type == 'VIEW_3D' and space.shading.type not in {'MATERIAL', 'RENDERED'}:
            space.shading.type = 'MATERIAL'

        self.report({'INFO'}, 'Applying sculpt to VDM is done in '+'{:0.2f}'.format(time.time() - T)+' seconds!')

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

        # Recover mirror modifier
        recover_mirror_modifier(obj)

        # Recover armature index
        arm = get_armature_modifier(obj)
        if arm: bpy.ops.object.modifier_move_to_index(modifier=arm.name, index=obj.yp_vdm.armature_index)

        # Go back to material view
        space = bpy.context.space_data
        if space.type == 'VIEW_3D' and space.shading.type not in {'MATERIAL', 'RENDERED'}:
            space.shading.type = 'MATERIAL'

        return {'FINISHED'}

class YRemoveVDMandAddMultires(bpy.types.Operator):
    bl_idname = "object.y_remove_vdm_and_add_multires"
    bl_label = "Apply VDM layers to Multires"
    bl_description = "Apply all VDM layers a single multires modifier.\nThis will remove all VDM layers"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=240)

    def draw(self, context):
        self.layout.alert = True
        self.layout.label(text='This will remove all VDM layers and', icon='ERROR')
        self.layout.label(text='apply them to a multires modifer', icon='BLANK1')

    def execute(self, context):
        obj = context.object
        scene = context.scene
        node = get_active_ypaint_node()
        tree = node.node_tree
        yp = tree.yp
        mat = get_active_material()

        vdm_layers, vdm_layer_ids = get_all_vdm_layers(yp, return_index=True)

        if len(vdm_layers) == 0:
            self.report({'ERROR'}, "No VDM layer found!")
            return {'CANCELLED'}

        if mat.users > 1:
            self.report({'ERROR'}, "Currently only works with a single object material!")
            return {'CANCELLED'}

        uv_name = vdm_layers[0].uv_name

        source = get_layer_source(vdm_layers[0])
        if not source or not source.image or source.image.size[0] == 0:
            self.report({'ERROR'}, "Invalid/Missing VDM image!")
            return {'CANCELLED'}
        height_ch = get_height_channel(vdm_layers[0])
        flip_yz = not height_ch.vdisp_enable_flip_yz if height_ch else True

        vdm_image = source.image

        if len(vdm_layers) > 1:
            # TODO: Use the highest resolution vdm image as the bake resolution
            vdm_image = get_combined_vdm_image(obj, uv_name, width=vdm_image.size[0], height=vdm_image.size[1], flip_yz=True, only_vdms=True)
            flip_yz = True

        # Convert all vdm layers to multires modifier
        convert_vdm_to_multires(obj, vdm_image, uv_name, flip_yz=flip_yz)

        # Remember before removing layers
        parent_dict = get_parent_dict(yp)
        index_dict = get_index_dict(yp)

        # Remove all vdm layers
        for i, l in reversed(list(enumerate(yp.layers))):
            if i in vdm_layer_ids:
                l = yp.layers[i]
                remove_entity_fcurves(l)
                Layer.remove_layer(yp, i)

        # Remove tangent and bitangent images since they're no longer useful
        tanimage, bitimage = get_tangent_bitangent_images(obj, uv_name)
        if tanimage: remove_datablock(bpy.data.images, tanimage)
        if bitimage: remove_datablock(bpy.data.images, bitimage)

        # Remap parents
        for lay in yp.layers:
            lay.parent_idx = get_layer_index_by_name(yp, parent_dict[lay.name])

        # Remap fcurves
        remap_layer_fcurves(yp, index_dict)

        # Check uv maps
        check_uv_nodes(yp)

        # Reconnect
        check_start_end_root_ch_nodes(tree)
        reconnect_yp_nodes(tree)
        rearrange_yp_nodes(tree)

        # Update UI
        bpy.context.window_manager.ypui.need_update = True

        # Refresh normal map
        yp.refresh_tree = True

        # Update list items
        ListItem.refresh_list_items(yp, repoint_active=True)

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

class YPaintVDMObjectProps(bpy.types.PropertyGroup):
    num_verts : IntProperty(default=0)
    mirror_modifier_name : StringProperty(default='')
    armature_index : IntProperty(default=0)

def register():
    bpy.utils.register_class(YSculptImage)
    bpy.utils.register_class(YApplySculptToImage)
    bpy.utils.register_class(YCancelSculptToImage)
    bpy.utils.register_class(YRemoveVDMandAddMultires)
    bpy.utils.register_class(YFixVDMMismatchUV)
    bpy.utils.register_class(YPaintVDMObjectProps)

    bpy.types.Object.yp_vdm = PointerProperty(type=YPaintVDMObjectProps)

def unregister():
    bpy.utils.unregister_class(YSculptImage)
    bpy.utils.unregister_class(YApplySculptToImage)
    bpy.utils.unregister_class(YCancelSculptToImage)
    bpy.utils.unregister_class(YRemoveVDMandAddMultires)
    bpy.utils.unregister_class(YFixVDMMismatchUV)
    bpy.utils.unregister_class(YPaintVDMObjectProps)
