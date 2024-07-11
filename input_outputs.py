import bpy, re
from . import lib
from .common import *
from .transition_common import *
from .subtree import *
from .node_arrangements import *
from .node_connections import *

def fix_io_index_360(item, items, correct_index):
    cur_index = [i for i, it in enumerate(items) if it == item]
    if cur_index and cur_index[0] != correct_index:
        items.move(cur_index[0], correct_index)

def get_tree_input_index_400(interface, item):
    index = -1
    for it in interface.items_tree:
        if item.in_out in {'INPUT', 'BOTH'} and it.in_out in {'INPUT', 'BOTH'}:
            index += 1
        if it == item:
             return index

    return index

def get_tree_output_index_400(interface, item):
    index = -1
    for it in interface.items_tree:
        if item.in_out in {'OUTPUT', 'BOTH'} and it.in_out in {'OUTPUT', 'BOTH'}:
            index += 1
        if it == item:
             return index

    return index

def fix_tree_input_index_400(interface, item, correct_index):
    if item.in_out != 'BOTH':
        outputs = [it for it in interface.items_tree if it.in_out in {'OUTPUT', 'BOTH'}]
        offset = len(outputs)
        cur_index = [i for i, it in enumerate(interface.items_tree) if it == item]
        if cur_index and cur_index[0] != correct_index + offset:
            interface.move(item, correct_index + offset)
    else:
        if get_tree_input_index_400(interface, item) == correct_index:
            return

        # HACK: Try to move using all index because interface move is still inconsistent
        for i in range(len(interface.items_tree)):
            interface.move(item, i)
            if get_tree_input_index_400(interface, item) == correct_index:
                return

def fix_tree_output_index_400(interface, item, correct_index):
    if item.in_out != 'BOTH':
        cur_index = [i for i, it in enumerate(interface.items_tree) if it == item]
        if cur_index and cur_index[0] != correct_index:
            interface.move(item, correct_index)
    else:
        if get_tree_output_index_400(interface, item) == correct_index:
            return

        # HACK: Try to move using all index because interface move is still inconsistent
        for i in range(len(interface.items_tree)):
            interface.move(item, i)
            if get_tree_output_index_400(interface, item) == correct_index:
                return

def fix_tree_input_index(tree, item, correct_index):
    if not is_greater_than_400():
        fix_io_index_360(item, tree.inputs, correct_index)
        return

    fix_tree_input_index_400(tree.interface, item, correct_index)

def fix_tree_output_index(tree, item, correct_index):
    if not is_greater_than_400():
        fix_io_index_360(item, tree.outputs, correct_index)
        return

    fix_tree_output_index_400(tree.interface, item, correct_index)

def create_input(tree, name, socket_type, valid_inputs, index, 
        dirty = False, min_value=None, max_value=None, default_value=None, hide_value=False, description=''):

    inp = get_tree_input_by_name(tree, name)
    if not inp:
        inp = new_tree_input(tree, name, socket_type, description=description, use_both=True)
        dirty = True
        if min_value != None and hasattr(inp, 'min_value'): inp.min_value = min_value
        if max_value != None and hasattr(inp, 'max_value'): inp.max_value = max_value
        if default_value != None: inp.default_value = default_value
        if hasattr(inp, 'hide_value'): inp.hide_value = hide_value

    valid_inputs.append(inp)
    fix_tree_input_index(tree, inp, index)

    return dirty

def make_outputs_first_400(interface):
    outputs = []
    for i, item in enumerate(interface.items_tree):
        if item.in_out == 'OUTPUT':
            pass

def create_output(tree, name, socket_type, valid_outputs, index, dirty=False, default_value=None):

    outp = get_tree_output_by_name(tree, name)
    if not outp:
        outp = new_tree_output(tree, name, socket_type, use_both=True)
        dirty = True
        if default_value != None: outp.default_value = default_value

    valid_outputs.append(outp)
    fix_tree_output_index(tree, outp, index)

    return dirty

def check_start_end_root_ch_nodes(group_tree, specific_channel=None):

    yp = group_tree.yp
    ypup = get_user_preferences()

    for channel in yp.channels:
        if specific_channel and channel != specific_channel: continue

        if channel.type in {'RGB', 'VALUE'}:

            # Create start linear
            if not yp.use_linear_blending and channel.colorspace != 'LINEAR' and any_layers_using_channel(channel):
                if channel.type == 'RGB':
                    start_linear = check_new_node(group_tree, channel, 'start_linear', 'ShaderNodeGamma', 'Start Linear')
                else: 
                    start_linear = check_new_node(group_tree, channel, 'start_linear', 'ShaderNodeMath', 'Start Linear')
                    start_linear.operation = 'POWER' if channel.colorspace != 'LINEAR' else 'MULTIPLY' # Multiply is probably faster if channel is linear
                start_linear.inputs[1].default_value = 1.0/GAMMA if channel.colorspace != 'LINEAR' else 1.0
            else:
                remove_node(group_tree, channel, 'start_linear')

            # Create end linear
            if channel.type == 'RGB':

                if not yp.use_linear_blending and channel.colorspace != 'LINEAR' and any_layers_using_channel(channel):
                    end_linear = check_new_node(group_tree, channel, 'end_linear', 'ShaderNodeGamma', 'End Linear')
                    end_linear.inputs[1].default_value = GAMMA
                else:
                    remove_node(group_tree, channel, 'end_linear')

                if channel.use_clamp and any_layers_using_channel(channel):
                    clamp = group_tree.nodes.get(channel.clamp)
                    if not clamp:
                        clamp = new_mix_node(group_tree, channel, 'clamp', 'Clamp')
                        clamp.inputs[0].default_value = 0.0
                        clamp.blend_type = 'MULTIPLY' # Multiply is probably faster than Mix
                        set_mix_clamp(clamp, True)
                else:
                    remove_node(group_tree, channel, 'clamp')

            elif channel.type == 'VALUE':

                if not yp.use_linear_blending and (channel.colorspace != 'LINEAR' or channel.use_clamp) and any_layers_using_channel(channel):
                    end_linear = check_new_node(group_tree, channel, 'end_linear', 'ShaderNodeMath', 'End Linear & Clamp')
                    end_linear.operation = 'POWER' if channel.colorspace != 'LINEAR' else 'MULTIPLY' # Multiply is probably faster if channel is linear
                    end_linear.use_clamp = channel.use_clamp
                    end_linear.inputs[1].default_value = GAMMA if channel.colorspace != 'LINEAR' else 1.0
                else:
                    remove_node(group_tree, channel, 'end_linear')

        elif channel.type == 'NORMAL':

            # Remember height tweak prop from node
            end_max_height_tweak = group_tree.nodes.get(channel.end_max_height_tweak)
            if end_max_height_tweak:
                if 'Height Tweak' in end_max_height_tweak.inputs: channel.height_tweak = end_max_height_tweak.inputs['Height Tweak'].default_value

                # Rename fcurve datapath
                for fcs in get_action_and_driver_fcurves(group_tree):
                    for fc in fcs:
                        match = re.match(r'^nodes\["' + channel.end_max_height_tweak + '"\]\.inputs\[(\d+)\]\.default_value$', fc.data_path)
                        if match:
                            index = int(match.group(1))
                            if end_max_height_tweak.inputs[index].name == 'Height Tweak':
                                fc.data_path = channel.path_from_id() + '.height_tweak'

            if not is_greater_than_300() and channel.enable_subdiv_setup:
                if not is_greater_than_280():
                    lib_name = lib.CHECK_INPUT_NORMAL_MIXED_BL27
                else: lib_name = lib.CHECK_INPUT_NORMAL_MIXED
            elif not channel.enable_smooth_bump and channel.enable_subdiv_setup: # and ypup.eevee_next_displacement:
                lib_name = lib.CHECK_INPUT_NORMAL_GEOMETRY
            else: lib_name = lib.CHECK_INPUT_NORMAL

            start_normal_filter = replace_new_node(
                    group_tree, channel, 'start_normal_filter', 'ShaderNodeGroup', 'Start Normal Filter', lib_name)

            if is_normal_height_input_connected(channel):
                #if channel.enable_smooth_bump:
                #    start_bump_process = replace_new_node(group_tree, channel, 'start_bump_process', 
                #                                            'ShaderNodeGroup', 'Start Bump Process', lib.START_FINE_BUMP_PROCESS, hard_replace=True)
                #else:
                start_bump_process = replace_new_node(group_tree, channel, 'start_bump_process', 
                    'ShaderNodeGroup', 'Start Bump Process', lib.START_BUMP_PROCESS, hard_replace=True)
            else:
                remove_node(group_tree, channel, 'start_bump_process')

            process_lib_name = ''

            if (any_layers_using_channel(channel) and any_layers_using_bump_map(channel)) or is_normal_height_input_connected(channel):

                # Add end linear for converting displacement map to grayscale
                if channel.enable_smooth_bump:
                    if is_normal_height_input_connected(channel):
                        if channel.enable_subdiv_setup: # and ypup.eevee_next_displacement:
                            process_lib_name = lib.FINE_BUMP_PROCESS_START_BUMP_SUBDIV_ON
                        else: process_lib_name = lib.FINE_BUMP_PROCESS_START_BUMP
                    else: 
                        process_lib_name = lib.FINE_BUMP_PROCESS
                else:
                    if channel.enable_subdiv_setup: # and ypup.eevee_next_displacement:
                        process_lib_name = lib.BUMP_PROCESS_SUBDIV_ON
                    else: process_lib_name = lib.BUMP_PROCESS

                # Engine filter is needed if smooth bump is on and subdiv is on
                #if channel.enable_smooth_bump and channel.enable_subdiv_setup: # and ypup.eevee_next_displacement:
                if yp.use_baked and channel.enable_subdiv_setup:
                    lib_name = lib.ENGINE_FILTER if is_greater_than_280() else lib.ENGINE_FILTER_LEGACY
                    end_normal_engine_filter = replace_new_node(
                            group_tree, channel, 'end_normal_engine_filter', 'ShaderNodeGroup', 'End Engine Filter', lib_name)
                    for inp in end_normal_engine_filter.inputs:
                        inp.default_value = (0.5, 0.5, 1.0, 1.0)
                else:
                    remove_node(group_tree, channel, 'end_normal_engine_filter')

                # Create a node to do height tweak
                if channel.enable_height_tweak:
                    if channel.enable_smooth_bump:
                        lib_name = lib.MAX_HEIGHT_TWEAK_SMOOTH
                    else: lib_name = lib.MAX_HEIGHT_TWEAK

                    end_max_height_tweak = replace_new_node(group_tree, channel, 'end_max_height_tweak', 
                                                            'ShaderNodeGroup', 'Max Height Tweak', lib_name, hard_replace=True)

                    # Set height tweak prop to node
                    end_max_height_tweak.inputs['Height Tweak'].default_value = channel.height_tweak

                    # Rename fcurve datapath
                    for fcs in get_action_and_driver_fcurves(group_tree):
                        for fc in fcs:
                            if fc.data_path == channel.path_from_id() + '.height_tweak':
                                index = [i for i, inp in enumerate(end_max_height_tweak.inputs) if inp.name == 'Height Tweak'][0]
                                fc.data_path = 'nodes["' + end_max_height_tweak.name + '"].inputs[' + str(index) + '].default_value'

                else:
                    remove_node(group_tree, channel, 'end_max_height_tweak')
            else:
                remove_node(group_tree, channel, 'end_linear')
                #remove_node(group_tree, channel, 'end_max_height')
                remove_node(group_tree, channel, 'end_max_height_tweak')

            # Remember smooth normal tweak prop from node when certain case met
            end_linear = group_tree.nodes.get(channel.end_linear)
            if end_linear and 'Normal Tweak' in end_linear.inputs and(
                    (not channel.enable_smooth_bump and channel.enable_smooth_normal_tweak) 
                    or (channel.enable_smooth_bump and not channel.enable_smooth_normal_tweak)
                    or (channel.enable_smooth_bump and channel.enable_smooth_normal_tweak and process_lib_name != '' and end_linear.node_tree.name != process_lib_name)
                    ):

                channel.smooth_normal_tweak = end_linear.inputs['Normal Tweak'].default_value

                # Rename fcurve datapath
                for fcs in get_action_and_driver_fcurves(group_tree):
                    for fc in fcs:
                        match = re.match(r'^nodes\["' + channel.end_linear + '"\]\.inputs\[(\d+)\]\.default_value$', fc.data_path)
                        if match:
                            index = int(match.group(1))
                            if end_linear.inputs[index].name == 'Normal Tweak':
                                fc.data_path = channel.path_from_id() + '.smooth_normal_tweak'

            if process_lib_name != '':

                end_linear = replace_new_node(group_tree, channel, 'end_linear', 'ShaderNodeGroup', 'Bump Process',
                        process_lib_name, hard_replace=True)

                # Smooth normal tweak
                if channel.enable_smooth_bump and channel.enable_smooth_normal_tweak:

                    end_linear.inputs['Normal Tweak'].default_value = channel.smooth_normal_tweak

                    # Rename fcurve datapath
                    for fcs in get_action_and_driver_fcurves(group_tree):
                        for fc in fcs:
                            if fc.data_path == channel.path_from_id() + '.smooth_normal_tweak':
                                index = [i for i, inp in enumerate(end_linear.inputs) if inp.name == 'Normal Tweak'][0]
                                fc.data_path = 'nodes["' + end_linear.name + '"].inputs[' + str(index) + '].default_value'

                elif 'Normal Tweak' in end_linear.inputs:

                    # Rename fcurve datapath
                    for fcs in get_action_and_driver_fcurves(group_tree):
                        for fc in fcs:
                            match = re.match(r'^nodes\["' + channel.end_linear + '"\]\.inputs\[(\d+)\]\.default_value$', fc.data_path)
                            if match:
                                index = int(match.group(1))
                                if end_linear.inputs[index].name == 'Normal Tweak':
                                    fc.data_path = channel.path_from_id() + '.smooth_normal_tweak'

                    # Set normal tweak value to 1.0 if it's disabled
                    end_linear.inputs['Normal Tweak'].default_value = 1.0

def check_all_channel_ios(yp, reconnect=True, specific_layer=None, remove_props=False, force_height_io=False, hard_reset=False):

    #print("Checking YP IO. Specific Layer: " + str(specific_layer))

    group_tree = yp.id_data

    input_index = 0
    output_index = 0
    valid_inputs = []
    valid_outputs = []

    for ch in yp.channels:

        if ch.type == 'VALUE':
            create_input(group_tree, ch.name, channel_socket_input_bl_idnames[ch.type], 
                    valid_inputs, input_index, min_value = 0.0, max_value = 1.0)
        elif ch.type == 'RGB':
            create_input(group_tree, ch.name, channel_socket_input_bl_idnames[ch.type], 
                    valid_inputs, input_index, default_value=(1,1,1,1))
        elif ch.type == 'NORMAL':
            # Use 999 as normal z value so it will fallback to use geometry normal at checking process
            create_input(group_tree, ch.name, channel_socket_input_bl_idnames[ch.type], 
                    valid_inputs, input_index, default_value=(999,999,999), hide_value=True)

        create_output(group_tree, ch.name, channel_socket_output_bl_idnames[ch.type], 
                valid_outputs, output_index)

        if ch.io_index != input_index:
            ch.io_index = input_index

        input_index += 1
        output_index += 1

        #if ch.type == 'RGB' and ch.enable_alpha:
        if ch.enable_alpha:

            name = ch.name + io_suffix['ALPHA']

            create_input(group_tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, 
                    min_value = 0.0, max_value = 1.0, default_value = 0.0)

            create_output(group_tree, name, 'NodeSocketFloat', valid_outputs, output_index)

            input_index += 1
            output_index += 1

            # Backface mode
            if ch.backface_mode != 'BOTH':
                end_backface = check_new_node(group_tree, ch, 'end_backface', 'ShaderNodeMath', 'Backface')
                end_backface.use_clamp = True

            if ch.backface_mode == 'FRONT_ONLY':
                end_backface.operation = 'SUBTRACT'
            elif ch.backface_mode == 'BACK_ONLY':
                end_backface.operation = 'MULTIPLY'

        if not ch.enable_alpha or ch.backface_mode == 'BOTH':
                remove_node(group_tree, ch, 'end_backface')

        # Displacement IO
        if ch.type == 'NORMAL' and (ch.enable_subdiv_setup or force_height_io):

            group_node = get_active_ypaint_node()

            name = ch.name + io_suffix['HEIGHT']

            height_default_value = 0.0
            create_input(group_tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, 
                    min_value = 0.0, max_value = 1.0, default_value = height_default_value, hide_value=True)
            if group_node.node_tree == group_tree:
                group_node.inputs[name].default_value = height_default_value
            input_index += 1

            create_output(group_tree, name, 'NodeSocketFloat', valid_outputs, output_index)
            output_index += 1

            name = ch.name + io_suffix['MAX_HEIGHT']

            max_height_default_value = 0.1
            create_input(group_tree, name, 'NodeSocketFloat', valid_inputs, input_index, default_value=max_height_default_value)
            # Set node default value
            if group_node.node_tree == group_tree:
                group_node.inputs[name].default_value = max_height_default_value
            input_index += 1

            create_output(group_tree, name, 'NodeSocketFloat', valid_outputs, output_index)
            output_index += 1

            name = ch.name + io_suffix['VDISP']

            create_input(group_tree, name, 'NodeSocketVector', valid_inputs, input_index, default_value=(0,0,0), hide_value=True)
            input_index += 1

            create_output(group_tree, name, 'NodeSocketVector', valid_outputs, output_index)
            output_index += 1

    # Check start and end nodes
    check_start_end_root_ch_nodes(group_tree)

    specific_channel = None
    if yp.layer_preview_mode:
        create_output(group_tree, LAYER_VIEWER, 'NodeSocketColor', valid_outputs, output_index)
        output_index += 1

        name = 'Layer Alpha Viewer'
        create_output(group_tree, LAYER_ALPHA_VIEWER, 'NodeSocketColor', valid_outputs, output_index)
        output_index += 1

    # Check for invalid io
    for inp in get_tree_inputs(group_tree):
        if inp not in valid_inputs:
            remove_tree_input(group_tree, inp)

    for outp in get_tree_outputs(group_tree):
        if outp not in valid_outputs:
            remove_tree_output(group_tree, outp)

    # Check uv maps
    check_uv_nodes(yp)

    # Update layer IO
    for layer in yp.layers:
        if specific_layer and layer != specific_layer: continue
        specific_ch = None
        if yp.layer_preview_mode and yp.active_channel_index < len(layer.channels):
            specific_ch = layer.channels[yp.active_channel_index]
        check_all_layer_channel_io_and_nodes(layer, specific_ch=specific_ch, do_recursive=False, remove_props=False, hard_reset=hard_reset)

    if reconnect:
        # Rearrange layers
        for layer in yp.layers:
            if specific_layer and layer != specific_layer: continue
            reconnect_layer_nodes(layer)
            rearrange_layer_nodes(layer)

        # Rearrange nodes
        reconnect_yp_nodes(group_tree)
        rearrange_yp_nodes(group_tree)

def check_all_layer_channel_io_and_nodes(layer, tree=None, specific_ch=None, do_recursive=True, remove_props=False, hard_reset=False): #, check_uvs=False): #, has_parent=False):

    #print("Checking layer IO. Layer: " + layer.name + ' Specific Channel: ' + str(specific_ch))

    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)

    # Check uv maps
    #if check_uvs:
    #    check_uv_nodes(yp)

    # Check layer tree io
    check_layer_tree_ios(layer, tree, remove_props, hard_reset=hard_reset)

    # Get source_tree
    source_tree = get_source_tree(layer, tree)

    # Find override channels
    #using_vector = is_layer_using_vector(layer)

    # Mapping node
    #if layer.type not in {'BACKGROUND', 'VCOL', 'GROUP', 'COLOR'} or using_vector:
    if is_layer_using_vector(layer):
        mapping = source_tree.nodes.get(layer.mapping)
        if not mapping:
            mapping = new_node(source_tree, layer, 'mapping', 'ShaderNodeMapping', 'Mapping')

    # Flip Y
    #update_image_flip_y(self, context)

    # Linear node
    check_layer_image_linear_node(layer, source_tree)

    # Check the need of bump process
    check_layer_bump_process(layer, tree)

    # Check the need of divider alpha
    check_layer_divider_alpha(layer)

    # Update transition related nodes
    height_ch = get_height_channel(layer)
    if height_ch:
        check_transition_bump_nodes(layer, tree, height_ch)

    # Channel nodes
    for i, ch in enumerate(layer.channels):
        if specific_ch and specific_ch != ch: continue
        root_ch = yp.channels[i]

        # Update layer ch blend type
        check_blend_type_nodes(root_ch, layer, ch)

        if root_ch.type != 'NORMAL': # Because normal map related nodes should already created
            # Check mask mix nodes
            check_mask_mix_nodes(layer, tree, specific_ch=ch)

    # Mask nodes
    #for mask in layer.masks:
    #    check_mask_image_linear_node(mask)

    # Linear nodes
    check_yp_linear_nodes(yp, layer, False)

    # Check other affected layers
    if do_recursive:
        do_recursive = False
        other_layers = []

        # Check parent layers
        for pid in get_list_of_parent_ids(layer):
            parent = yp.layers[pid]
            other_layers.append(parent)

        # Check child layers
        childs, child_ids = get_list_of_all_childs_and_child_ids(layer)
        for child in childs: 
            other_layers.append(child)

        # Check background layers
        layer_idx = get_layer_index(layer)
        bgs = [l for i, l in enumerate(yp.layers) if i < layer_idx and l.type == 'BACKGROUND']
        other_layers.extend(bgs)

        # Recursive to other affected layers
        for ol in other_layers:
            check_all_layer_channel_io_and_nodes(ol, do_recursive=do_recursive, hard_reset=hard_reset)
            reconnect_layer_nodes(ol)
            rearrange_layer_nodes(ol)

def recheck_background_layers_ios(yp, index_dict):
    for i, layer in enumerate(yp.layers):
        if layer.type != 'BACKGROUND': continue
        if index_dict[layer.name] != i or len(yp.layers) != len(index_dict):
            check_all_layer_channel_io_and_nodes(layer, do_recursive=False)
            reconnect_layer_nodes(layer)
            rearrange_layer_nodes(layer)

def create_prop_input(entity, prop_name, valid_inputs, input_index, dirty):

    root_tree = entity.id_data
    yp = root_tree.yp

    m1 = re.match(r'^yp\.layers\[(\d+)\].*', entity.path_from_id())

    if m1:
        layer_index = int(m1.group(1))
        layer = yp.layers[int(layer_index)]
    else:
        return False

    # Get property rna
    entity_rna = type(entity).bl_rna
    rna = entity_rna.properties[prop_name]

    # Get prop value
    prop_value = getattr(entity, prop_name)

    # Get socket type
    if type(prop_value) == float:
        socket_type = 'NodeSocketFloat'
        if rna.subtype == 'FACTOR':
            socket_type = 'NodeSocketFloatFactor'
        default_value = rna.default
    elif type(prop_value) == Color:
        socket_type = 'NodeSocketColor'
        default_value = (rna.default, rna.default, rna.default, 1.0)
    else:
        return False # Not implemented yet

    layer_node = root_tree.nodes.get(layer.group_node)
    tree = layer_node.node_tree
    input_name = get_entity_input_name(entity, prop_name)

    inp_dirty = create_input(tree, input_name, socket_type, 
            valid_inputs, input_index, False,
            min_value=rna.soft_min, max_value=rna.soft_max, default_value=default_value, 
            description=rna.description)

    # Set default value
    if inp_dirty:
        inp = layer_node.inputs.get(input_name)
        if type(prop_value) == Color:
            inp.default_value = (prop_value.r, prop_value.g, prop_value.b, 1.0)
        else: inp.default_value = prop_value
        dirty = True

    # Set animation data path back
    if root_tree.animation_data and root_tree.animation_data.action:
        # Example: yp.layers[0].channels[0].intensity_value'
        for fc in root_tree.animation_data.action.fcurves:
            if fc.data_path == 'yp.layers[' + str(layer_index) + ']' + input_name:
                fc.data_path = 'nodes["' + layer_node.name + '"].inputs[' + str(input_index) + '].default_value'
        for driver in root_tree.animation_data.drivers:
            if driver.data_path == 'yp.layers[' + str(layer_index) + ']' + input_name:
                driver.data_path = 'nodes["' + layer_node.name + '"].inputs[' + str(input_index) + '].default_value'

    return dirty

def check_layer_tree_ios(layer, tree=None, remove_props=False, hard_reset=False):

    yp = layer.id_data.yp
    if not tree: tree = get_tree(layer)
    root_tree = layer.id_data
    layer_node = root_tree.nodes.get(layer.group_node)

    # Remove all inputs first if hard reset is True
    if hard_reset:
        for inp in reversed(get_tree_inputs(tree)):
            remove_tree_input(tree, inp)

    dirty = False

    input_index = 0
    output_index = 0
    valid_inputs = []
    valid_outputs = []

    has_parent = layer.parent_idx != -1
    need_prev_normal = check_need_prev_normal(layer)

    layer_enabled = get_layer_enabled(layer)
    
    trans_bump_ch = get_transition_bump_channel(layer)

    # Rename fcurve and driver data path before rearranging the inputs
    if root_tree.animation_data and root_tree.animation_data.action:
        # Example: nodes["Group.003"].inputs[9].default_value'
        for fc in root_tree.animation_data.action.fcurves:
            m = re.match(r'^nodes\["' + layer_node.name + '"\]\.inputs\[(\d+)\]\.default_value$', fc.data_path)
            if m:
                inp = layer_node.inputs[int(m.group(1))]
                fc.data_path = 'yp.layers[' + str(get_layer_index(layer)) + ']' + inp.name
        for driver in root_tree.animation_data.drivers:
            m = re.match(r'^nodes\["' + layer_node.name + '"\]\.inputs\[(\d+)\]\.default_value$', driver.data_path)
            if m:
                inp = layer_node.inputs[int(m.group(1))]
                driver.data_path = 'yp.layers[' + str(get_layer_index(layer)) + ']' + inp.name

    # Prop inputs
    if not remove_props and layer_enabled:

        dirty = create_prop_input(layer, 'intensity_value', valid_inputs, input_index, dirty)
        input_index += 1

        # Layer prop inputs
        if layer.enable_blur_vector:
            dirty = create_prop_input(layer, 'blur_vector_factor', valid_inputs, input_index, dirty)
            input_index += 1
        
        # Channel prop inputs
        for i, ch in enumerate(layer.channels):
            if not get_channel_enabled(ch): continue

            root_ch = yp.channels[i]

            # Get default value
            default_value = ch.intensity_value

            # Create intensity socket
            dirty = create_prop_input(ch, 'intensity_value', valid_inputs, input_index, dirty)
            input_index += 1

            # Override values
            if ch.override and ch.override_type == 'DEFAULT':
                if root_ch.type == 'VALUE':
                    dirty = create_prop_input(ch, 'override_value', valid_inputs, input_index, dirty)
                    input_index += 1
                else:
                    dirty = create_prop_input(ch, 'override_color', valid_inputs, input_index, dirty)
                    input_index += 1

            # Override 1 values
            if ch.override_1 and ch.override_1_type == 'DEFAULT':
                dirty = create_prop_input(ch, 'override_1_color', valid_inputs, input_index, dirty)
                input_index += 1

            if root_ch.type == 'NORMAL':

                # Height/bump distance input
                if ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:
                    dirty = create_prop_input(ch, 'bump_distance', valid_inputs, input_index, dirty)
                    input_index += 1

                # Height/bump midlevel input
                if ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:
                    dirty = create_prop_input(ch, 'bump_midlevel', valid_inputs, input_index, dirty)
                    input_index += 1

                # Normal map strength input
                if ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'}:
                    dirty = create_prop_input(ch, 'normal_strength', valid_inputs, input_index, dirty)
                    input_index += 1
                elif ch.normal_map_type == 'VECTOR_DISPLACEMENT_MAP':
                    dirty = create_prop_input(ch, 'vdisp_strength', valid_inputs, input_index, dirty)
                    input_index += 1

                # Smooth bump multiplier input:
                if root_ch.enable_smooth_bump:
                    if ch.normal_map_type in {'BUMP_MAP', 'BUMP_NORMAL_MAP'}:
                        dirty = create_prop_input(ch, 'bump_smooth_multiplier', valid_inputs, input_index, dirty)
                        input_index += 1

                # Normal height/bump distance input
                #if ch.normal_map_type in {'NORMAL_MAP', 'BUMP_NORMAL_MAP'}:
                #    dirty = create_prop_input( ch, 'normal_bump_distance', valid_inputs, input_index, dirty)
                #    input_index += 1

                # Transition bump inputs
                if ch.enable_transition_bump:
                    dirty = create_prop_input(ch, 'transition_bump_distance', valid_inputs, input_index, dirty)
                    input_index += 1

                    dirty = create_prop_input(ch, 'transition_bump_value', valid_inputs, input_index, dirty)
                    input_index += 1

                    dirty = create_prop_input(ch, 'transition_bump_second_edge_value', valid_inputs, input_index, dirty)
                    input_index += 1

                    # Transition bump crease factor input
                    if ch.transition_bump_crease and not ch.transition_bump_flip:
                        dirty = create_prop_input(ch, 'transition_bump_crease_factor', valid_inputs, input_index, dirty)
                        input_index += 1

                        dirty = create_prop_input(ch, 'transition_bump_crease_power', valid_inputs, input_index, dirty)
                        input_index += 1

                    if ch.transition_bump_falloff and ch.transition_bump_falloff_type == 'EMULATED_CURVE':
                        dirty = create_prop_input(ch, 'transition_bump_falloff_emulated_curve_fac', valid_inputs, input_index, dirty)
                        input_index += 1

            elif trans_bump_ch:

                dirty = create_prop_input(ch, 'transition_bump_fac', valid_inputs, input_index, dirty)
                input_index += 1

                if ch.enable_transition_ramp:

                    dirty = create_prop_input(ch, 'transition_bump_second_fac', valid_inputs, input_index, dirty)
                    input_index += 1

            if ch.enable_transition_ramp:
                dirty = create_prop_input(ch, 'transition_ramp_intensity_value', valid_inputs, input_index, dirty)
                input_index += 1

            if ch.enable_transition_ao:
                dirty = create_prop_input(ch, 'transition_ao_intensity', valid_inputs, input_index, dirty)
                input_index += 1
        
                dirty = create_prop_input(ch, 'transition_ao_power', valid_inputs, input_index, dirty)
                input_index += 1

                dirty = create_prop_input(ch, 'transition_ao_color', valid_inputs, input_index, dirty)
                input_index += 1

                dirty = create_prop_input(ch, 'transition_ao_inside_intensity', valid_inputs, input_index, dirty)
                input_index += 1

        # Mask prop inputs
        for mask in layer.masks:
            if not mask.enable: continue

            # Create intensity socket
            dirty = create_prop_input(mask, 'intensity_value', valid_inputs, input_index, dirty)
            input_index += 1

            # Mask blur vector
            if mask.enable_blur_vector:
                dirty = create_prop_input(mask, 'blur_vector_factor', valid_inputs, input_index, dirty)
                input_index += 1

            # Color ID
            if mask.type == 'COLOR_ID':
                dirty = create_prop_input(mask, 'color_id', valid_inputs, input_index, dirty)
                input_index += 1

    # Tree input and outputs
    for i, ch in enumerate(layer.channels):
        root_ch = yp.channels[i]
        channel_enabled = get_channel_enabled(ch, layer, root_ch)

        force_normal_input = root_ch.type == 'NORMAL' and need_prev_normal and layer_enabled

        if channel_enabled or force_normal_input:
            dirty = create_input(tree, root_ch.name, channel_socket_input_bl_idnames[root_ch.type], 
                    valid_inputs, input_index, dirty)
            input_index += 1

        if channel_enabled:
            dirty = create_output(tree, root_ch.name, channel_socket_output_bl_idnames[root_ch.type], 
                    valid_outputs, output_index, dirty)
            output_index += 1

        # Alpha IO
        if root_ch.enable_alpha or has_parent:

            name = root_ch.name + io_suffix['ALPHA']

            if channel_enabled or force_normal_input:
                dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, dirty)
                input_index += 1

            if channel_enabled:
                dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, output_index, dirty)
                output_index += 1

        # Displacement IO
        if root_ch.type == 'NORMAL':


            name = root_ch.name + io_suffix['HEIGHT']

            if channel_enabled or force_normal_input:
                dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, dirty)
                input_index += 1

            if channel_enabled:
                dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, output_index, dirty)
                output_index += 1

            if root_ch.enable_smooth_bump:

                for letter in nsew_letters:

                    name = root_ch.name + ' Height ' + letter.upper()
                    
                    if channel_enabled or force_normal_input:
                        dirty = create_input(tree, name, 'NodeSocketFloat', valid_inputs, input_index, dirty)
                        input_index += 1

                    if channel_enabled:
                        dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, output_index, dirty)
                        output_index += 1
                        pass

            if has_parent or (is_normal_height_input_connected(root_ch) and root_ch.enable_smooth_bump):

                name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA']

                if channel_enabled or force_normal_input:
                    dirty = create_input(tree, name, 'NodeSocketFloatFactor', valid_inputs, input_index, dirty)
                    input_index += 1

                if channel_enabled:
                    dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, output_index, dirty)
                    output_index += 1

                if root_ch.enable_smooth_bump:

                    for letter in nsew_letters:
                        name = root_ch.name + ' Height ' + letter.upper() + io_suffix['ALPHA']

                        if channel_enabled or force_normal_input:
                            dirty = create_input(tree, name, 'NodeSocketFloat', valid_inputs, input_index, dirty)
                            input_index += 1

                        if channel_enabled:
                            dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, output_index, dirty)
                            output_index += 1

            name = root_ch.name + io_suffix['MAX_HEIGHT']

            if channel_enabled or force_normal_input:

                dirty = create_input(tree, name, 'NodeSocketFloat', valid_inputs, input_index, dirty)
                input_index += 1

            if channel_enabled:
                dirty = create_output(tree, name, 'NodeSocketFloat', valid_outputs, output_index, dirty)
                output_index += 1

            name = root_ch.name + io_suffix['VDISP']

            if channel_enabled or force_normal_input:

                dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
                input_index += 1

            if channel_enabled:
                dirty = create_output(tree, name, 'NodeSocketVector', valid_outputs, output_index, dirty)
                output_index += 1

    # Tree background inputs
    if layer.type in {'BACKGROUND', 'GROUP'}:

        for i, ch in enumerate(layer.channels):
            root_ch = yp.channels[i]
            channel_enabled = get_channel_enabled(ch, layer, root_ch)

            #if yp.disable_quick_toggle and not channel_enabled: continue
            if not channel_enabled: continue

            root_ch = yp.channels[i]

            if root_ch.type != 'NORMAL' or (layer.type == 'GROUP' and is_layer_using_normal_map(layer, root_ch)):

                name = root_ch.name + io_suffix[layer.type]
                dirty = create_input(tree, name, channel_socket_input_bl_idnames[root_ch.type],
                        valid_inputs, input_index, dirty)
                input_index += 1

                # Alpha Input
                if root_ch.enable_alpha or layer.type == 'GROUP':

                    name = root_ch.name + io_suffix['ALPHA'] + io_suffix[layer.type]
                    dirty = create_input(tree, name, 'NodeSocketFloatFactor',
                            valid_inputs, input_index, dirty)
                    input_index += 1

            # Displacement Input
            if root_ch.type == 'NORMAL' and layer.type == 'GROUP' and is_height_process_needed(layer):

                #if not root_ch.enable_smooth_bump:

                name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['GROUP']
                dirty = create_input(tree, name, 'NodeSocketFloat',
                        valid_inputs, input_index, dirty)
                input_index += 1

                if root_ch.enable_smooth_bump:

                    for letter in nsew_letters:
                        name = root_ch.name + io_suffix['HEIGHT_' + letter.upper()] + io_suffix['GROUP']
                        dirty = create_input(tree, name, 'NodeSocketFloat', valid_inputs, input_index, dirty)
                        input_index += 1

                name = root_ch.name + io_suffix['HEIGHT'] + io_suffix['ALPHA'] + io_suffix['GROUP']
                dirty = create_input(tree, name, 'NodeSocketFloat',
                        valid_inputs, input_index, dirty)
                input_index += 1

                if root_ch.enable_smooth_bump:

                    for letter in nsew_letters:
                        name = root_ch.name + io_suffix['HEIGHT_' + letter.upper()] + io_suffix['ALPHA'] + io_suffix['GROUP']
                        dirty = create_input(tree, name, 'NodeSocketFloat', valid_inputs, input_index, dirty)
                        input_index += 1

                name = root_ch.name + io_suffix['MAX_HEIGHT'] + io_suffix['GROUP']
                dirty = create_input(tree, name, 'NodeSocketFloat', valid_inputs, input_index, dirty)
                input_index += 1

    # Create UV inputs
    for uv in yp.uvs:
        if is_uv_input_needed(layer, uv.name):
            name = uv.name + io_suffix['UV']
            dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
            input_index += 1

        if is_tangent_input_needed(layer, uv.name):

            name = uv.name + io_suffix['TANGENT']
            dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
            input_index += 1

            name = uv.name + io_suffix['BITANGENT']
            dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
            input_index += 1

    # Other than uv texcoord name container
    texcoords = []

    # Check layer texcoords
    if layer_enabled and layer.texcoord_type != 'UV' and layer.type not in {'VCOL', 'COLOR', 'HEMI', 'GROUP', 'BACKGROUND'}:
        texcoords.append(layer.texcoord_type)

    for mask in layer.masks:
        if get_mask_enabled(mask, layer) and mask.texcoord_type != 'UV' and mask.type not in {'VCOL', 'COLOR_ID', 'OBJECT_INDEX', 'HEMI'} and mask.texcoord_type not in texcoords:
            texcoords.append(mask.texcoord_type)

    for texcoord in texcoords:
        name = io_names[texcoord]
        dirty = create_input(tree, name, 'NodeSocketVector', valid_inputs, input_index, dirty)
        input_index += 1

    if yp.layer_preview_mode:
        dirty = create_output(tree, LAYER_VIEWER, 'NodeSocketColor', valid_outputs, output_index, dirty)
        output_index += 1

        dirty = create_output(tree, LAYER_ALPHA_VIEWER, 'NodeSocketColor', valid_outputs, output_index, dirty)
        output_index += 1

    # Deleting invalid inputs
    #for i, inp in reversed(list(enumerate(get_tree_inputs(tree)))):
    for i, inp in enumerate(get_tree_inputs(tree)):
        if inp not in valid_inputs:
            # Set input prop before deleting input socket
            if inp.name.startswith('.'):

                # For fully implemented prop only
                if not any(prop for prop in [
                    #'transition_bump_value', 
                    #'transition_bump_second_edge_value',
                    ] if prop in inp.name): 

                    # Rename fcurve path first before deleting the input
                    #if root_tree.animation_data and root_tree.animation_data.action:
                    #    for fc in root_tree.animation_data.action.fcurves:
                    #        if fc.data_path == 'nodes["' + layer_node.name + '"].inputs[' + str(i) + '].default_value':
                    #            print([n.name for n in layer_node.inputs])
                    #            print(fc.data_path, inp.name)
                    #            fc.data_path = 'yp.layers[' + str(get_layer_index(layer)) + ']' + inp.name

                    # Set value back to prop
                    val = layer_node.inputs.get(inp.name).default_value
                    socket_type = inp.socket_type if is_greater_than_400() else inp.type
                    if socket_type in {'NodeSocketColor', 'RGBA'}:
                        try: exec('layer' + inp.name + ' = (val[0], val[1], val[2])')
                        except Exception as e: print(e)
                    else:
                        try: exec('layer' + inp.name + ' = val')
                        except Exception as e: print(e)

            # Remove input socket
            remove_tree_input(tree, inp)

    # Deleting invalid outputs
    for outp in get_tree_outputs(tree):
        if outp not in valid_outputs:
            remove_tree_output(tree, outp)

    return dirty

