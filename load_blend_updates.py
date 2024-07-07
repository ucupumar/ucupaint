import bpy, time
from .common import *
from .subtree import *
from .lib import *
from mathutils import *
from bpy.app.handlers import persistent
from distutils.version import LooseVersion #, StrictVersion
from .node_arrangements import *
from .node_connections import *
from .input_outputs import *
from . import Bake

def flip_tangent_sign():
    meshes = []

    for obj in bpy.data.objects:
        if obj.type == 'MESH' and obj.data not in meshes:
            meshes.append(obj.data)
            for vc in get_vertex_colors(obj):
                if vc.name.startswith(TANGENT_SIGN_PREFIX):

                    i = 0
                    for poly in obj.data.polygons:
                        for idx in poly.loop_indices:
                            vert = obj.data.loops[idx]
                            col = vc.data[i].color
                            if is_greater_than_280():
                                vc.data[i].color = (1.0-col[0], 1.0-col[1], 1.0-col[2], 1.0)
                            else: vc.data[i].color = (1.0-col[0], 1.0-col[1], 1.0-col[2])
                            i += 1

def get_lib_revision(tree):
    rev = tree.nodes.get('revision')

    # Check lib tree revision
    if rev:
        m = re.match(r'.*(\d)', rev.label)
        try: revision = int(m.group(1))
        except: revision = 0
    else: revision = 0

    return revision

def convert_mix_nodes(tree):
    for n in tree.nodes:
        if n.bl_idname == 'ShaderNodeMixRGB':
            nn = simple_new_mix_node(tree)
            name = n.name

            inp = n.inputs[0]
            for l in inp.links:
                create_link(tree, l.from_socket, nn.inputs[0])
            nn.inputs[0].default_value = inp.default_value

            inp = n.inputs[1]
            for l in inp.links:
                create_link(tree, l.from_socket, nn.inputs[6])
            nn.inputs[6].default_value = inp.default_value

            inp = n.inputs[2]
            for l in inp.links:
                create_link(tree, l.from_socket, nn.inputs[7])
            nn.inputs[7].default_value = inp.default_value

            outp = n.outputs[0]
            for l in outp.links:
                create_link(tree, nn.outputs[2], l.to_socket)

            nn.location = n.location
            nn.label = n.label
            nn.blend_type = n.blend_type
            nn.clamp_result = n.use_clamp
            nn.parent = n.parent

            simple_remove_node(tree, n)
            nn.name = name

        elif n.type == 'GROUP' and n.node_tree:
            convert_mix_nodes(n.node_tree)

def remove_tangent_sign_vcols(objs=None):
    if not objs: objs = bpy.data.objects

    for ob in objs:
        vcols = get_vertex_colors(ob)
        for vcol in reversed(vcols):
            if vcol.name.startswith(TANGENT_SIGN_PREFIX):
                print('INFO:', 'Vertex color "' + vcol.name + '" in', ob.name, 'is deleted!')
                vcols.remove(vcol)

def update_tangent_process(tree, lib_name):

    node_groups = []

    for node in tree.nodes:
        if node.type == 'GROUP' and node.node_tree and node.node_tree.name.startswith(TANGENT_PROCESS):
            node_groups.append(node)

    for ng in node_groups:

        # Remember original tree
        ori_tree = ng.node_tree

        # Duplicate lib tree
        ng.node_tree = get_node_tree_lib(lib_name)
        duplicate_lib_node_tree(ng)

        print('INFO:', ori_tree.name, 'is replaced to', ng.node_tree.name + '!')

        # Copy some nodes inside
        for n in ng.node_tree.nodes:
            if n.name.startswith('_'):
                # Try to get the node on original tree
                ori_n = ori_tree.nodes.get(n.name)
                if ori_n: 
                    copy_node_props(ori_n, n)
                    # There's need to manually copy uv_map prop because the node type can be different
                    if hasattr(ori_n, 'uv_map') and hasattr(n, 'uv_map'):
                        n.uv_map = ori_n.uv_map

        # Delete original tree
        bpy.data.node_groups.remove(ori_tree)

        # Create info frames
        create_info_nodes(ng.node_tree)

def update_yp_tree(tree):
    cur_version = get_current_version_str()
    yp = tree.yp

    updated_to_tangent_process_300 = False
    updated_to_yp_200_displacement = False

    # SECTION I: Update based on yp version

    # Version 0.9.1 and above will fix wrong bake type stored on images bake type
    if LooseVersion(yp.version) < LooseVersion('0.9.1'):
        #print(cur_version)
        for layer in yp.layers:
            if layer.type == 'IMAGE':
                source = get_layer_source(layer)

                if source.image and source.image.y_bake_info.is_baked:
                    #print(source.image)
                    for type_name, label in bake_type_suffixes.items():
                        if label in source.image.name and source.image.y_bake_info.bake_type != type_name:
                            source.image.y_bake_info.bake_type = type_name
                            print('INFO: Bake type of', source.image.name, 'is fixed by setting it to', label + '!')

    # Version 0.9.2 and above will move mapping outside source group
    if LooseVersion(yp.version) < LooseVersion('0.9.2'):

        for layer in yp.layers:
            ltree = get_tree(layer)

            mapping_replaced = False

            # Move layer mapping
            if layer.source_group != '':
                group = ltree.nodes.get(layer.source_group)
                if group:
                    mapping_ref = group.node_tree.nodes.get(layer.mapping)
                    if mapping_ref:
                        mapping = new_node(ltree, layer, 'mapping', 'ShaderNodeMapping')
                        copy_node_props(mapping_ref, mapping)
                        group.node_tree.nodes.remove(mapping_ref)
                        set_uv_neighbor_resolution(layer) #, mapping=mapping)
                        mapping_replaced = True
                        print('INFO: Mapping of', layer.name, 'is moved out!')

            # Move mask mapping
            for mask in layer.masks:
                if mask.group_node != '':
                    group = ltree.nodes.get(mask.group_node)
                    if group:
                        mapping_ref = group.node_tree.nodes.get(mask.mapping)
                        if mapping_ref:
                            mapping = new_node(ltree, mask, 'mapping', 'ShaderNodeMapping')
                            copy_node_props(mapping_ref, mapping)
                            group.node_tree.nodes.remove(mapping_ref)
                            set_uv_neighbor_resolution(mask) #, mapping=mapping)
                            mapping_replaced = True
                            print('INFO: Mapping of', mask.name, 'is moved out!')

            if mapping_replaced:
                reconnect_layer_nodes(layer)
                rearrange_layer_nodes(layer)

    # Version 0.9.3 and above will replace override color modifier with newer override system
    if LooseVersion(yp.version) < LooseVersion('0.9.3'):

        for layer in yp.layers:
            for i, ch in enumerate(layer.channels):
                root_ch = yp.channels[i]
                mod_ids = []
                for j, mod in enumerate(ch.modifiers):
                    if mod.type == 'OVERRIDE_COLOR':
                        mod_ids.append(j)

                for j in reversed(mod_ids):
                    mod = ch.modifiers[j]
                    mtree = get_mod_tree(ch)

                    ch.override = True
                    if root_ch.type == 'VALUE':
                        ch.override_value = mod.oc_val
                    else:
                        ch.override_color = (mod.oc_col[0], mod.oc_col[1], mod.oc_col[2])

                    if ch.override_type != 'DEFAULT':
                        ch.override_type = 'DEFAULT'

                    # Delete the nodes and modifier
                    remove_node(mtree, mod, 'oc')
                    ch.modifiers.remove(j)

                if mod_ids:

                    # Update input value for version 2.0+
                    if cur_version >= LooseVersion('2.0.0'):
                        if root_ch.type == 'VALUE':
                            set_entity_prop_value(ch, 'override_value', ch.override_value)
                        else: set_entity_prop_value(ch, 'override_color', ch.override_color)

                    reconnect_layer_nodes(layer)
                    rearrange_layer_nodes(layer)

    # Version 0.9.4 and above will replace multipier modifier with math modifier
    if LooseVersion(yp.version) < LooseVersion('0.9.4'):

        mods = []
        parents = []
        types = []

        for channel in yp.channels:
            channel_tree = get_mod_tree(channel)
            for mod in channel.modifiers:
                if mod.type == 'MULTIPLIER' :
                    mods.append(mod)
                    parents.append(channel)
                    types.append(channel.type)

        for layer in yp.layers:
            layer_tree = get_mod_tree(layer)
            for mod in layer.modifiers:
                if mod.type == 'MULTIPLIER' :
                    mods.append(mod)
                    parents.append(layer)
                    types.append('RGB')

            for i, ch in enumerate(layer.channels):
                root_ch = yp.channels[i]
                ch_tree = get_mod_tree(ch)
                for j, mod in enumerate(ch.modifiers):
                    if mod.type == 'MULTIPLIER' :
                        mods.append(mod)
                        parents.append(ch)
                        types.append(root_ch.type)

        for i, mod in enumerate(mods):
            parent = parents[i]
            ch_type = types[i]

            mtree = get_mod_tree(parent)

            mod.name = 'Math'
            mod.type = 'MATH'
            remove_node(mtree, mod, 'multiplier')
            math = new_node(mtree, mod, 'math', 'ShaderNodeGroup', 'Math')

            if ch_type == 'VALUE':
                math.node_tree = get_node_tree_lib(MOD_MATH_VALUE)
            else:
                math.node_tree = get_node_tree_lib(MOD_MATH)
            
            duplicate_lib_node_tree(math)

            mod.affect_alpha = True
            math.node_tree.nodes.get('Mix.A').mute = False

            mod.math_a_val = mod.multiplier_a_val
            mod.math_r_val = mod.multiplier_r_val
            math.node_tree.nodes.get('Math.R').use_clamp = mod.use_clamp
            math.node_tree.nodes.get('Math.A').use_clamp = mod.use_clamp
            if ch_type != 'VALUE':
                mod.math_g_val = mod.multiplier_g_val
                mod.math_b_val = mod.multiplier_b_val
                math.node_tree.nodes.get('Math.G').use_clamp = mod.use_clamp
                math.node_tree.nodes.get('Math.B').use_clamp = mod.use_clamp

        if mods:
            for layer in yp.layers:
                reconnect_layer_nodes(layer)
                rearrange_layer_nodes(layer)
            reconnect_yp_nodes(tree)
            rearrange_yp_nodes(tree)

    # Version 0.9.5 and above have ability to use vertex color alpha on layer
    if LooseVersion(yp.version) < LooseVersion('0.9.5'):

        for layer in yp.layers:
            # Update vcol layer to use alpha by reconnection
            if layer.type == 'VCOL':

                # Smooth bump channel need another fake neighbor for alpha
                smooth_bump_ch = get_smooth_bump_channel(layer)
                if smooth_bump_ch and smooth_bump_ch.enable:
                    layer_tree = get_tree(layer)
                    uv_neighbor_1 = replace_new_node(layer_tree, layer, 'uv_neighbor_1', 'ShaderNodeGroup', 'Neighbor UV 1', 
                            NEIGHBOR_FAKE, hard_replace=True)

                reconnect_layer_nodes(layer)
                rearrange_layer_nodes(layer)

    # Version 0.9.8 and above will use sRGB images by default
    if LooseVersion(yp.version) < LooseVersion('0.9.8'):

        for layer in yp.layers:
            if not layer.enable: continue

            image_found = False
            if layer.type == 'IMAGE':

                source = get_layer_source(layer)
                if source and source.image and not source.image.is_float: 
                    if source.image.colorspace_settings.name != 'sRGB':
                        source.image.colorspace_settings.name = 'sRGB'
                        print('INFO:', source.image.name, 'image is now using sRGB!')
                    check_layer_image_linear_node(layer)
                image_found = True

            for ch in layer.channels:
                if not ch.enable or not ch.override: continue

                if ch.override_type == 'IMAGE':

                    source = get_channel_source(ch)
                    if source and source.image and not source.image.is_float:
                        if source.image.colorspace_settings.name != 'sRGB':
                            source.image.colorspace_settings.name = 'sRGB'
                            print('INFO:', source.image.name, 'image is now using sRGB!')
                        check_layer_channel_linear_node(ch)
                    image_found = True

            for mask in layer.masks:
                if not mask.enable: continue

                if mask.type == 'IMAGE':
                    source = get_mask_source(mask)
                    if source and source.image and not source.image.is_float:
                        if source.image.colorspace_settings.name != 'sRGB':
                            source.image.colorspace_settings.name = 'sRGB'
                            print('INFO:', source.image.name, 'image is now using sRGB!')
                        check_mask_image_linear_node(mask)
                    image_found = True

            if image_found:
                rearrange_layer_nodes(layer)
                reconnect_layer_nodes(layer)

    # Version 0.9.9 have separate normal and bump override
    if LooseVersion(yp.version) < LooseVersion('0.9.9'):
        for layer in yp.layers:
            for i, ch in enumerate(layer.channels):
                root_ch = yp.channels[i]
                if root_ch.type == 'NORMAL' and ch.normal_map_type == 'NORMAL_MAP' and ch.override:

                    # Disable override first
                    ch.override = False

                    # Rename pointers
                    ch.cache_1_image = ch.cache_image

                    # Remove previous pointers
                    ch.cache_image = ''

                    # Copy props
                    ch.override_1_type = ch.override_type
                    ch.override_type = 'DEFAULT'

                    # Enable override
                    ch.override_1 = True

                    # Copy active edit
                    ch.active_edit_1 = ch.active_edit

                    print('INFO:', layer.name, root_ch.name, 'now has separate override properties!')

    # Version 1.0.11 will make sure divider alpha node is connected correctly
    if LooseVersion(yp.version) < LooseVersion('1.0.11'):
        for layer in yp.layers:
            if layer.type == 'VCOL':
                # Refresh divider alpha by setting the prop
                layer.divide_rgb_by_alpha = layer.divide_rgb_by_alpha

    # Version 1.2 will have mask inputs
    if LooseVersion(yp.version) < LooseVersion('1.2.0'):
        for layer in yp.layers:
            for mask in layer.masks:
                # Voronoi and noise default is using alpha/value input
                if mask.type in {'VORONOI', 'NOISE'}:
                    mask.source_input = 'ALPHA'

    # Version 1.2.4 has voronoi feature prop
    if LooseVersion(yp.version) < LooseVersion('1.2.4'):
        for layer in yp.layers:
            if layer.type == 'VORONOI':
                source = get_layer_source(layer)
                yp.halt_update = True
                layer.voronoi_feature = source.feature
                yp.halt_update = False

            for ch in layer.channels:
                if ch.override_type == 'VORONOI':
                    source = get_channel_source(ch)
                    if source:
                        yp.halt_update = True
                        ch.voronoi_feature = source.feature
                        yp.halt_update = False

                layer_tree = get_tree(layer)
                cache_voronoi = layer_tree.nodes.get(ch.cache_voronoi)
                if cache_voronoi:
                    yp.halt_update = True
                    ch.voronoi_feature = cache_voronoi.feature
                    yp.halt_update = False

            for mask in layer.masks:
                if mask.type == 'VORONOI':
                    source = get_mask_source(mask)
                    yp.halt_update = True
                    mask.voronoi_feature = source.feature
                    yp.halt_update = False

    # Version 1.2.5 fix end normal process
    if LooseVersion(yp.version) < LooseVersion('1.2.5'):
        height_root_ch = get_root_height_channel(yp)
        if height_root_ch:
            check_start_end_root_ch_nodes(tree, height_root_ch)
            reconnect_yp_nodes(tree)
            rearrange_yp_nodes(tree)

            for layer in yp.layers:
                height_ch = get_height_channel(layer)
                if height_ch and height_ch.enable:
                    reconnect_layer_nodes(layer)
                    rearrange_layer_nodes(layer)

    # Version 1.2.9 will use cubic interpolation for bump map
    if LooseVersion(yp.version) < LooseVersion('1.2.9'):
        height_root_ch = get_root_height_channel(yp)
        if height_root_ch:
            for layer in yp.layers:
                height_ch = get_height_channel(layer)
                if height_ch and height_ch.enable:
                    update_layer_images_interpolation(layer, 'Cubic')

    # Version 2.0 won't use custom prop for mapping and intensity
    if LooseVersion(yp.version) < LooseVersion('2.0.0'):

        # Update input outputs
        check_all_channel_ios(yp)

        height_root_ch = get_root_height_channel(yp)
        if height_root_ch and height_root_ch.enable_subdiv_setup:

            if height_root_ch.subdiv_adaptive:

                # Set max height value
                end_max_height = tree.nodes.get(height_root_ch.end_max_height)
                if end_max_height:
                    end_max_height.outputs[0].default_value /= 5.0

                # Set normal scale
                if height_root_ch.enable_smooth_bump:
                    height_root_ch.enable_smooth_normal_tweak = True
                    set_entity_prop_value(height_root_ch, 'smooth_normal_tweak', 5.0)

            # Set displacement method
            if not height_root_ch.subdiv_adaptive:
                mats = get_all_materials_with_tree(tree)
                for mat in mats:
                    if hasattr(mat, 'displacement_method'):
                        mat.displacement_method = 'BOTH'

                    if is_greater_than_280():
                        mat.cycles.displacement_method = 'BOTH'
                    else: mat.cycles.displacement_method = 'TRUE'

                # Update displacement connection
                Bake.check_subdiv_setup(height_root_ch)

                updated_to_yp_200_displacement = True

        for layer in yp.layers:

            # Update height distance since the scale is divided by 5 to match closer to blender bump node value
            if height_root_ch:
                height_ch = get_height_channel(layer)
                if height_ch:
                    if not yp.use_baked and not height_root_ch.enable_subdiv_setup:
                        set_entity_prop_value(height_ch, 'bump_distance', height_ch.bump_distance*5.0)
                        set_entity_prop_value(height_ch, 'normal_bump_distance', height_ch.normal_bump_distance*5.0)
                        set_entity_prop_value(height_ch, 'transition_bump_distance', height_ch.transition_bump_distance*5.0)
                    elif height_root_ch.subdiv_adaptive:
                        set_entity_prop_value(height_ch, 'bump_distance', height_ch.bump_distance/5.0)
                        set_entity_prop_value(height_ch, 'normal_bump_distance', height_ch.normal_bump_distance/5.0)
                        set_entity_prop_value(height_ch, 'transition_bump_distance', height_ch.transition_bump_distance/5.0)

            # Transfer channel intensity value to layer intensity value if there's only one enabled channel
            enabled_channels = [c for c in layer.channels if c.enable]
            if len(enabled_channels) == 1:
                ch = enabled_channels[0]
                ch_idx = get_layer_channel_index(layer, ch)
                root_ch = yp.channels[ch_idx]

                set_entity_prop_value(layer, 'intensity_value', ch.intensity_value)
                set_entity_prop_value(ch, 'intensity_value', 1.0)

                if len(ch.modifiers) == 0:
                    layer.expand_channels = False

                # Transfer fcurve
                if tree.animation_data and tree.animation_data.action:
                    fcs = tree.animation_data.action.fcurves
                    for fc in fcs:
                        m = re.match(r'yp\.layers\[(\d+)\]\.channels\[(\d+)\]\.intensity_value', fc.data_path)
                        if m:
                            mlayer = yp.layers[int(m.group(1))]
                            mch = mlayer.channels[int(m.group(2))]
                            if mch != ch: continue
                            fc.data_path = 'yp.layers[' + m.group(1) + '].intensity_value'

        # Subdiv tweak is no longer used
        height_root_ch = get_root_height_channel(yp)
        if height_root_ch and hasattr(height_root_ch, 'subdiv_tweak') and height_root_ch.subdiv_tweak != 1.0:
            height_root_ch.enable_height_tweak = True
            height_root_ch.height_tweak = height_root_ch.subdiv_tweak

        # Check for mapping actions
        if tree.animation_data and tree.animation_data.action:
            fcs = tree.animation_data.action.fcurves
            new_fcs = []
            for fc in fcs:
                #print(fc.data_path)

                # New fcurve
                nfc = None

                # Get entity
                mlayer = re.match(r'yp\.layers\[(\d+)\]\.+', fc.data_path)
                mmask = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]\.+', fc.data_path)

                if mlayer: entity = yp.layers[int(mlayer.group(1))]
                if mmask: entity = yp.layers[int(mmask.group(1))].masks[int(mmask.group(2))]

                # Match data path
                m1 = re.match(r'yp\.layers\[(\d+)\]\.translation', fc.data_path)
                m2 = re.match(r'yp\.layers\[(\d+)\]\.rotation', fc.data_path)
                m3 = re.match(r'yp\.layers\[(\d+)\]\.scale', fc.data_path)
                m4 = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]\.translation', fc.data_path)
                m5 = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]\.rotation', fc.data_path)
                m6 = re.match(r'yp\.layers\[(\d+)\]\.masks\[(\d+)\]\.scale', fc.data_path)

                # Mapping
                if m1 or m2 or m3 or m4 or m5 or m6:
                    mapping = get_entity_mapping(entity)
                    parent_node = mapping.id_data

                    # Translation
                    if m1 or m4:
                        if is_greater_than_281():
                            new_data_path = 'nodes["' + mapping.name + '"].inputs[1].default_value'
                        else: new_data_path = 'nodes["' + mapping.name + '"].translation'

                    # Rotation
                    elif m2 or m5:
                        if is_greater_than_281():
                            new_data_path = 'nodes["' + mapping.name + '"].inputs[2].default_value'
                        else: new_data_path = 'nodes["' + mapping.name + '"].rotation'

                    # Scale
                    else: #elif m3 or m6:
                        if is_greater_than_281():
                            new_data_path = 'nodes["' + mapping.name + '"].inputs[3].default_value'
                        else: new_data_path = 'nodes["' + mapping.name + '"].scale'

                    for i, kp in enumerate(fc.keyframe_points):

                        # Set current frame and value
                        #mapping.inputs[1].default_value[fc.array_index] = fc.evaluate(int(kp.co[0]))
                        bpy.context.scene.frame_set(int(kp.co[0]))
                        if m1 or m4: # Translation
                            mapping.inputs[1].default_value[fc.array_index] = entity.translation[fc.array_index]
                        elif m2 or m5: # Rotation
                            mapping.inputs[2].default_value[fc.array_index] = entity.rotation[fc.array_index]
                        elif m3 or m6: # Scale
                            mapping.inputs[3].default_value[fc.array_index] = entity.scale[fc.array_index]

                        # Insert keyframe
                        parent_node.keyframe_insert(data_path=new_data_path, frame=int(kp.co[0]))

                        # Get new fcurve
                        if not nfc:
                            nfc = [f for f in parent_node.animation_data.action.fcurves if f.data_path == new_data_path and f.array_index == fc.array_index][0]

                        # Get new keyframe point
                        nkp = nfc.keyframe_points[i]

                        # Copy keyframe props
                        copy_id_props(kp, nkp)

                new_fcs.append(nfc)

            for i, fc in reversed(list(enumerate(fcs))):

                # Get new fcurve
                nfc = new_fcs[i]
                if not nfc: continue

                # Copy modifiers
                for mod in fc.modifiers:
                    nmod = nfc.modifiers.new(type=mod.type)
                    copy_id_props(mod, nmod)

                # Copy fcurve props
                #copy_id_props(fc, nfc)
                nfc.mute = fc.mute
                nfc.hide = fc.hide
                nfc.extrapolation = fc.extrapolation
                nfc.lock = fc.lock

                # Remove original fcurve
                fcs.remove(fc)

    # SECTION II: Updates based on the blender version

    # Blender 2.92 can finally access it's vertex color alpha
    if is_greater_than_292() and (is_created_before_292() or LooseVersion(yp.blender_version) < LooseVersion('2.9.2')):
        show_message = False
        for layer in yp.layers:
            # Update vcol layer to use alpha by reconnection
            if layer.type == 'VCOL':
                reconnect_layer_nodes(layer)
                rearrange_layer_nodes(layer)
                show_message = True

        if show_message:
            print("INFO: Now " + get_addon_title() + " is capable to use vertex paint alpha since Blender 2.92, Enjoy!")

    # Blender 4.1 no longer has musgrave node
    if is_greater_than_410() and (is_created_before_410() or LooseVersion(yp.blender_version) < LooseVersion('4.1.0')):
        show_message = False
            
        for layer in yp.layers:
            if layer.type == 'MUSGRAVE':
                layer.type = 'NOISE'
                show_message = True
            for ch in layer.channels:
                if ch.override_type == 'MUSGRAVE':
                    ch.override_type = 'NOISE'
                if ch.override_1_type == 'MUSGRAVE':
                    ch.override_1_type = 'NOISE'
            for mask in layer.masks:
                if mask.type == 'MUSGRAVE':
                    mask.type = 'NOISE'
                    show_message = True

        if show_message:
            print("INFO: 'Musgrave' node is no longer available since Blender 4.1, converting it to 'Noise'..")

    # SECTION III: Updates based on the blender version and yp version

    # Version 1.1.0 and Blender 2.90 can hide default normal input
    if is_greater_than_290() and (is_created_before_290() or 
                                  LooseVersion(yp.blender_version) < LooseVersion('2.9.0') or 
                                  LooseVersion(yp.version) < LooseVersion('1.1.0')
                                  ):
        height_root_ch = get_root_height_channel(yp)
        if height_root_ch:
            inp = get_tree_input_by_name(tree, height_root_ch.name)
            if inp: 
                inp.hide_value = True
                print("INFO: " + tree.name + " Normal input is hidden since Blender 2.90!")

    # Blender 3.4 and version 1.0.9 will make sure all mix node using the newest type
    if LooseVersion(yp.version) < LooseVersion('1.0.9') and is_greater_than_340():
        print('INFO:', 'Converting old mix rgb nodes to newer ones...')
        convert_mix_nodes(tree)

    # Version 1.0.12 will use newer tangent process nodes on Blender 3.0 or above
    if is_greater_than_300() and (
            LooseVersion(yp.version) < LooseVersion('1.0.12') or is_created_before_300() or LooseVersion(yp.blender_version) < LooseVersion('3.0.0')
        ):
        update_tangent_process(tree, TANGENT_PROCESS_300)
        updated_to_tangent_process_300 = True

    # Update tangent process from Blender 2.79 to 2.8x and 2.9x
    if not is_greater_than_300() and is_greater_than_280() and (is_created_using_279() or LooseVersion(yp.blender_version) < LooseVersion('2.80.0')):
        update_tangent_process(tree, TANGENT_PROCESS)

    # Update blender version
    if LooseVersion(yp.blender_version) < get_current_blender_version_str():
        yp.blender_version = get_current_blender_version_str()

    # Update version
    if LooseVersion(yp.version) < LooseVersion(cur_version):
        yp.version = cur_version
        print('INFO:', tree.name, 'is updated to version', cur_version)

    return updated_to_tangent_process_300, updated_to_yp_200_displacement

@persistent
def update_routine(name):
    T = time.time()

    # Flags
    updated_to_tangent_process_300 = False
    updated_to_yp_200_displacement = False

    for ng in bpy.data.node_groups:
        if not hasattr(ng, 'yp'): continue
        if not ng.yp.is_ypaint_node: continue

        # Update yp trees
        flag1, flag2 = update_yp_tree(ng)
        if flag1: updated_to_tangent_process_300 = True
        if flag2: updated_to_yp_200_displacement = True

    # Remove tangent sign vertex colors for Blender 3.0+
    if updated_to_tangent_process_300:
        remove_tangent_sign_vcols()

    # Remove old displace modifiers from all objects
    if updated_to_yp_200_displacement:
        for obj in bpy.data.objects:
            for mod in reversed(obj.modifiers):
                if mod.type == 'DISPLACE' and mod.name.startswith('yP_Displace'):
                    set_active_object(obj)
                    bpy.ops.object.modifier_remove(modifier=mod.name)

    # Special update for opening Blender 2.79 file
    filepath = get_addon_filepath() + "lib.blend"
    if is_created_using_279() and is_greater_than_280() and bpy.data.filepath != filepath:

        legacy_groups = []
        newer_groups = []
        newer_group_names = []

        for ng in bpy.data.node_groups:

            m = re.match(r'^(~yPL .+)(?: Legacy)(?:_Copy)?(?:\.\d{3}?)?$', ng.name)
            if m and ng.name not in legacy_groups:
                legacy_groups.append(ng)
                new_group_name = m.group(1)
                # Tangent process has its own tangent process for blender 3.0 and above
                if new_group_name == TANGENT_PROCESS and is_greater_than_300():
                    newer_group_name = TANGENT_PROCESS_300
                newer_group_names.append(new_group_name)

        # Load node groups
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            from_ngs = data_from.node_groups
            to_ngs = data_to.node_groups
            for ng in from_ngs:
                if ng in newer_group_names:
                    to_ngs.append(ng)

        # Fill newer groups
        for name in newer_group_names:
            newer_groups.append(bpy.data.node_groups.get(name))

        # List of already copied groups
        copied_groups = []

        # Update from legacy to newer groups
        for i, legacy_ng in enumerate(legacy_groups):
            newer_ng = newer_groups[i]

            if '_Copy' not in legacy_ng.name:

                # Search for legacy tree usages
                for mat in bpy.data.materials:
                    if not mat.node_tree: continue
                    for node in mat.node_tree.nodes:
                        if node.type == 'GROUP' and node.node_tree == legacy_ng:
                            node.node_tree = newer_ng

                for group in bpy.data.node_groups:
                    for node in group.nodes:
                        if node.type == 'GROUP' and node.node_tree == legacy_ng:
                            node.node_tree = newer_ng

                print('INFO:', legacy_ng.name, 'is replaced to', newer_ng.name + '!')

                # Remove old tree
                bpy.data.node_groups.remove(legacy_ng)

                # Create info frames
                create_info_nodes(newer_ng)

            else:

                used_nodes = []
                parent_trees = []

                # Search for old tree usages
                for mat in bpy.data.materials:
                    if not mat.node_tree: continue
                    for node in mat.node_tree.nodes:
                        if node.type == 'GROUP' and node.node_tree == legacy_ng:
                            used_nodes.append(node)
                            parent_trees.append(mat.node_tree)

                for group in bpy.data.node_groups:
                    for node in group.nodes:
                        if node.type == 'GROUP' and node.node_tree == legacy_ng:
                            used_nodes.append(node)
                            parent_trees.append(group)

                #print(legacy_ng.name, used_nodes)

                if used_nodes:

                    # Remember original tree
                    ori_tree = used_nodes[0].node_tree

                    # Duplicate lib tree
                    if '_Copy' not in newer_ng.name:
                        newer_ng.name += '_Copy'
                    used_nodes[0].node_tree = newer_ng.copy()
                    new_tree = used_nodes[0].node_tree
                    #newer_ng.name = name

                    print('INFO:', ori_tree.name, 'is replaced to', new_tree.name + '!')

                    if newer_ng not in copied_groups:
                        copied_groups.append(newer_ng)

                    # Copy some nodes inside
                    for n in new_tree.nodes:
                        if n.name.startswith('_'):
                            # Try to get the node on original tree
                            ori_n = ori_tree.nodes.get(n.name)
                            if ori_n: copy_node_props(ori_n, n)

                    # Delete original tree
                    bpy.data.node_groups.remove(ori_tree)

                    # Create info frames
                    create_info_nodes(new_tree)

        # Remove already copied groups
        for ng in copied_groups:
            bpy.data.node_groups.remove(ng)

    print('INFO: ' + get_addon_title() + ' update routine are done at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

def get_inside_group_update_names(tree, update_names):

    for n in tree.nodes:
        if n.type == 'GROUP' and n.node_tree and n.node_tree.name not in update_names:
            update_names.append(n.node_tree.name)
            update_names = get_inside_group_update_names(n.node_tree, update_names)

    return update_names

def fix_missing_lib_trees(tree, problematic_trees):
    for node in tree.nodes:
        if node.type != 'GROUP' or not node.node_tree: continue
        if node.node_tree.is_missing:
            fixed_trees = [ng for ng in bpy.data.node_groups if ng.name == node.node_tree.name and not ng.is_missing]
            if fixed_trees: 
                if node.node_tree not in problematic_trees:
                    problematic_trees.append(node.node_tree)
                node.node_tree = fixed_trees[0]
        else:
            problematic_trees = fix_missing_lib_trees(node.node_tree, problematic_trees)

    return problematic_trees

def copy_lib_tree_contents(tree, lib_tree, lib_trees):

    # Check for the versions first
    cur_ver = get_lib_revision(tree)
    lib_ver = get_lib_revision(lib_tree)
    if cur_ver >= lib_ver: return

    # Update other libraries inside the tree
    for n in tree.nodes:
        if n.type == 'GROUP' and n.node_tree:
            m = re.match(r'^(~yPL .+?)(?:_Copy?)?(?:\.\d{3}?)?$', n.node_tree.name)
            if not m: continue
            lname = m.group(1)
            ltree = [t for t in lib_trees if re.search(r'^' + re.escape(lname) + r'(?:\.\d{3}?)?$', t.name)]
            if not ltree: continue
            ltree = ltree[0]
            copy_lib_tree_contents(n.node_tree, ltree, lib_trees)       

    valid_nodes = []

    # Create new nodes
    for n in lib_tree.nodes:

        # Skip some nodes
        if (n.name in tree.nodes and (
            n.name.startswith('_') or #  Underscore meant the node stays the same
            (lib_tree.name == HEMI and n.name in {'Normal', 'Vector Transform'}) # Hemi node will keep these nodes
            )): 
            nn = tree.nodes.get(n.name)
            valid_nodes.append(nn)
            continue

        # Remove current node first
        if n.name in tree.nodes:
            tree.nodes.remove(tree.nodes[n.name])

        # Create new node
        new_n = tree.nodes.new(n.bl_idname)
        new_n.name = n.name
        valid_nodes.append(new_n)

        # Checking if sub lib tree already exists
        if n.type == 'GROUP':
            # NOTE: Finding '_Copy' in name is still doing nothing here
            m = re.match(r'^(~yPL .+?)(?:_Copy?)?(?:\.\d{3}?)?$', n.node_tree.name)
            if m:
                lib_name = m.group(1)
                sublib = bpy.data.node_groups.get(lib_name)
                if sublib:
                    new_n.node_tree = sublib

            # Fallback if node tree is not found
            if new_n.node_tree == None:
                new_n.node_tree = n.node_tree

        if n.type not in {'REROUTE'}:
            copy_node_props(n, new_n, extras=['node_tree'])

    # Set parent and location
    for n in lib_tree.nodes:
        nn = tree.nodes.get(n.name)

        if n.parent != None:
            nn_parent = tree.nodes.get(n.parent.name)
            if nn and nn_parent:
                nn.parent = nn_parent
                nn_parent.location = n.parent.location.copy()

        if nn: nn.location = n.location.copy()

    # Remove invalid nodes
    for n in reversed(tree.nodes):
        if n not in valid_nodes:
            tree.nodes.remove(n)

    # Socket props that cannot be copied
    socket_exception_props = ['draw', 'from_socket', 'identifier', 'in_out', 'index', 'init_socket', 'item_type', 'parent', 'position', 'type', 'draw_color', 'is_output']

    # Create new inputs
    cur_input_names = [inp.name for inp in get_tree_inputs(tree)]
    new_input_default_dict = {}
    for inp in get_tree_inputs(lib_tree):
        if inp.name not in cur_input_names:
            description = inp.description if hasattr(inp, 'description') else ''
            ninp = new_tree_input(tree, inp.name, inp.bl_socket_idname, description)
            # NOTE: Reverse is needed because some prop need to be set first, probably not the best solution
            copy_id_props(inp, ninp, socket_exception_props, reverse=True)
            new_input_default_dict[ninp.name] = inp.default_value
        else: cur_input_names.remove(inp.name)

    # Remove remaining inputs
    for inp in reversed(get_tree_inputs(tree)):
        if inp.name in cur_input_names:
            remove_tree_input(tree, inp)
    
    # Create new outputs
    cur_output_names = [outp.name for outp in get_tree_outputs(tree)]
    for outp in get_tree_outputs(lib_tree):
        if outp.name not in cur_output_names:
            description = outp.description if hasattr(inp, 'description') else ''
            noutp = new_tree_output(tree, outp.name, outp.bl_socket_idname, description)
            # NOTE: Reverse is needed because some prop need to be set first, probably not the best solution
            copy_id_props(outp, noutp, socket_exception_props, reverse=True)
        else: cur_output_names.remove(outp.name)

    # Remove remaining outputs
    for outp in reversed(get_tree_outputs(tree)):
        if outp.name in cur_output_names:
            remove_tree_output(tree, outp)

    # TODO: What if socket has different type but same name

    # Reorder inputs and outputs
    if is_greater_than_400():
        for i, item in enumerate(lib_tree.interface.items_tree):
            cur_i = [ci for ci, citem in enumerate(tree.interface.items_tree) if citem.name == item.name and citem.in_out == item.in_out][0]
            if i != cur_i:
                cur_item = tree.interface.items_tree[cur_i]
                tree.interface.move(cur_item, i)
    else:
        # Reorder inputs
        for i, inp in enumerate(lib_tree.inputs):
            cur_i = [ci for ci, cinp in enumerate(tree.inputs) if cinp.name == inp.name][0]
            if i != cur_i:
                tree.inputs.move(cur_i, i)

        # Reorder outputs
        for i, outp in enumerate(lib_tree.outputs):
            cur_i = [ci for ci, coutp in enumerate(tree.outputs) if coutp.name == outp.name][0]
            if i != cur_i:
                tree.outputs.move(cur_i, i)

    # TODO: Check connection after reorders

    # Create links
    for l in lib_tree.links:

        from_node = tree.nodes.get(l.from_node.name)
        to_node = tree.nodes.get(l.to_node.name)

        # Get from socket index
        from_index = -1
        for i, soc in enumerate(l.from_node.outputs):
            if soc == l.from_socket:
                from_index = i
                break

        # Get to socket index
        to_index = -1
        for i, soc in enumerate(l.to_node.inputs):
            if soc == l.to_socket:
                to_index = i
                break

        # Create the link
        try: tree.links.new(from_node.outputs[from_index], to_node.inputs[to_index])
        except Exception as e: print(e)

    # Create info frames
    create_info_nodes(tree)

    # Set default value for newly created inputs
    if new_input_default_dict:
        for ng in bpy.data.node_groups:
            for n in ng.nodes:
                if n.type == 'GROUP' and n.node_tree and n.node_tree == tree:
                    for name, default_value in new_input_default_dict.items():
                        n.inputs[name].default_value = default_value
        for mat in bpy.data.materials:
            if not mat.node_tree: continue
            for n in mat.node_tree.nodes:
                if n.type == 'GROUP' and n.node_tree and n.node_tree == tree:
                    for name, default_value in new_input_default_dict.items():
                        n.inputs[name].default_value = default_value

@persistent
def update_node_tree_libs(name):
    T = time.time()

    filepaths = []
    filepaths.append(get_addon_filepath() + "lib.blend")
    if is_greater_than_281(): filepaths.append(get_addon_filepath() + "lib_281.blend")
    if is_greater_than_282(): filepaths.append(get_addon_filepath() + "lib_282.blend")

    for fp in filepaths:
        if bpy.data.filepath == fp: return

    tree_names = []
    existing_lib_names = []
    existing_actual_names = []
    missing_groups = []

    for ng in bpy.data.node_groups:

        if hasattr(ng, 'is_missing') and ng.is_missing:
            missing_groups.append(ng.name)
            print("INFO: '" + ng.name + "' is missing! Trying to reload it from library again...")
            continue

        m = re.match(r'^(~yPL .+?)(?:_Copy?)?(?:\.\d{3}?)?$', ng.name)
        if not m: continue
        if m.group(1) not in existing_lib_names:
            existing_lib_names.append(m.group(1))
        if ng.name not in existing_actual_names:
            existing_actual_names.append(ng.name)

    # Fix missing groups
    if any(missing_groups):

        # Load missing node groups
        for fp in filepaths:
            with bpy.data.libraries.load(fp) as (data_from, data_to):
                for ng in data_from.node_groups:
                    if ng not in missing_groups: continue
                    fixed_trees = [n for n in bpy.data.node_groups if n.name == ng and not n.is_missing]
                    if not fixed_trees:
                        data_to.node_groups.append(ng)

        # Fix missing trees
        problematic_trees = []
        for ng in bpy.data.node_groups:
            if hasattr(ng, 'yp') and ng.yp.is_ypaint_node:
                problematic_trees = fix_missing_lib_trees(ng, problematic_trees)

        # Remove problematic trees
        for pt in problematic_trees:
            bpy.data.node_groups.remove(pt)

    if not existing_lib_names: return

    # Load node groups
    for fp in filepaths:
        with bpy.data.libraries.load(fp) as (data_from, data_to):
            from_ngs = data_from.node_groups
            to_ngs = data_to.node_groups
            for ng in from_ngs:
                if ng in existing_lib_names:
                    tree_names.append(ng)
                    to_ngs.append(ng)

    update_names = []
    lib_trees = []

    for name in tree_names:

        lib_tree = [n for n in bpy.data.node_groups if re.search(r'^' + re.escape(name) + r'(?:\.\d{3}?)?$', n.name) and n.name not in existing_actual_names]
        if lib_tree: lib_tree = lib_tree[0]
        else: continue
        lib_trees.append(lib_tree)

        cur_trees = [n for n in bpy.data.node_groups if re.search(r'^' + re.escape(name) + r'(?:_Copy?)?(?:\.\d{3}?)?$', n.name) and n.name in existing_actual_names]

        for cur_tree in cur_trees:
            # Check lib tree revision
            cur_ver = get_lib_revision(cur_tree)
            lib_ver = get_lib_revision(lib_tree)

            if lib_ver > cur_ver:

                if name not in update_names:
                    update_names.append(name)

                # Check for group inside group
                update_names = get_inside_group_update_names(lib_tree, update_names)

                # Flip tangent if tangent process is updated to ver 1
                if name == TANGENT_PROCESS and cur_ver == 0 and lib_ver == 1:
                    flip_tangent_sign()

                print('INFO: Updating Node group', name, 'to revision', str(lib_ver) + '!')

    for name in tree_names:

        # Get library tree
        lib_tree = [n for n in bpy.data.node_groups if re.search(r'^' + re.escape(name) + r'(?:\.\d{3}?)?$', n.name) and n.name not in existing_actual_names]
        if lib_tree: lib_tree = lib_tree[0]
        else: continue

        if name not in update_names: continue

        if lib_tree.name != name:
            cur_tree = bpy.data.node_groups.get(name)
            copy_lib_tree_contents(cur_tree, lib_tree, lib_trees)
        else:

            #cur_trees = [n for n in bpy.data.node_groups if n.name.startswith(name) and n.name != name]
            cur_trees = [n for n in bpy.data.node_groups if re.search(r'^' + re.escape(name) + r'(?:_Copy?)?(?:\.\d{3}?)?$', n.name) and n.name in existing_actual_names]

            for cur_tree in cur_trees:

                used_nodes = []
                parent_trees = []

                # Search for tree usages
                for mat in bpy.data.materials:
                    if not mat.node_tree: continue
                    for node in mat.node_tree.nodes:
                        if node.type == 'GROUP' and node.node_tree == cur_tree:
                            used_nodes.append(node)
                            parent_trees.append(mat.node_tree)

                for group in bpy.data.node_groups:
                    for node in group.nodes:
                        if node.type == 'GROUP' and node.node_tree == cur_tree:
                            used_nodes.append(node)
                            parent_trees.append(group)

                if used_nodes:

                    lib_ver = get_lib_revision(lib_tree)

                    for i, node in enumerate(used_nodes):
                        cur_tree = node.node_tree
                        cur_ver = get_lib_revision(cur_tree)

                        copy_lib_tree_contents(cur_tree, lib_tree, lib_trees)

                        # Hemi revision 1 has normal input
                        if name == HEMI and cur_ver == 0 and lib_ver == 1:
                            geom = parent_trees[i].nodes.get(GEOMETRY)
                            if geom: parent_trees[i].links.new(geom.outputs['Normal'], node.inputs['Normal'])

    # Remove lib trees
    for lib_tree in lib_trees:
        bpy.data.node_groups.remove(lib_tree)

    # Remove temporary libraries (Doesn't work with Blender 2.79)
    if is_greater_than_280():
        for l in reversed(bpy.data.libraries):
            if l.filepath in filepaths:
                bpy.data.batch_remove(ids=(l,))

    print('INFO: ' + get_addon_title() + ' Node group libraries are checked at', '{:0.2f}'.format((time.time() - T) * 1000), 'ms!')

class YUpdateYPTrees(bpy.types.Operator):
    bl_idname = "node.y_update_yp_trees"
    bl_label = "Update " + get_addon_title() + " Node Groups"
    bl_description = "Update " + get_addon_title() + " node groups to newest version"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_active_ypaint_node()

    def execute(self, context):
        update_node_tree_libs('')
        update_routine('')
        return {'FINISHED'}

def register():
    bpy.utils.register_class(YUpdateYPTrees)

    bpy.app.handlers.load_post.append(update_node_tree_libs)
    bpy.app.handlers.load_post.append(update_routine)

def unregister():
    bpy.utils.unregister_class(YUpdateYPTrees)

    bpy.app.handlers.load_post.remove(update_node_tree_libs)
    bpy.app.handlers.load_post.remove(update_routine)
